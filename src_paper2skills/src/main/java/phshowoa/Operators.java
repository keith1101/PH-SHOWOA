package phshowoa;

import java.util.ArrayList;
import java.util.Collections;
import java.util.HashSet;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Random;
import java.util.Set;

/**
 * Route operators for Algorithms 2 and 4--8 of PH-SHOWOA.
 *
 * <p>Routes contain customers only; the evaluator supplies both depot edges.
 * All changes are made to private copies, so an instance of this class may be
 * shared by workers provided each worker supplies its own {@link Random}.
 * Candidate generation deliberately leaves the acceptance decision to the
 * main algorithm's simulated-annealing gate.</p>
 */
public final class Operators {
    private final Evaluator evaluator;
    private final Repair repair;

    public Operators(Evaluator evaluator, Repair repair) {
        this.evaluator = evaluator;
        this.repair = repair;
    }

    /**
     * Algorithm 2 neighbourhood proposal: choose uniformly among swap,
     * insertion, reversal, Pd-shift and Pd-exchange. An unavailable operation
     * is a no-op. The caller must check feasibility before SA acceptance.
     */
    public Solution perturb(Solution current, Random random) {
        List<List<Integer>> routes = current.mutableRoutes();
        int operation = random.nextInt(5);
        if (operation < 3) {
            int route = pickRoute(routes, 2, random);
            if (route >= 0) {
                intra(routes.get(route), operation, random);
            }
        } else {
            inter(routes, operation - 3, random);
        }
        return solution(routes);
    }

    /** Algorithm 7: equiprobable intra/inter operation, with feasibility rollback. */
    public Solution mutate(Solution current, Random random) {
        if (current.routes.isEmpty()) {
            return current;
        }
        List<List<Integer>> routes = current.mutableRoutes();
        boolean useIntra = random.nextBoolean();
        int route = random.nextInt(routes.size());
        if (useIntra) {
            intra(routes.get(route), random.nextInt(3), random);
        } else if (routes.size() >= 2) {
            inter(routes, random.nextInt(2), random);
        }
        Solution candidate = solution(routes);
        return evaluator.isFeasible(candidate) ? candidate : current;
    }

    /** Tournament selection without replacement, using at most three individuals. */
    public Solution tournament(List<Solution> population, Random random) {
        if (population.isEmpty()) {
            throw new IllegalArgumentException("Tournament population must not be empty");
        }
        int[] indices = new int[population.size()];
        for (int i = 0; i < indices.length; i++) {
            indices[i] = i;
        }
        Solution winner = null;
        for (int i = 0; i < Math.min(3, indices.length); i++) {
            int selected = i + random.nextInt(indices.length - i);
            int temp = indices[i];
            indices[i] = indices[selected];
            indices[selected] = temp;
            Solution contender = population.get(indices[i]);
            if (winner == null || evaluator.compare(contender, winner) < 0) {
                winner = contender;
            }
        }
        return winner;
    }

    /**
     * Algorithm 6: retain one (probability .6) or two randomly selected best
     * routes, then reconstruct the remaining partner/current order without
     * duplicates. Every append is checked against the complete route load and
     * time-window constraints, including return to the depot. This corrects
     * the net-demand-only test in the printed pseudocode. Fleet-limit and
     * coverage violations are passed to repair; an unsuccessful repair rolls
     * back to the current parent.
     */
    public Solution crossover(Solution best, Solution partner, Solution current,
                              Random random) {
        if (best.routes.isEmpty()) {
            return current;
        }
        int take = best.routes.size() == 1 ? 1 : (random.nextDouble() < 0.6 ? 1 : 2);
        List<Integer> indices = new ArrayList<Integer>();
        for (int i = 0; i < best.routes.size(); i++) {
            indices.add(i);
        }
        Collections.shuffle(indices, random);
        List<List<Integer>> routes = new ArrayList<List<Integer>>();
        Set<Integer> kept = new HashSet<Integer>();
        for (int i = 0; i < take; i++) {
            List<Integer> seed = new ArrayList<Integer>(best.routes.get(indices.get(i)));
            routes.add(seed);
            kept.addAll(seed);
        }
        Set<Integer> remaining = new LinkedHashSet<Integer>();
        collectRemaining(partner, kept, remaining);
        collectRemaining(current, kept, remaining);
        List<Integer> route = new ArrayList<Integer>();
        for (Integer customer : remaining) {
            route.add(customer);
            if (route.size() > 1 && !evaluator.isRouteFeasible(route)) {
                route.remove(route.size() - 1);
                routes.add(route);
                route = new ArrayList<Integer>();
                route.add(customer);
            }
        }
        if (!route.isEmpty()) {
            routes.add(route);
        }
        Solution candidate = feasibleOrRepair(solution(routes));
        return candidate == null ? current : candidate;
    }

    /**
     * Algorithm 4 candidate generation with per-route A in [-a,a], C in [0,2].
     *
     * <p>The paper names ENCIRCLING_PREY and SPIRAL_MOVEMENT but does not
     * define their discrete implementation. The explicit mapping here uses
     * only customers shared by the current route and the best route at the
     * same route index. Those customers occupy their original slots, and their
     * target order is their relative order in the best route. Customer IDs
     * are never treated as coordinates and membership is preserved.</p>
     *
     * <p>Encircling performs at most ceil(m*(1-|A|)*C/2) rank insertions,
     * clamped to [1,m-1], where m is the number of shared customers. The sign
     * of A selects which end of the target sequence is aligned first. Spiral
     * relinking uses l=C-1 and ceil(m*min(1,|exp(l)*cos(2*pi*l)|)) insertions,
     * also clamped to [1,m-1]; the sign of l chooses the alignment direction.
     * These are documented implementation choices, not missing formulas
     * claimed to have been reproduced from the paper.</p>
     *
     * <p>When p&lt;.5 and |A|&gt;=1, the paper's bounded random intra/inter
     * operators are used. Each modification is rolled back immediately if
     * infeasible. The final candidate is repaired if necessary, with the
     * original feasible solution as fallback. Objective acceptance belongs to
     * Algorithm 1; no population member or global best is changed here.</p>
     */
    public Solution woa(Solution current, Solution best, double a, Random random) {
        if (!Double.isFinite(a) || a < 0.0 || a > 2.0) {
            throw new IllegalArgumentException("WOA a must be in [0,2]");
        }
        List<List<Integer>> routes = current.mutableRoutes();
        int limit = Math.min(routes.size(), best.routes.size());
        double[] coefficientsA = new double[routes.size()];
        double[] coefficientsC = new double[routes.size()];
        for (int i = 0; i < routes.size(); i++) {
            coefficientsA[i] = 2.0 * a * random.nextDouble() - a;
        }
        for (int i = 0; i < routes.size(); i++) {
            coefficientsC[i] = 2.0 * random.nextDouble();
        }
        for (int i = 0; i < limit; i++) {
            double coefficientA = coefficientsA[i];
            double coefficientC = coefficientsC[i];
            if (random.nextDouble() < 0.5) {
                if (Math.abs(coefficientA) < 1.0) {
                    List<Integer> backup = new ArrayList<Integer>(routes.get(i));
                    relink(routes.get(i), best.routes.get(i),
                            (1.0 - Math.abs(coefficientA)) * coefficientC / 2.0,
                            coefficientA >= 0.0);
                    if (!evaluator.isRouteFeasible(routes.get(i))) {
                        routes.set(i, backup);
                    }
                } else if (random.nextDouble() < 0.5) {
                    List<Integer> backup = new ArrayList<Integer>(routes.get(i));
                    intra(routes.get(i), random.nextInt(3), random);
                    if (!evaluator.isRouteFeasible(routes.get(i))) {
                        routes.set(i, backup);
                    }
                } else {
                    List<List<Integer>> backup = copyRoutes(routes);
                    inter(routes, random.nextInt(2), random);
                    if (!evaluator.isFeasible(solution(routes))) {
                        routes = backup;
                    }
                }
            } else {
                List<Integer> backup = new ArrayList<Integer>(routes.get(i));
                double l = coefficientC - 1.0;
                double fraction = Math.min(1.0,
                        Math.abs(Math.exp(l) * Math.cos(2.0 * Math.PI * l)));
                relink(routes.get(i), best.routes.get(i), fraction, l >= 0.0);
                if (!evaluator.isRouteFeasible(routes.get(i))) {
                    routes.set(i, backup);
                }
            }
        }
        Solution candidate = feasibleOrRepair(solution(routes));
        return candidate == null ? current : candidate;
    }

    /**
     * Algorithm 8. Restart at 2-opt after the first strict improvement in
     * 2-opt, intra/inter relocate, or inter-route swap, in that order. Even an
     * infeasible neighbour is offered to repair before it is rejected.
     */
    public Solution localSearch(Solution initial) {
        Solution current = feasibleOrRepair(initial);
        if (current == null) {
            throw new IllegalArgumentException("Local search requires a feasible or repairable solution");
        }
        while (true) {
            Solution improved = firstTwoOpt(current);
            if (improved == null) {
                improved = firstRelocate(current);
            }
            if (improved == null) {
                improved = firstSwap(current);
            }
            if (improved == null) {
                return current;
            }
            current = improved;
        }
    }

    private Solution firstTwoOpt(Solution current) {
        for (int r = 0; r < current.routes.size(); r++) {
            int size = current.routes.get(r).size();
            for (int first = 0; first < size - 1; first++) {
                for (int last = first + 1; last < size; last++) {
                    List<List<Integer>> routes = current.mutableRoutes();
                    Collections.reverse(routes.get(r).subList(first, last + 1));
                    Solution improved = improving(routes, current);
                    if (improved != null) {
                        return improved;
                    }
                }
            }
        }
        return null;
    }

    private Solution firstRelocate(Solution current) {
        for (int fromRoute = 0; fromRoute < current.routes.size(); fromRoute++) {
            for (int from = 0; from < current.routes.get(fromRoute).size(); from++) {
                for (int toRoute = 0; toRoute < current.routes.size(); toRoute++) {
                    int targetSize = current.routes.get(toRoute).size();
                    for (int to = 0; to <= targetSize; to++) {
                        if (fromRoute == toRoute && (to == from || to == from + 1)) {
                            continue;
                        }
                        List<List<Integer>> routes = current.mutableRoutes();
                        Integer customer = routes.get(fromRoute).remove(from);
                        int position = fromRoute == toRoute && to > from ? to - 1 : to;
                        routes.get(toRoute).add(position, customer);
                        Solution improved = improving(routes, current);
                        if (improved != null) {
                            return improved;
                        }
                    }
                }
            }
        }
        return null;
    }

    private Solution firstSwap(Solution current) {
        for (int left = 0; left < current.routes.size() - 1; left++) {
            for (int right = left + 1; right < current.routes.size(); right++) {
                for (int i = 0; i < current.routes.get(left).size(); i++) {
                    for (int j = 0; j < current.routes.get(right).size(); j++) {
                        List<List<Integer>> routes = current.mutableRoutes();
                        Integer old = routes.get(left).set(i, routes.get(right).get(j));
                        routes.get(right).set(j, old);
                        Solution improved = improving(routes, current);
                        if (improved != null) {
                            return improved;
                        }
                    }
                }
            }
        }
        return null;
    }

    private Solution improving(List<List<Integer>> routes, Solution reference) {
        Solution candidate = feasibleOrRepair(solution(routes));
        return candidate != null && evaluator.compare(candidate, reference) < 0
                ? candidate : null;
    }

    private Solution feasibleOrRepair(Solution candidate) {
        if (evaluator.isFeasible(candidate)) {
            return candidate;
        }
        Solution restored = repair.repair(candidate);
        return restored != null && evaluator.isFeasible(restored) ? restored : null;
    }

    private static void collectRemaining(Solution parent, Set<Integer> kept,
                                         Set<Integer> remaining) {
        for (List<Integer> route : parent.routes) {
            for (Integer customer : route) {
                if (!kept.contains(customer)) {
                    remaining.add(customer);
                }
            }
        }
    }

    private static void intra(List<Integer> route, int operation, Random random) {
        if (route.size() < 2) {
            return;
        }
        int first = random.nextInt(route.size());
        int second = random.nextInt(route.size() - 1);
        if (second >= first) {
            second++;
        }
        if (operation == 0) {
            Collections.swap(route, first, second);
        } else if (operation == 1) {
            Integer customer = route.remove(first);
            route.add(second, customer);
        } else {
            Collections.reverse(route.subList(Math.min(first, second),
                    Math.max(first, second) + 1));
        }
    }

    /** Leave empty route placeholders in place until constructing a Solution. */
    private static void inter(List<List<Integer>> routes, int operation, Random random) {
        if (routes.size() < 2) {
            return;
        }
        int source = pickRoute(routes, 1, random);
        if (source < 0) {
            return;
        }
        int target;
        if (operation == 0) {
            target = random.nextInt(routes.size() - 1);
            if (target >= source) {
                target++;
            }
        } else {
            List<Integer> possible = new ArrayList<Integer>();
            for (int i = 0; i < routes.size(); i++) {
                if (i != source && !routes.get(i).isEmpty()) {
                    possible.add(i);
                }
            }
            if (possible.isEmpty()) {
                return;
            }
            target = possible.get(random.nextInt(possible.size()));
        }
        List<Integer> from = routes.get(source);
        List<Integer> to = routes.get(target);
        int fromPosition = random.nextInt(from.size());
        if (operation == 0) {
            Integer customer = from.remove(fromPosition);
            to.add(random.nextInt(to.size() + 1), customer);
        } else {
            int toPosition = random.nextInt(to.size());
            Integer customer = from.set(fromPosition, to.get(toPosition));
            to.set(toPosition, customer);
        }
    }

    private static int pickRoute(List<List<Integer>> routes, int minimumSize, Random random) {
        List<Integer> eligible = new ArrayList<Integer>();
        for (int i = 0; i < routes.size(); i++) {
            if (routes.get(i).size() >= minimumSize) {
                eligible.add(i);
            }
        }
        return eligible.isEmpty() ? -1 : eligible.get(random.nextInt(eligible.size()));
    }

    private static void relink(List<Integer> route, List<Integer> bestRoute,
                               double fraction, boolean forward) {
        Set<Integer> inRoute = new HashSet<Integer>(route);
        List<Integer> target = new ArrayList<Integer>();
        for (Integer customer : bestRoute) {
            if (inRoute.contains(customer)) {
                target.add(customer);
            }
        }
        if (target.size() < 2) {
            return;
        }
        Set<Integer> shared = new HashSet<Integer>(target);
        List<Integer> slots = new ArrayList<Integer>();
        List<Integer> order = new ArrayList<Integer>();
        for (int i = 0; i < route.size(); i++) {
            if (shared.contains(route.get(i))) {
                slots.add(i);
                order.add(route.get(i));
            }
        }
        int steps = Math.min(target.size() - 1,
                Math.max(1, (int) Math.ceil(target.size() * fraction)));
        int changed = 0;
        for (int offset = 0; offset < target.size() && changed < steps; offset++) {
            int position = forward ? offset : target.size() - 1 - offset;
            Integer wanted = target.get(position);
            if (!wanted.equals(order.get(position))) {
                order.remove(order.indexOf(wanted));
                order.add(position, wanted);
                changed++;
            }
        }
        for (int i = 0; i < slots.size(); i++) {
            route.set(slots.get(i), order.get(i));
        }
    }

    private static List<List<Integer>> copyRoutes(List<List<Integer>> routes) {
        List<List<Integer>> copy = new ArrayList<List<Integer>>();
        for (List<Integer> route : routes) {
            copy.add(new ArrayList<Integer>(route));
        }
        return copy;
    }

    private static Solution solution(List<List<Integer>> routes) {
        List<List<Integer>> nonempty = new ArrayList<List<Integer>>();
        for (List<Integer> route : routes) {
            if (!route.isEmpty()) {
                nonempty.add(route);
            }
        }
        return new Solution(nonempty);
    }
}
