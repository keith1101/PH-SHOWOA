package phshowoa;

import java.util.HashSet;
import java.util.Set;

/**
 * Validated VRPSPDTW instance, with depot at internal index zero.
 * Constructor inputs are copied. Public arrays are read-only by convention;
 * the solver never mutates them, so concurrent evaluation can share an instance.
 */
public final class Problem {
    public final String name;
    public final Node[] nodes;
    public final double[][] distance;
    public final double[][] travelTime;
    public final int vehicles;
    public final double capacity;
    public final double dispatchCost;
    public final double unitCost;

    public Problem(String name, Node[] nodes, double[][] distance, double[][] travelTime,
                   int vehicles, double capacity, double dispatchCost, double unitCost) {
        if (name == null || name.trim().isEmpty()) {
            throw new IllegalArgumentException("Problem name is required");
        }
        if (nodes == null || nodes.length == 0) {
            throw new IllegalArgumentException("Problem requires at least the depot");
        }
        Set<Integer> ids = new HashSet<Integer>();
        for (Node node : nodes) {
            if (node == null || !ids.add(node.id)) {
                throw new IllegalArgumentException("Nodes must be nonnull with distinct original ids");
            }
        }
        if (nodes[0].delivery != 0.0 || nodes[0].pickup != 0.0 || nodes[0].service != 0.0) {
            throw new IllegalArgumentException("Depot must have zero delivery, pickup and service time");
        }
        if (vehicles <= 0) {
            throw new IllegalArgumentException("Available vehicles must be positive");
        }
        Node.nonnegative("capacity", capacity);
        if (capacity == 0.0) {
            throw new IllegalArgumentException("Capacity must be positive");
        }
        Node.nonnegative("dispatchCost", dispatchCost);
        Node.nonnegative("unitCost", unitCost);
        this.name = name;
        this.nodes = nodes.clone();
        this.distance = matrixCopy("distance", distance, nodes.length);
        this.travelTime = matrixCopy("travelTime", travelTime, nodes.length);
        this.vehicles = vehicles;
        this.capacity = capacity;
        this.dispatchCost = dispatchCost;
        this.unitCost = unitCost;
    }

    public int customerCount() {
        return nodes.length - 1;
    }

    private static double[][] matrixCopy(String name, double[][] matrix, int dimension) {
        if (matrix == null || matrix.length != dimension) {
            throw new IllegalArgumentException(name + " must have " + dimension + " rows");
        }
        double[][] result = new double[dimension][];
        for (int i = 0; i < dimension; i++) {
            if (matrix[i] == null || matrix[i].length != dimension) {
                throw new IllegalArgumentException(name + " row " + i + " must have " + dimension + " columns");
            }
            result[i] = matrix[i].clone();
            for (int j = 0; j < dimension; j++) {
                Node.nonnegative(name + "[" + i + "][" + j + "]", result[i][j]);
                if (i == j && result[i][j] != 0.0) {
                    throw new IllegalArgumentException(name + " diagonal must be zero");
                }
            }
        }
        return result;
    }
}
