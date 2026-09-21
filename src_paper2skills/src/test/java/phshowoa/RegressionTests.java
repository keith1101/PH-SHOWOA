package phshowoa;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashSet;
import java.util.List;
import java.util.Random;
import java.util.Set;

/** Dependency-free executable regressions. Assertions do not require java -ea. */
public final class RegressionTests {
    private static int passed;
    private static final List<String> failures = new ArrayList<String>();

    private interface TestCase {
        void run() throws Exception;
    }

    private RegressionTests() { }

    public static void main(String[] args) throws Exception {
        run("initial delivery load", RegressionTests::initialDeliveryLoad);
        run("intermediate pickup overload", RegressionTests::intermediatePickupOverload);
        run("final customer pickup", RegressionTests::finalPickupOverload);
        run("waiting and service propagation", RegressionTests::waitingAndService);
        run("depot departure and return bounds", RegressionTests::depotBounds);
        run("fleet and exactly-once coverage", RegressionTests::fleetAndCoverage);
        run("asymmetric distance and independent travel time", RegressionTests::asymmetricMetrics);
        run("strict vehicle-first objective", RegressionTests::lexicographicPriority);
        run("zero monetary distance cost retains search objective", RegressionTests::zeroMonetaryDistanceCost);
        run("solution copy isolation", RegressionTests::solutionIsolation);
        run("repair duplicate and missing visits", RegressionTests::repairCoverage);
        run("repair failure preserves input", RegressionTests::repairFailure);
        run("time repair prefers earliest service and source reordering", RegressionTests::repairByEarliestService);
        run("EXPLICIT parser preserves directed distance and time", RegressionTests::explicitParser);
        run("Wang-Chen text parser", RegressionTests::wangChenParser);
        run("malformed explicit matrix rejected", RegressionTests::invalidExplicitParser);
        run("normalized annealing acceptance", RegressionTests::annealingAcceptance);
        run("floating-point cooling stall rejected", RegressionTests::coolingStall);
        run("route operators preserve coverage and parents", RegressionTests::operatorInvariants);
        run("stagnation diversification and zero-based cadence", RegressionTests::stagnationCadence);
        run("serial and parallel deterministic evolution", RegressionTests::deterministicEvolution);
        System.out.println("Regression tests: " + passed + " passed, " + failures.size() + " failed.");
        if (!failures.isEmpty()) {
            throw new AssertionError("Regression failures: " + failures);
        }
    }

    private static void run(String name, TestCase test) {
        try {
            test.run();
            passed++;
            System.out.println("PASS " + name);
        } catch (Throwable failure) {
            failures.add(name + ": " + failure);
            System.err.println("FAIL " + name);
            failure.printStackTrace(System.err);
        }
    }

    private static void initialDeliveryLoad() {
        Fixture f = new Fixture(2, 10, depot(), node(6, 0), node(6, 0));
        Evaluator e = new Evaluator(f.problem());
        check(!e.isFeasible(Solution.of(new int[] {1, 2})),
                "Vehicles must carry every route delivery when leaving the depot.");
        check(e.isFeasible(Solution.of(new int[] {1}, new int[] {2})),
                "Splitting an overloaded delivery route should restore capacity.");
    }

    private static void intermediatePickupOverload() {
        Fixture f = new Fixture(1, 10, depot(), node(1, 8), node(8, 1));
        Evaluator e = new Evaluator(f.problem());
        check(!e.isRouteFeasible(Arrays.asList(1, 2)),
                "Initial and final load 9 do not make an intermediate load 16 feasible.");
        check(e.isRouteFeasible(Arrays.asList(2, 1)),
                "Delivering first should keep every intermediate load within capacity.");
    }

    private static void finalPickupOverload() {
        Fixture f = new Fixture(1, 10, depot(), node(0, 11));
        Evaluator e = new Evaluator(f.problem());
        check(!e.isFeasible(Solution.of(new int[] {1})),
                "The pickup at the final customer must be checked before depot return.");
    }

    private static void waitingAndService() {
        Fixture wait = new Fixture(1, 10, depot(), timedNode(1, 1, 20, 25, 2));
        Evaluator e = new Evaluator(wait.problem());
        check(e.isFeasible(Solution.of(new int[] {1})),
                "Arrival before ready time is allowed when the vehicle waits.");
        Fixture delayed = new Fixture(1, 10, depot(),
                timedNode(1, 1, 20, 25, 2), timedNode(1, 1, 0, 21, 0));
        check(!new Evaluator(delayed.problem()).isFeasible(Solution.of(new int[] {1, 2})),
                "Waiting plus service at customer 1 makes customer 2 late.");
    }

    private static void depotBounds() {
        Fixture lateDeparture = new Fixture(1, 10,
                timedNode(0, 0, 5, 100, 0), timedNode(1, 0, 0, 5, 0));
        check(!new Evaluator(lateDeparture.problem()).isFeasible(Solution.of(new int[] {1})),
                "Travel must start at the depot earliest departure, not time zero.");
        Fixture lateReturn = new Fixture(1, 10,
                timedNode(0, 0, 0, 5, 0), node(1, 0));
        lateReturn.time[1][0] = 5;
        check(!new Evaluator(lateReturn.problem()).isFeasible(Solution.of(new int[] {1})),
                "A feasible customer visit cannot excuse a late depot return.");
        lateReturn.time[1][0] = 4;
        check(new Evaluator(lateReturn.problem()).isFeasible(Solution.of(new int[] {1})),
                "Returning exactly at the depot deadline is feasible.");
    }

    private static void fleetAndCoverage() {
        Fixture f = new Fixture(1, 10, depot(), node(1, 0), node(1, 0));
        Evaluator e = new Evaluator(f.problem());
        check(!e.isFeasible(Solution.of(new int[] {1}, new int[] {2})),
                "Route count must not exceed the available fleet.");
        check(!e.isFeasible(Solution.of(new int[] {1, 1, 2})),
                "Duplicate customer visits must be rejected.");
        check(!e.isFeasible(Solution.of(new int[] {1})),
                "Missing customer visits must be rejected.");
        check(e.isFeasible(Solution.of(new int[] {1, 2})), "Complete route should be feasible.");
    }

    private static void asymmetricMetrics() {
        Fixture f = new Fixture(1, 10, depot(), node(1, 0), node(1, 0));
        f.distance[0][1] = 2;
        f.distance[1][2] = 3;
        f.distance[2][0] = 5;
        f.distance[0][2] = 7;
        f.distance[2][1] = 11;
        f.distance[1][0] = 13;
        Evaluator e = new Evaluator(f.problem());
        near(10, e.distance(Solution.of(new int[] {1, 2})), "Forward directed route distance");
        near(31, e.distance(Solution.of(new int[] {2, 1})), "Reverse directed route distance");
        f.nodes[1][3] = 5;
        f.time[0][1] = 6;
        Evaluator delayed = new Evaluator(f.problem());
        check(!delayed.isFeasible(Solution.of(new int[] {1, 2})),
                "Time-window validation must use travel time, independently of distance.");
        near(10, delayed.distance(Solution.of(new int[] {1, 2})),
                "Changing travel time must not change travel distance");
    }

    private static void lexicographicPriority() {
        Fixture f = new Fixture(2, 10, depot(), node(1, 0), node(1, 0));
        f.distance[1][2] = 100000;
        Evaluator e = new Evaluator(f.problem());
        Solution fewer = Solution.of(new int[] {1, 2});
        Solution shorter = Solution.of(new int[] {1}, new int[] {2});
        check(e.isFeasible(fewer) && e.isFeasible(shorter), "Objective comparison needs feasible routes.");
        check(e.compare(fewer, shorter) < 0,
                "One vehicle must beat two even when its distance exceeds the fixed dispatch cost.");
        check(e.fitness(fewer) < e.fitness(shorter),
                "Scalar acceptance fitness must preserve the same vehicle-first ordering.");
        check(e.compare(Solution.of(new int[] {2, 1}), fewer) < 0,
                "Among equal fleets the smaller distance must win.");
    }

    private static void zeroMonetaryDistanceCost() {
        Fixture f = new Fixture(2, 10, depot(), node(1, 0), node(1, 0));
        f.unitCost = 0;
        f.distance[1][2] = 30;
        Evaluator e = new Evaluator(f.problem());
        Solution longer = Solution.of(new int[] {1, 2});
        Solution shorter = Solution.of(new int[] {2, 1});
        check(e.compare(shorter, longer) < 0 && e.fitness(shorter) < e.fitness(longer),
                "A zero monetary unit cost must not erase secondary-distance search ordering.");
        near(e.operationalCost(shorter), e.operationalCost(longer),
                "Monetary reporting must still honor the actual zero unit cost");
        check(Solver.acceptanceProbability(e.fitness(longer), e.fitness(shorter), 0) < 1,
                "Distance-worsening moves must not be mistaken for equal-fitness moves.");
    }

    private static void solutionIsolation() {
        int[] originalRoute = new int[] {1, 2};
        Solution original = Solution.of(originalRoute);
        originalRoute[0] = 2;
        check(original.mutableRoutes().get(0).equals(Arrays.asList(1, 2)),
                "Solution.of must own a copy of the caller's route array.");
        List<List<Integer>> exported = original.mutableRoutes();
        exported.get(0).set(0, 2);
        exported.add(new ArrayList<Integer>(Arrays.asList(3)));
        check(original.vehicles() == 1 && original.mutableRoutes().get(0).equals(Arrays.asList(1, 2)),
                "Mutable route exports must not alias the immutable solution.");
    }

    private static void repairCoverage() {
        Fixture f = new Fixture(3, 10, depot(), node(1, 0), node(1, 0), node(1, 0));
        Evaluator e = new Evaluator(f.problem());
        Solution damaged = Solution.of(new int[] {1, 1}, new int[] {2});
        List<List<Integer>> snapshot = damaged.mutableRoutes();
        Solution repaired = new Repair(e).repair(damaged);
        check(repaired != null && e.isFeasible(repaired),
                "Repair should remove duplicates and insert the missing customer.");
        check(damaged.mutableRoutes().equals(snapshot), "Successful repair must preserve the input.");
        independentAudit(f, repaired, e);
    }

    private static void repairFailure() {
        Fixture impossible = new Fixture(1, 10, depot(), node(0, 11));
        Evaluator e = new Evaluator(impossible.problem());
        Solution source = Solution.of(new int[] {1});
        List<List<Integer>> snapshot = source.mutableRoutes();
        check(new Repair(e).repair(source) == null,
                "Repair must report failure for a customer whose pickup alone exceeds capacity.");
        check(source.mutableRoutes().equals(snapshot), "Failed repair must preserve the input.");
        Fixture fleet = new Fixture(1, 10, depot(), node(6, 0), node(6, 0));
        Evaluator fleetEvaluator = new Evaluator(fleet.problem());
        Solution tooMany = Solution.of(new int[] {1}, new int[] {2});
        check(new Repair(fleetEvaluator).repair(tooMany) == null,
                "Repair must not return extra singleton routes beyond the available fleet.");
    }

    private static void repairByEarliestService() {
        Fixture f = new Fixture(2, 10, depot(), timedNode(1, 0, 0, 1000, 10),
                timedNode(1, 0, 0, 1, 0), timedNode(1, 0, 0, 5, 0));
        // Customer 3 can start at time 1 by preceding 1 in its source route,
        // or at time 2 after customer 2 in the other route. The latter costs less.
        f.distance[0][3] = 100;
        Evaluator e = new Evaluator(f.problem());
        Solution late = Solution.of(new int[] {1, 3}, new int[] {2});
        check(!e.isFeasible(late), "The regression source must violate customer 3's deadline.");
        Solution restored = new Repair(e).repair(late);
        check(restored != null, "Time repair must find an available feasible reinsertion.");
        independentAudit(f, restored, e);
        check(restored.mutableRoutes().contains(Arrays.asList(3, 1)),
                "Time repair must permit source-route reordering and prefer earliest service over distance.");
        check(late.mutableRoutes().equals(Arrays.asList(Arrays.asList(1, 3), Arrays.asList(2))),
                "Time repair must leave its input unchanged.");
    }

    private static void explicitParser() throws IOException {
        Path path = Files.createTempFile("phshowoa-explicit-", ".vrpsdptw");
        try {
            Files.write(path, explicitText().getBytes(StandardCharsets.UTF_8));
            Problem problem = InstanceReader.read(path);
            Evaluator evaluator = new Evaluator(problem);
            Solution route = Solution.of(new int[] {1, 2});
            near(10, evaluator.distance(route), "Parsed directed distances");
            check(evaluator.isFeasible(route), "Declared depot and arbitrary customer IDs must map correctly.");
            near(31, evaluator.distance(Solution.of(new int[] {2, 1})), "Parsed reverse distances");
        } finally {
            Files.deleteIfExists(path);
        }
    }

    private static void wangChenParser() throws IOException {
        String text = "regression-wc\n\nCUSTOMER VEHICLE\n"
                + "NUMBER NUMBER CAPACITY\n2 2 10\n\nCUSTOMER\n"
                + "CUST NO. XCOORD. YCOORD. DDEMAND PDEMAND READY TIME DUE DATE SERVICE TIME\n"
                + "0 0 0 0 0 0 1000 0\n"
                + "10 3 0 4 1 0 1000 0\n"
                + "20 3 4 2 3 0 1000 0\n";
        Path path = Files.createTempFile("phshowoa-wc-", ".txt");
        try {
            Files.write(path, text.getBytes(StandardCharsets.UTF_8));
            Evaluator evaluator = new Evaluator(InstanceReader.read(path));
            Solution route = Solution.of(new int[] {1, 2});
            near(12, evaluator.distance(route), "Unrounded Euclidean WC distances");
            check(evaluator.isFeasible(route), "WC customer row fields must parse in DDEMAND/PDEMAND order.");
        } finally {
            Files.deleteIfExists(path);
        }
    }

    private static void invalidExplicitParser() throws IOException {
        Path path = Files.createTempFile("phshowoa-invalid-", ".vrpsdptw");
        try {
            Files.write(path, explicitText().replace("90 70 11 1\n", "").getBytes(StandardCharsets.UTF_8));
            boolean rejected = false;
            try {
                InstanceReader.read(path);
            } catch (IOException expected) {
                rejected = true;
            }
            check(rejected, "An absent directed edge must not silently become zero distance.");
        } finally {
            Files.deleteIfExists(path);
        }
    }

    private static String explicitText() {
        return "NAME : regression-explicit\nTYPE : VRPSDPTW\nDIMENSION : 3\n"
                + "VEHICLES : 2\nDISPATCHINGCOST : 2000\nUNITCOST : 1\n"
                + "CAPACITY : 10\nEDGE_WEIGHT_TYPE : EXPLICIT\nNODE_SECTION\n"
                + "50 0 0 0 1000 0\n70 4 1 0 1000 0\n90 2 3 0 1000 0\n"
                + "DISTANCETIME_SECTION\n50 70 2 1\n70 90 3 1\n90 50 5 1\n"
                + "50 90 7 1\n90 70 11 1\n70 50 13 1\nDEPOT_SECTION\n50\n-1\nEOF\n";
    }

    private static void annealingAcceptance() {
        near(1, Solver.acceptanceProbability(99, 100, 0), "Improving moves always accepted");
        near(1, Solver.acceptanceProbability(100, 100, 0), "Equal-cost moves accepted");
        near(Math.exp(-10 / (1e-6 + 0.5 * 100)), Solver.acceptanceProbability(110, 100, 0.5),
                "Algorithm 1 normalized Boltzmann formula");
        double warm = Solver.acceptanceProbability(110, 100, 1);
        double cold = Solver.acceptanceProbability(110, 100, 0.01);
        check(warm > cold && warm < 1 && cold > 0,
                "Cooling must reduce, but not reverse, inferior-move acceptance probability.");
        near(0, Solver.acceptanceProbability(1, 0, 0), "Zero fitness/temperature stabilized acceptance");
    }

    private static void coolingStall() {
        Config stalled = config(1);
        stalled.initTemperature = 1e-323;
        stalled.initMinTemperature = Double.MIN_VALUE;
        stalled.initCooling = 0.9;
        stalled.initMoves = 1;
        boolean rejected = false;
        try {
            stalled.validate();
        } catch (IllegalArgumentException expected) {
            rejected = true;
        }
        check(rejected, "A cooling factor that rounds back to the same temperature must fail validation.");
        stalled.initCooling = 0.5;
        stalled.validate(); // A subnormal schedule that really reaches Tmin is valid.
    }

    private static void operatorInvariants() {
        Fixture f = new Fixture(6, 100, depot(), node(2, 1), node(2, 1), node(2, 1),
                node(2, 1), node(2, 1), node(2, 1));
        Evaluator e = new Evaluator(f.problem());
        Operators operators = new Operators(e, new Repair(e));
        Solution current = Solution.of(new int[] {3, 2, 1}, new int[] {6, 5, 4});
        Solution best = Solution.of(new int[] {1, 2, 3}, new int[] {4, 5, 6});
        Solution partner = Solution.of(new int[] {6, 4}, new int[] {3, 1}, new int[] {5, 2});
        List<List<Integer>> currentSnapshot = current.mutableRoutes();
        List<List<Integer>> bestSnapshot = best.mutableRoutes();
        List<List<Integer>> partnerSnapshot = partner.mutableRoutes();
        Set<Solution> proposals = new HashSet<Solution>();
        for (int seed = 0; seed < 40; seed++) {
            Solution perturbed = operators.perturb(current, new Random(seed));
            // This fixture has generous capacity/time bounds: every permutation is feasible.
            independentAudit(f, perturbed, e);
            proposals.add(perturbed);
            independentAudit(f, operators.mutate(current, new Random(seed)), e);
            independentAudit(f, operators.crossover(best, partner, current, new Random(seed)), e);
            for (double a : new double[] {0, 1, 2}) {
                independentAudit(f, operators.woa(current, best, a, new Random(seed)), e);
            }
            check(current.mutableRoutes().equals(currentSnapshot)
                            && best.mutableRoutes().equals(bestSnapshot)
                            && partner.mutableRoutes().equals(partnerSnapshot),
                    "Perturbation, mutation, crossover, and WOA must preserve every parent.");
        }
        check(proposals.size() > 1, "Neighbourhood proposals must exercise actual route changes.");
        Solution oneVehicle = Solution.of(new int[] {1, 2, 3, 4, 5, 6});
        check(operators.tournament(Arrays.asList(current, partner, oneVehicle), new Random(42)).equals(oneVehicle),
                "A three-member tournament must prefer fewer vehicles.");
        Solution redundant = Solution.of(new int[] {1}, new int[] {2}, new int[] {3, 4, 5, 6});
        List<List<Integer>> redundantSnapshot = redundant.mutableRoutes();
        Solution improved = operators.localSearch(redundant);
        independentAudit(f, improved, e);
        check(improved.vehicles() < redundant.vehicles() && e.compare(improved, redundant) < 0,
                "Combined local search must remove redundant singleton routes by improving relocations.");
        check(redundant.mutableRoutes().equals(redundantSnapshot), "Local search must preserve its source solution.");
    }

    private static void stagnationCadence() {
        Fixture f = new Fixture(1, 10, depot(), node(1, 1));
        Config config = config(1);
        config.iterations = 51;
        config.populationSize = 1;
        config.initMoves = 0;
        Result result = new Solver(f.problem(), config).solve();
        independentAudit(f, result.best, new Evaluator(f.problem()));
        check(result.diversifications == 1,
                "A constant objective must diversify once after 50 non-improving iterations.");
        check(result.localSearchCalls == 3,
                "Zero-based local-search cadence must include iterations 0, 25, and 50.");
        check(result.saWorseAccepted == 0, "Identical single-customer routes are not inferior SA moves.");
    }

    private static void deterministicEvolution() {
        Fixture f = new Fixture(3, 7, depot(), node(2, 1), node(2, 3), node(2, 2),
                node(2, 1), node(2, 3), node(2, 2));
        double[][] points = {{0, 0}, {2, 0}, {4, 1}, {4, 4}, {1, 5}, {-2, 3}, {-2, 0}};
        for (int i = 0; i < points.length; i++) {
            for (int j = 0; j < points.length; j++) {
                f.distance[i][j] = Math.hypot(points[i][0] - points[j][0], points[i][1] - points[j][1]);
                f.time[i][j] = f.distance[i][j];
            }
        }
        Config serialConfig = config(1);
        Config parallelConfig = config(2);
        Result serial = new Solver(f.problem(), serialConfig).solve();
        Result parallel = new Solver(f.problem(), parallelConfig).solve();
        Evaluator e = new Evaluator(f.problem());
        independentAudit(f, serial.best, e);
        independentAudit(f, parallel.best, e);
        check(serial.best.mutableRoutes().equals(parallel.best.mutableRoutes()),
                "Fixed seeds must produce the same route output for one and two workers.");
        near(e.distance(serial.best), e.distance(parallel.best), "Worker-count deterministic distance");
        check(serial.shoUpdates == parallel.shoUpdates && serial.woaUpdates == parallel.woaUpdates,
                "Parallel scheduling must not change the operator random streams.");
        check(serial.saWorseAccepted == parallel.saWorseAccepted,
                "Parallel scheduling must not change SA acceptance decisions.");
        check(serial.saWorseAccepted > 0,
                "Feasible inferior candidates must reach Algorithm 1's SA gate and sometimes be accepted.");
        check(serial.shoUpdates > 0 && serial.woaUpdates > 0,
                "The integration run must exercise both hybrid operators.");
        check(serial.shoUpdates + serial.woaUpdates == (long) serialConfig.iterations * serialConfig.populationSize,
                "Every individual must receive exactly one hybrid update per iteration.");
        check(serial.localSearchCalls == 2,
                "Algorithm 1 local search must run at zero-based iterations 0 and 25.");
        check(serial.history.size() == serialConfig.iterations + 1,
                "History must include initialization and every completed iteration.");
        check(serial.history.size() == parallel.history.size(), "Parallel history length must match.");
        for (int i = 0; i < serial.history.size(); i++) {
            Result.Progress current = serial.history.get(i);
            Result.Progress other = parallel.history.get(i);
            check(current.iteration == i - 1, "History iteration indices must be sequential from -1.");
            check(current.vehicles == other.vehicles && current.distinctSolutions == other.distinctSolutions,
                    "Worker scheduling must preserve each generation's best fleet and population diversity.");
            near(current.distance, other.distance, "Worker-count deterministic convergence history");
            if (i > 0) {
                Result.Progress previous = serial.history.get(i - 1);
                check(current.vehicles < previous.vehicles
                                || (current.vehicles == previous.vehicles && current.distance <= previous.distance + 1e-9),
                        "Best-so-far must never regress despite accepting worse population candidates.");
            }
        }
    }

    private static Config config(int workers) {
        Config config = new Config();
        config.iterations = 35;
        config.populationSize = 6;
        config.workers = workers;
        config.seed = 20260905L;
        config.initMoves = 3;
        return config;
    }

    /** Independent physical checker uses raw fixture arrays, not Evaluator feasibility. */
    private static void independentAudit(Fixture f, Solution solution, Evaluator evaluator) {
        check(solution != null, "Solver returned no solution.");
        List<List<Integer>> routes = solution.mutableRoutes();
        check(routes.size() <= f.vehicles, "Independent check: fleet bound.");
        boolean[] visited = new boolean[f.nodes.length];
        double totalDistance = 0;
        for (List<Integer> route : routes) {
            check(!route.isEmpty(), "Independent check: no empty active routes.");
            double load = 0;
            for (int customer : route) {
                check(customer > 0 && customer < f.nodes.length, "Independent check: customer index.");
                load += f.nodes[customer][0];
            }
            check(load <= f.capacity + 1e-9, "Independent check: initial delivery load.");
            double time = f.nodes[0][2];
            int previous = 0;
            for (int customer : route) {
                check(!visited[customer], "Independent check: duplicate visit.");
                visited[customer] = true;
                totalDistance += f.distance[previous][customer];
                time = Math.max(time + f.time[previous][customer], f.nodes[customer][2]);
                check(time <= f.nodes[customer][3] + 1e-9, "Independent check: service start time window.");
                time += f.nodes[customer][4];
                load = load - f.nodes[customer][0] + f.nodes[customer][1];
                check(load >= -1e-9 && load <= f.capacity + 1e-9,
                        "Independent check: post-service load, including last pickup.");
                previous = customer;
            }
            totalDistance += f.distance[previous][0];
            time += f.time[previous][0];
            check(time <= f.nodes[0][3] + 1e-9, "Independent check: depot return deadline.");
        }
        for (int customer = 1; customer < visited.length; customer++) {
            check(visited[customer], "Independent check: missing customer " + customer);
        }
        near(totalDistance, evaluator.distance(solution), "Independent travel-distance sum");
    }

    private static double[] depot() {
        return timedNode(0, 0, 0, 1000, 0);
    }

    private static double[] node(double delivery, double pickup) {
        return timedNode(delivery, pickup, 0, 1000, 0);
    }

    private static double[] timedNode(double delivery, double pickup, double ready, double due, double service) {
        return new double[] {delivery, pickup, ready, due, service};
    }

    private static void check(boolean condition, String message) {
        if (!condition) {
            throw new AssertionError(message);
        }
    }

    private static void near(double expected, double actual, String message) {
        if (!Double.isFinite(actual) || Math.abs(expected - actual) > 1e-8 * Math.max(1, Math.abs(expected))) {
            throw new AssertionError(message + ": expected " + expected + ", got " + actual);
        }
    }

    private static final class Fixture {
        final int vehicles;
        final double capacity;
        final double[][] nodes;
        final double[][] distance;
        final double[][] time;
        double unitCost = 1;

        Fixture(int vehicles, double capacity, double[]... nodes) {
            this.vehicles = vehicles;
            this.capacity = capacity;
            this.nodes = nodes;
            distance = new double[nodes.length][nodes.length];
            time = new double[nodes.length][nodes.length];
            for (int i = 0; i < nodes.length; i++) {
                for (int j = 0; j < nodes.length; j++) {
                    distance[i][j] = i == j ? 0 : 1;
                    time[i][j] = distance[i][j];
                }
            }
        }

        Problem problem() {
            Node[] customers = new Node[nodes.length];
            for (int i = 0; i < nodes.length; i++) {
                double[] n = nodes[i];
                customers[i] = new Node(i, n[0], n[1], n[2], n[3], n[4]);
            }
            return new Problem("regression", customers, distance, time, vehicles, capacity, 2000, unitCost);
        }
    }
}
