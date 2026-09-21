package phshowoa;

import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.List;
import java.util.Random;
import java.util.concurrent.Callable;
import java.util.concurrent.ExecutionException;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.function.Consumer;

/** Algorithms 1-3. Workers read a generation snapshot; reduction is index ordered. */
public final class Solver {
    private final Config config;
    private final Evaluator evaluator;
    private final Repair repair;
    private final Operators operators;

    public Solver(Problem problem, Config config) {
        this.config = config.copy(); this.config.validate();
        evaluator = new Evaluator(problem); repair = new Repair(evaluator);
        operators = new Operators(evaluator, repair);
    }

    public Result solve() { return solve(null); }

    public Result solve(Consumer<Result.Progress> listener) {
        long start = System.nanoTime();
        ExecutorService pool = config.workers == 1 ? null : Executors.newFixedThreadPool(config.workers);
        try {
            List<Callable<Solution>> initialization = new ArrayList<Callable<Solution>>();
            for (int i = 0; i < config.populationSize; i++) {
                final int index = i;
                initialization.add(() -> {
                    Random random = random(0, 0, index);
                    Solution initial = construct(random);
                    return initial == null ? null : initializeSA(initial, random);
                });
            }
            List<Solution> population = execute(initialization, pool);
            Solution seedSolution = null;
            for (Solution s : population) if (s != null) { seedSolution = s; break; }
            if (seedSolution == null) throw new IllegalStateException(
                    "No feasible initial solution found within construction attempts; this is not a proof of infeasibility."
                    + " Check fleet/time windows or increase --construction-attempts.");
            for (int i = 0; i < population.size(); i++) if (population.get(i) == null)
                population.set(i, initializeSA(seedSolution, random(3, 0, i)));
            Solution best = Collections.min(population, evaluator::compare);
            Solution stagnationBest = best;
            int noImprove = 0, localSearchCalls = 0, diversifications = 0;
            long sho = 0, woa = 0, worse = 0;
            List<Result.Progress> history = new ArrayList<Result.Progress>();
            record(history, -1, best, population, listener);
            for (int iteration = 0; iteration < config.iterations; iteration++) {
                final int step = iteration;
                final List<Solution> snapshot = Collections.unmodifiableList(new ArrayList<Solution>(population));
                final Solution guide = best;
                final double fraction = iteration / (double) config.iterations;
                final double a = 2.0 - 2.0 * fraction;
                final double pHybrid = Math.max(0.15, 0.5 * (1.0 - fraction));
                final double temperature = 1.0 - fraction;
                List<Callable<Update>> jobs = new ArrayList<Callable<Update>>();
                for (int i = 0; i < snapshot.size(); i++) {
                    final int index = i;
                    jobs.add(() -> update(snapshot.get(index), snapshot, guide, a, pHybrid,
                            temperature, random(1, step, index)));
                }
                List<Update> updates = execute(jobs, pool);
                population = new ArrayList<Solution>();
                for (Update u : updates) {
                    population.add(u.solution);
                    if (u.sho) sho++; else woa++;
                    if (u.worse) worse++;
                    if (evaluator.compare(u.solution, best) < 0) best = u.solution;
                }
                // Exact zero-based condition printed in Algorithm 1, including iteration 0.
                if (iteration % config.localSearchInterval == 0) {
                    best = operators.localSearch(best); localSearchCalls++;
                }
                if (best.vehicles() < stagnationBest.vehicles()
                        || (best.vehicles() == stagnationBest.vehicles()
                            && evaluator.distance(best) < evaluator.distance(stagnationBest) - config.improvementEpsilon)) {
                    stagnationBest = best; noImprove = 0;
                } else if (++noImprove >= config.stagnationIterations) {
                    population = diversify(population, iteration);
                    for (Solution s : population) if (evaluator.compare(s, best) < 0) best = s;
                    stagnationBest = best; noImprove = 0; diversifications++;
                }
                record(history, iteration, best, population, listener);
            }
            if (!evaluator.isFeasible(best)) throw new IllegalStateException("Internal error: final solution is infeasible");
            return new Result(best, history, sho, woa, worse, localSearchCalls, diversifications,
                    (System.nanoTime() - start) / 1e9);
        } finally {
            if (pool != null) pool.shutdownNow();
        }
    }

    private Update update(Solution current, List<Solution> population, Solution best,
                          double a, double pHybrid, double temperature, Random random) {
        boolean sho = random.nextDouble() < pHybrid;
        Solution candidate;
        if (sho) {
            Solution partner = operators.tournament(population, random);
            candidate = operators.crossover(best, partner, current, random);
            if (random.nextDouble() < config.mutationProbability) candidate = operators.mutate(candidate, random);
        } else candidate = operators.woa(current, best, a, random);
        if (!evaluator.isFeasible(candidate)) candidate = repair.repair(candidate);
        if (candidate == null || !evaluator.isFeasible(candidate)) return new Update(current, sho, false);
        int comparison = evaluator.compare(candidate, current);
        boolean accept = comparison < 0 || random.nextDouble() < acceptanceProbability(
                evaluator.fitness(candidate), evaluator.fitness(current), temperature);
        return new Update(accept ? candidate : current, sho, accept && comparison > 0);
    }

    /** Algorithm 2 follows Section 4.2's explicit distance-only initialization objective. */
    private Solution initializeSA(Solution initial, Random random) {
        Solution current = initial, best = initial;
        if (config.initMoves == 0) return initial;
        for (double t = config.initTemperature; t > config.initMinTemperature; t *= config.initCooling) {
            for (int move = 0; move < config.initMoves; move++) {
                Solution next = operators.perturb(current, random);
                if (!evaluator.isFeasible(next)) continue;
                double nf = evaluator.distance(next), cf = evaluator.distance(current);
                if (nf < cf || random.nextDouble() < acceptanceProbability(nf, cf, t)) {
                    current = next;
                    if (nf < evaluator.distance(best)) best = next;
                }
            }
        }
        return best;
    }

    /** Paper leaves S0 undefined: randomized customer-order, best feasible insertion. */
    private Solution construct(Random random) {
        List<Integer> order = new ArrayList<Integer>();
        for (int c = 1; c < evaluator.problem.nodes.length; c++) order.add(c);
        for (int attempt = 0; attempt < config.constructionAttempts; attempt++) {
            Collections.shuffle(order, random);
            if (attempt == 0) order.sort(Comparator.comparingDouble(c -> evaluator.problem.nodes[c].due));
            List<List<Integer>> routes = new ArrayList<List<Integer>>();
            boolean ok = true;
            for (int c : order) if (!repair.insert(routes, c, -1, true)) { ok = false; break; }
            if (ok) {
                Solution candidate = repair.repair(new Solution(routes));
                if (candidate != null) return candidate;
            }
        }
        return null;
    }

    private List<Solution> diversify(List<Solution> population, int iteration) {
        List<Solution> result = new ArrayList<Solution>(population);
        List<Integer> indices = new ArrayList<Integer>();
        for (int i = 0; i < result.size(); i++) indices.add(i);
        indices.sort((i, j) -> evaluator.compare(population.get(j), population.get(i)));
        int count = Math.max(1, (int) Math.ceil(result.size() * config.diversificationFraction));
        for (int k = 0; k < count; k++) {
            int index = indices.get(k);
            Random random = random(2, iteration, index);
            Solution candidate = result.get(index);
            for (int j = 0; j < config.diversificationMoves; j++) candidate = operators.mutate(candidate, random);
            if (candidate.equals(result.get(index))) {
                Solution restart = construct(random);
                if (restart != null) candidate = restart;
            }
            result.set(index, candidate);
        }
        return result;
    }

    public static double acceptanceProbability(double newFitness, double currentFitness, double temperature) {
        if (!Double.isFinite(newFitness) || !Double.isFinite(currentFitness)
                || !Double.isFinite(temperature) || temperature < 0)
            throw new IllegalArgumentException("SA requires finite fitness and nonnegative temperature");
        if (newFitness <= currentFitness) return 1.0;
        return Math.exp(-(newFitness - currentFitness) / (1e-6 + temperature * Math.abs(currentFitness)));
    }

    private Random random(long phase, long iteration, long index) {
        long z = config.seed ^ (phase * 0x9e3779b97f4a7c15L)
                ^ ((iteration + 1) * 0xbf58476d1ce4e5b9L) ^ ((index + 1) * 0x94d049bb133111ebL);
        z = (z ^ (z >>> 30)) * 0xbf58476d1ce4e5b9L;
        z = (z ^ (z >>> 27)) * 0x94d049bb133111ebL;
        return new Random(z ^ (z >>> 31));
    }

    private void record(List<Result.Progress> history, int iteration, Solution best,
                        List<Solution> population, Consumer<Result.Progress> listener) {
        Result.Progress progress = new Result.Progress(iteration, best, evaluator, population);
        history.add(progress); if (listener != null) listener.accept(progress);
    }

    private static final class Update {
        final Solution solution; final boolean sho, worse;
        Update(Solution solution, boolean sho, boolean worse) { this.solution = solution; this.sho = sho; this.worse = worse; }
    }

    private static <T> List<T> execute(List<Callable<T>> jobs, ExecutorService pool) {
        List<T> result = new ArrayList<T>();
        try {
            if (pool == null) for (Callable<T> job : jobs) result.add(job.call());
            else for (Future<T> future : pool.invokeAll(jobs)) result.add(future.get());
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt(); throw new IllegalStateException("Solver interrupted", e);
        } catch (ExecutionException e) { throw new IllegalStateException("Worker failed", e.getCause());
        } catch (Exception e) { throw new IllegalStateException("Solver failed: " + e.getMessage(), e); }
        return result;
    }
}
