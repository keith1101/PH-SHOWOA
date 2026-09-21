package phshowoa;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

/** Immutable customer-only routes; the depot at each end is implicit. */
public final class Solution {
    public final List<List<Integer>> routes;

    public Solution(List<? extends List<Integer>> routes) {
        if (routes == null) {
            throw new IllegalArgumentException("Routes must not be null");
        }
        List<List<Integer>> copy = new ArrayList<List<Integer>>();
        for (List<Integer> route : routes) {
            if (route == null) {
                throw new IllegalArgumentException("A route must not be null");
            }
            for (Integer node : route) {
                if (node == null) {
                    throw new IllegalArgumentException("Route entries must not be null");
                }
            }
            if (!route.isEmpty()) {
                copy.add(Collections.unmodifiableList(new ArrayList<Integer>(route)));
            }
        }
        this.routes = Collections.unmodifiableList(copy);
    }

    public int vehicles() {
        return routes.size();
    }

    public List<List<Integer>> mutableRoutes() {
        List<List<Integer>> copy = new ArrayList<List<Integer>>();
        for (List<Integer> route : routes) {
            copy.add(new ArrayList<Integer>(route));
        }
        return copy;
    }

    public static Solution of(int[]... routes) {
        if (routes == null) {
            throw new IllegalArgumentException("Routes must not be null");
        }
        List<List<Integer>> converted = new ArrayList<List<Integer>>();
        for (int[] route : routes) {
            if (route == null) {
                throw new IllegalArgumentException("A route must not be null");
            }
            List<Integer> convertedRoute = new ArrayList<Integer>();
            for (int node : route) {
                convertedRoute.add(node);
            }
            converted.add(convertedRoute);
        }
        return new Solution(converted);
    }

    @Override
    public boolean equals(Object other) {
        return this == other || other instanceof Solution && routes.equals(((Solution) other).routes);
    }

    @Override
    public int hashCode() {
        return routes.hashCode();
    }

    @Override
    public String toString() {
        return routes.toString();
    }
}
