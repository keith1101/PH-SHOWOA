package phshowoa;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

/** Algorithm 10: bounded repair on a copy; null explicitly means failure. */
public final class Repair {
    private final Evaluator evaluator;
    public Repair(Evaluator evaluator) { this.evaluator = evaluator; }

    public Solution repair(Solution input) {
        if (evaluator.isFeasible(input)) return input;
        if (input == null) return null;
        List<List<Integer>> routes = input.mutableRoutes();
        int n = evaluator.problem.nodes.length;
        for (List<Integer> route : routes)
            for (Integer c : route) if (c == null || c <= 0 || c >= n) return null;
        // Keep the duplicate occurrence with the least marginal insertion distance.
        for (int c = 1; c < n; c++) {
            int bestR = -1, bestP = -1;
            double bestCost = Double.POSITIVE_INFINITY;
            for (int r = 0; r < routes.size(); r++) {
                List<Integer> route = routes.get(r);
                for (int p = 0; p < route.size(); p++) if (route.get(p) == c) {
                    int prev = p == 0 ? 0 : route.get(p - 1);
                    int next = p + 1 == route.size() ? 0 : route.get(p + 1);
                    double cost = evaluator.problem.distance[prev][c] + evaluator.problem.distance[c][next]
                            - evaluator.problem.distance[prev][next];
                    if (cost < bestCost) { bestCost = cost; bestR = r; bestP = p; }
                }
            }
            for (int r = routes.size() - 1; r >= 0; r--)
                for (int p = routes.get(r).size() - 1; p >= 0; p--)
                    if (routes.get(r).get(p) == c && !(r == bestR && p == bestP)) routes.get(r).remove(p);
        }
        removeEmpty(routes);
        boolean[] seen = new boolean[n];
        for (List<Integer> r : routes) for (int c : r) seen[c] = true;
        for (int c = 1; c < n; c++) if (!seen[c] && !insert(routes, c, -1, true)) return null;

        // Capacity and time repair. Every iteration removes one offending customer
        // and inserts into a fully feasible route (or singleton). Time repair may
        // reorder the source route; capacity repair must choose another route.
        // The explicit bound prevents cycling on impossible directed instances.
        int limit = Math.max(1, 4 * n);
        for (int step = 0; step < limit; step++) {
            int bad = -1;
            Evaluator.RouteCheck state = null;
            for (int r = 0; r < routes.size(); r++) {
                Evaluator.RouteCheck check = evaluator.checkRoute(routes.get(r));
                if (!check.feasible) { bad = r; state = check; break; }
            }
            if (bad < 0) break;
            List<Integer> route = routes.get(bad);
            int chosen = 0;
            if (!state.capacityFeasible) {
                double maximum = -1;
                for (int p = 0; p < route.size(); p++) {
                    Node c = evaluator.problem.nodes[route.get(p)];
                    double delta = Math.abs(c.delivery - c.pickup);
                    if (delta > maximum) { maximum = delta; chosen = p; }
                }
            } else if (state.lateCustomer > 0) {
                chosen = route.indexOf(state.lateCustomer);
            } else chosen = route.size() - 1; // depot return violation
            int customer = route.remove(chosen);
            boolean inserted = state.capacityFeasible
                    ? insertByArrival(routes, customer)
                    : insert(routes, customer, bad, true);
            if (!inserted) return null;
            removeEmpty(routes);
        }
        for (List<Integer> route : routes) if (!evaluator.isRouteFeasible(route)) return null;

        // Algorithm 10's new-route fallback may exceed J; enforce Eq.1 before return.
        while (routes.size() > evaluator.problem.vehicles) {
            List<List<Integer>> reduced = null;
            for (int r = 0; r < routes.size(); r++) {
                List<List<Integer>> trial = copy(routes);
                List<Integer> removed = trial.remove(r);
                boolean ok = true;
                for (int c : removed) if (!insert(trial, c, -1, false)) { ok = false; break; }
                if (ok) { reduced = trial; break; }
            }
            if (reduced == null) return null;
            routes = reduced;
        }
        // Step 4: first-improvement intra-route 2-opt, strictly decreasing distance.
        for (int r = 0; r < routes.size(); r++) {
            List<Integer> route = routes.get(r);
            boolean improved = true;
            while (improved) {
                improved = false;
                double old = evaluator.routeDistance(route);
                search: for (int i = 0; i < route.size(); i++) for (int j = i + 1; j < route.size(); j++) {
                    List<Integer> trial = new ArrayList<Integer>(route);
                    Collections.reverse(trial.subList(i, j + 1));
                    if (evaluator.isRouteFeasible(trial) && evaluator.routeDistance(trial) < old - Evaluator.EPS) {
                        route = trial; improved = true; break search;
                    }
                }
            }
            routes.set(r, route);
        }
        Solution result = new Solution(routes);
        return evaluator.isFeasible(result) ? result : null;
    }

    /** Best feasible insertion; temporary fleet overflow is validated by repair's final phase. */
    public boolean insert(List<List<Integer>> routes, int customer, int excluded, boolean allowNew) {
        return insert(routes, customer, excluded, allowNew, false);
    }

    private boolean insertByArrival(List<List<Integer>> routes, int customer) {
        return insert(routes, customer, -1, true, true);
    }

    private boolean insert(List<List<Integer>> routes, int customer, int excluded,
                           boolean allowNew, boolean earliestArrival) {
        double best = Double.POSITIVE_INFINITY;
        double bestDistance = Double.POSITIVE_INFINITY;
        int bestRoute = -1, bestPosition = -1;
        for (int r = 0; r < routes.size(); r++) {
            if (r == excluded) continue;
            List<Integer> route = routes.get(r);
            double old = evaluator.routeDistance(route);
            for (int p = 0; p <= route.size(); p++) {
                List<Integer> trial = new ArrayList<Integer>(route);
                trial.add(p, customer);
                if (evaluator.isRouteFeasible(trial)) {
                    double delta = evaluator.routeDistance(trial) - old;
                    double cost = earliestArrival ? serviceStart(trial, p) : delta;
                    if (cost < best || (cost == best && delta < bestDistance)) {
                        best = cost; bestDistance = delta; bestRoute = r; bestPosition = p;
                    }
                }
            }
        }
        if (bestRoute >= 0) { routes.get(bestRoute).add(bestPosition, customer); return true; }
        List<Integer> singleton = new ArrayList<Integer>(Collections.singletonList(customer));
        if (allowNew && evaluator.isRouteFeasible(singleton)) { routes.add(singleton); return true; }
        return false;
    }

    private double serviceStart(List<Integer> route, int position) {
        double time = evaluator.problem.nodes[0].ready;
        int previous = 0;
        for (int p = 0; p <= position; p++) {
            int customer = route.get(p);
            Node node = evaluator.problem.nodes[customer];
            time = Math.max(time + evaluator.problem.travelTime[previous][customer], node.ready);
            if (p == position) return time;
            time += node.service;
            previous = customer;
        }
        throw new IllegalArgumentException("Invalid insertion position");
    }

    private static void removeEmpty(List<List<Integer>> routes) { routes.removeIf(List::isEmpty); }
    private static List<List<Integer>> copy(List<List<Integer>> routes) {
        List<List<Integer>> result = new ArrayList<List<Integer>>();
        for (List<Integer> route : routes) result.add(new ArrayList<Integer>(route));
        return result;
    }
}
