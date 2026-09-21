package phshowoa;

import java.io.BufferedReader;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;

/** Readers for the repository's Wang-Chen text and explicit VRPSDPTW instances. */
public final class InstanceReader {
    private InstanceReader() { }

    public static Problem read(Path path) throws IOException {
        boolean explicit = detectExplicit(path);
        try (Cursor cursor = new Cursor(path)) {
            try {
                return explicit ? readExplicit(cursor) : readCoordinates(cursor);
            } catch (IllegalArgumentException ex) {
                throw cursor.error(ex.getMessage(), ex);
            }
        }
    }

    private static boolean detectExplicit(Path path) throws IOException {
        try (Cursor cursor = new Cursor(path)) {
            String line;
            while ((line = cursor.next()) != null) {
                String upper = line.toUpperCase(Locale.ROOT);
                if (upper.startsWith("TYPE") && upper.contains(":")
                        || upper.startsWith("DIMENSION") || upper.startsWith("EDGE_WEIGHT_TYPE")
                        || upper.equals("NODE_SECTION")) {
                    return true;
                }
                if (upper.equals("VEHICLE") || upper.equals("CUSTOMER")
                        || upper.matches("CUSTOMER\\s+VEHICLE") || upper.startsWith("CUST NO")) {
                    return false;
                }
            }
            throw cursor.error("Unsupported instance format; expected Wang-Chen text or EXPLICIT VRPSDPTW");
        }
    }

    private static Problem readExplicit(Cursor cursor) throws IOException {
        Map<String, String> header = new HashMap<String, String>();
        LinkedHashMap<Integer, Node> nodes = new LinkedHashMap<Integer, Node>();
        Map<Integer, Integer> indices = new HashMap<Integer, Integer>();
        double[][] distance = null;
        double[][] travelTime = null;
        Integer depot = null;
        int section = 0; // header, nodes, directed arcs, depot
        boolean depotTerminated = false;
        String line;
        while ((line = cursor.next()) != null) {
            String upper = line.toUpperCase(Locale.ROOT);
            if (upper.equals("EOF")) {
                break;
            }
            if (upper.equals("NODE_SECTION") || upper.equals("NODE_SECTION:")) {
                if (section != 0) {
                    throw cursor.error("NODE_SECTION must appear once, before distance/time entries");
                }
                section = 1;
                continue;
            }
            if (upper.equals("DISTANCETIME_SECTION") || upper.equals("DISTANCETIME_SECTION:")) {
                if (section != 1) {
                    throw cursor.error("DISTANCETIME_SECTION must follow NODE_SECTION");
                }
                int dimension = positiveInt(required(header, "DIMENSION"), "DIMENSION");
                if (nodes.size() != dimension) {
                    throw cursor.error("DIMENSION is " + dimension + " but NODE_SECTION contains " + nodes.size() + " nodes");
                }
                int index = 0;
                for (Integer id : nodes.keySet()) {
                    indices.put(id, index++);
                }
                distance = missingMatrix(dimension);
                travelTime = missingMatrix(dimension);
                section = 2;
                continue;
            }
            if (upper.equals("DEPOT_SECTION") || upper.equals("DEPOT_SECTION:")) {
                if (section != 2) {
                    throw cursor.error("DEPOT_SECTION must follow DISTANCETIME_SECTION");
                }
                section = 3;
                continue;
            }
            if (section == 0) {
                int colon = line.indexOf(':');
                if (colon < 0 && header.isEmpty()) {
                    header.put("NAME", line);
                    continue;
                }
                if (colon < 0) {
                    throw cursor.error("Expected KEY : VALUE header, found " + line);
                }
                String key = line.substring(0, colon).trim().toUpperCase(Locale.ROOT);
                String value = line.substring(colon + 1).trim();
                if (key.equals("COMMENT")) {
                    continue;
                }
                if (!Arrays.asList("NAME", "TYPE", "DIMENSION", "VEHICLES", "DISPATCHINGCOST",
                        "UNITCOST", "CAPACITY", "EDGE_WEIGHT_TYPE").contains(key)) {
                    throw cursor.error("Unsupported EXPLICIT header: " + key);
                }
                if (value.isEmpty() || header.put(key, value) != null) {
                    throw cursor.error("Empty or duplicate header: " + key);
                }
            } else if (section == 1) {
                String[] fields = fields(line, 6, cursor);
                int id = integer(fields[0], "node id");
                Node node = new Node(id, number(fields[1]), number(fields[2]), number(fields[3]),
                        number(fields[4]), number(fields[5]));
                if (nodes.put(id, node) != null) {
                    throw cursor.error("Duplicate node id " + id);
                }
            } else if (section == 2) {
                String[] fields = fields(line, 4, cursor);
                int fromId = integer(fields[0], "edge origin");
                int toId = integer(fields[1], "edge destination");
                Integer from = indices.get(fromId);
                Integer to = indices.get(toId);
                if (from == null || to == null) {
                    throw cursor.error("Edge references unknown node id: " + fromId + " -> " + toId);
                }
                double dist = number(fields[2]);
                double time = number(fields[3]);
                Node.nonnegative("distance", dist);
                Node.nonnegative("travel time", time);
                if (from.equals(to)) {
                    if (dist != 0.0 || time != 0.0) {
                        throw cursor.error("Self-edge distance/time must both be zero");
                    }
                } else if (!Double.isNaN(distance[from][to])) {
                    throw cursor.error("Duplicate directed edge " + fromId + " -> " + toId);
                }
                distance[from][to] = dist;
                travelTime[from][to] = time;
            } else {
                int id = integer(line, "depot id");
                if (id == -1 && depot != null && !depotTerminated) {
                    depotTerminated = true;
                } else if (depot == null && id >= 0) {
                    depot = id;
                } else {
                    throw cursor.error("Exactly one depot is supported (optional trailing -1)");
                }
            }
        }
        String type = required(header, "TYPE").toUpperCase(Locale.ROOT);
        if (!type.equals("VRPSDPTW") && !type.equals("VRPSPDTW")) {
            throw cursor.error("Unsupported TYPE: " + type);
        }
        if (!required(header, "EDGE_WEIGHT_TYPE").equalsIgnoreCase("EXPLICIT")) {
            throw cursor.error("EDGE_WEIGHT_TYPE must be EXPLICIT");
        }
        if (distance == null || depot == null || !nodes.containsKey(depot)) {
            throw cursor.error("Complete NODE_SECTION, DISTANCETIME_SECTION and one valid DEPOT_SECTION are required");
        }
        List<Integer> orderedIds = new ArrayList<Integer>(nodes.keySet());
        for (int i = 0; i < distance.length; i++) {
            for (int j = 0; j < distance.length; j++) {
                if (Double.isNaN(distance[i][j]) || Double.isNaN(travelTime[i][j])) {
                    throw cursor.error("Missing directed distance/time edge " + orderedIds.get(i) + " -> " + orderedIds.get(j));
                }
            }
        }
        orderedIds.remove(depot);
        orderedIds.add(0, depot);
        Node[] orderedNodes = new Node[nodes.size()];
        double[][] orderedDistance = new double[nodes.size()][nodes.size()];
        double[][] orderedTime = new double[nodes.size()][nodes.size()];
        for (int i = 0; i < orderedNodes.length; i++) {
            orderedNodes[i] = nodes.get(orderedIds.get(i));
            for (int j = 0; j < orderedNodes.length; j++) {
                orderedDistance[i][j] = distance[indices.get(orderedIds.get(i))][indices.get(orderedIds.get(j))];
                orderedTime[i][j] = travelTime[indices.get(orderedIds.get(i))][indices.get(orderedIds.get(j))];
            }
        }
        return new Problem(required(header, "NAME"), orderedNodes, orderedDistance, orderedTime,
                positiveInt(required(header, "VEHICLES"), "VEHICLES"), number(required(header, "CAPACITY")),
                number(required(header, "DISPATCHINGCOST")), number(required(header, "UNITCOST")));
    }

    private static Problem readCoordinates(Cursor cursor) throws IOException {
        String name = cursor.next();
        if (name == null) {
            throw cursor.error("Empty instance");
        }
        int vehicles = -1;
        int customerCount = -1;
        double capacity = Double.NaN;
        boolean coordinates = false;
        List<Node> nodes = new ArrayList<Node>();
        List<double[]> points = new ArrayList<double[]>();
        String line;
        while ((line = cursor.next()) != null) {
            String upper = line.toUpperCase(Locale.ROOT);
            if (upper.equals("EOF")) {
                break;
            }
            if (!coordinates && upper.startsWith("CUST") && upper.contains("XCOORD")) {
                if (!upper.contains("DDEMAND") || !upper.contains("PDEMAND")) {
                    throw cursor.error("Expected separate DDEMAND and PDEMAND columns for simultaneous pickup/delivery");
                }
                coordinates = true;
                continue;
            }
            if (!coordinates) {
                if (upper.equals("VEHICLE") || upper.equals("CUSTOMER")
                        || upper.matches("CUSTOMER\\s+VEHICLE") || upper.startsWith("NUMBER")) {
                    continue;
                }
                if (vehicles != -1) {
                    throw cursor.error("Unexpected text before customer rows: " + line);
                }
                String[] fields = line.split("\\s+");
                if (fields.length == 3) {
                    customerCount = integer(fields[0], "customer count");
                    if (customerCount < 0) {
                        throw cursor.error("Customer count must be nonnegative");
                    }
                    vehicles = positiveInt(fields[1], "vehicles");
                    capacity = number(fields[2]);
                } else if (fields.length == 2) {
                    vehicles = positiveInt(fields[0], "vehicles");
                    capacity = number(fields[1]);
                } else {
                    throw cursor.error("Expected customer-count/vehicles/capacity or vehicles/capacity line");
                }
            } else {
                String[] fields = fields(line, 8, cursor);
                nodes.add(new Node(integer(fields[0], "node id"), number(fields[3]), number(fields[4]),
                        number(fields[5]), number(fields[6]), number(fields[7])));
                double x = number(fields[1]);
                double y = number(fields[2]);
                if (!Double.isFinite(x) || !Double.isFinite(y)) {
                    throw cursor.error("Coordinates must be finite");
                }
                points.add(new double[] {x, y});
            }
        }
        if (!coordinates || nodes.isEmpty() || vehicles < 1) {
            throw cursor.error("Missing fleet data or customer rows");
        }
        if (customerCount >= 0 && nodes.size() != customerCount + 1) {
            throw cursor.error("Header declares " + customerCount + " customers but found " + (nodes.size() - 1));
        }
        double[][] distances = new double[nodes.size()][nodes.size()];
        for (int i = 0; i < nodes.size(); i++) {
            for (int j = 0; j < i; j++) {
                double value = Math.hypot(points.get(i)[0] - points.get(j)[0], points.get(i)[1] - points.get(j)[1]);
                distances[i][j] = value;
                distances[j][i] = value;
            }
        }
        // Wang-Chen coordinates use Euclidean distance and travel time at unit speed.
        // Their text format omits costs; these are the paper's WC coefficients.
        return new Problem(name, nodes.toArray(new Node[nodes.size()]), distances, distances,
                vehicles, capacity, 2000.0, 1.0);
    }

    private static double[][] missingMatrix(int size) {
        double[][] matrix = new double[size][size];
        for (int i = 0; i < size; i++) {
            Arrays.fill(matrix[i], Double.NaN);
            // The paper excludes self-arcs from E; local explicit files omit them.
            matrix[i][i] = 0.0;
        }
        return matrix;
    }

    private static String[] fields(String line, int count, Cursor cursor) throws IOException {
        String[] fields = line.contains(",") ? line.split("\\s*,\\s*", -1) : line.split("\\s+");
        if (fields.length != count) {
            throw cursor.error("Expected " + count + " fields, found " + fields.length);
        }
        return fields;
    }

    private static String required(Map<String, String> header, String key) {
        String value = header.get(key);
        if (value == null) {
            throw new IllegalArgumentException("Missing required header " + key);
        }
        return value;
    }

    private static int integer(String value, String label) {
        try {
            return Integer.parseInt(value.trim());
        } catch (NumberFormatException ex) {
            throw new IllegalArgumentException("Invalid integer " + label + ": " + value, ex);
        }
    }

    private static int positiveInt(String value, String label) {
        int parsed = integer(value, label);
        if (parsed <= 0) {
            throw new IllegalArgumentException(label + " must be positive");
        }
        return parsed;
    }

    private static double number(String value) {
        try {
            return Double.parseDouble(value.trim());
        } catch (NumberFormatException ex) {
            throw new IllegalArgumentException("Invalid number: " + value, ex);
        }
    }

    private static final class Cursor implements AutoCloseable {
        private final Path path;
        private final BufferedReader reader;
        private int lineNumber;

        Cursor(Path path) throws IOException {
            this.path = path;
            this.reader = Files.newBufferedReader(path, StandardCharsets.UTF_8);
        }

        String next() throws IOException {
            String line;
            while ((line = reader.readLine()) != null) {
                lineNumber++;
                if (lineNumber == 1 && line.startsWith("\uFEFF")) {
                    line = line.substring(1);
                }
                line = line.trim();
                if (!line.isEmpty() && !line.startsWith("#")) {
                    return line;
                }
            }
            return null;
        }

        IOException error(String message) {
            return new IOException(path + ":" + lineNumber + ": " + message);
        }

        IOException error(String message, Throwable cause) {
            return new IOException(path + ":" + lineNumber + ": " + message, cause);
        }

        @Override
        public void close() throws IOException {
            reader.close();
        }
    }
}
