package phshowoa;

import java.util.List;

/** Section 3 equations (1)-(11); corrects Algorithm 9's reversed load convention. */
public final class Evaluator {
    public static final double EPS = 1e-9;
    public final Problem problem;
    public final double vehicleWeight;
    public final double distanceWeight;

    public Evaluator(Problem problem) {
        this.problem = problem;
        // A zero monetary unit cost must not erase the distance objective.
        distanceWeight = problem.unitCost > 0.0 ? problem.unitCost : 1.0;
        double largest = 0;
        for (double[] row : problem.distance) for (double d : row) largest = Math.max(largest, d);
        int n = problem.nodes.length - 1;
        // A feasible solution has n+K arcs, K <= min(n,J). This is a safe TD bound
        // for directed, nonmetric matrices too. Do not mistake dataset cost for priority.
        double bound = (n + (double) Math.min(n, problem.vehicles)) * largest * distanceWeight;
        vehicleWeight = Math.max(problem.dispatchCost, Math.nextUp(bound + 1.0));
        if (!Double.isFinite(vehicleWeight * (n + 1.0) + bound)) {
            throw new IllegalArgumentException("Instance costs are too large for finite fitness");
        }
    }

    public static final class RouteCheck {
        public final boolean feasible, capacityFeasible, timeFeasible;
        public final int lateCustomer;
        public final double distance, returnTime, peakLoad;
        RouteCheck(boolean capacity, boolean time, int late, double distance, double end, double peak) {
            this.capacityFeasible = capacity; this.timeFeasible = time;
            this.feasible = capacity && time; this.lateCustomer = late;
            this.distance = distance; this.returnTime = end; this.peakLoad = peak;
        }
    }

    public RouteCheck checkRoute(List<Integer> route) {
        double load = 0;
        for (Integer c : route) {
            if (c == null || c <= 0 || c >= problem.nodes.length)
                return new RouteCheck(false, false, -1, Double.POSITIVE_INFINITY, 0, 0);
            load += problem.nodes[c].delivery;
        }
        double peak = load, time = problem.nodes[0].ready, distance = 0;
        boolean capacity = load <= problem.capacity + EPS;
        boolean timely = true;
        int previous = 0, late = -1;
        for (int c : route) {
            Node node = problem.nodes[c];
            time += problem.travelTime[previous][c];
            time = Math.max(time, node.ready);
            if (time > node.due + EPS) { timely = false; if (late < 0) late = c; }
            time += node.service;
            load += node.pickup - node.delivery;
            peak = Math.max(peak, load);
            if (load < -EPS || load > problem.capacity + EPS) capacity = false;
            distance += problem.distance[previous][c];
            previous = c;
        }
        if (!route.isEmpty()) {
            distance += problem.distance[previous][0];
            time += problem.travelTime[previous][0];
        }
        if (time > problem.nodes[0].due + EPS) { timely = false; if (late < 0) late = 0; }
        return new RouteCheck(capacity, timely, late, distance, time, peak);
    }

    public boolean isRouteFeasible(List<Integer> route) { return checkRoute(route).feasible; }
    public double routeDistance(List<Integer> route) { return checkRoute(route).distance; }

    /** Pure detection: neither routes nor cached problem data are modified. */
    public boolean isFeasible(Solution solution) {
        if (solution == null || solution.vehicles() > problem.vehicles) return false;
        boolean[] visited = new boolean[problem.nodes.length];
        for (List<Integer> route : solution.routes) {
            for (Integer c : route) {
                if (c == null || c <= 0 || c >= visited.length || visited[c]) return false;
                visited[c] = true;
            }
            if (!isRouteFeasible(route)) return false;
        }
        for (int c = 1; c < visited.length; c++) if (!visited[c]) return false;
        return true;
    }

    public double distance(Solution solution) {
        double total = 0;
        for (List<Integer> r : solution.routes) total += routeDistance(r);
        return total;
    }

    public double fitness(Solution solution) {
        return vehicleWeight * solution.vehicles() + distanceWeight * distance(solution);
    }

    /** Monetary cost is reported separately from the dominating scalar used by SA. */
    public double operationalCost(Solution solution) {
        return problem.dispatchCost * solution.vehicles() + problem.unitCost * distance(solution);
    }

    public int compare(Solution a, Solution b) {
        int primary = Integer.compare(a.vehicles(), b.vehicles());
        return primary != 0 ? primary : Double.compare(distance(a), distance(b));
    }
}
