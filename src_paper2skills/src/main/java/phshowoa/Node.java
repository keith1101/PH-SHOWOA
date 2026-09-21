package phshowoa;

/** One physical stop. The id is the original input id, not its route index. */
public final class Node {
    public final int id;
    public final double delivery;
    public final double pickup;
    public final double ready;
    public final double due;
    public final double service;

    public Node(int id, double delivery, double pickup, double ready, double due, double service) {
        if (id < 0) {
            throw new IllegalArgumentException("Node id must be nonnegative: " + id);
        }
        nonnegative("delivery", delivery);
        nonnegative("pickup", pickup);
        nonnegative("ready", ready);
        nonnegative("due", due);
        nonnegative("service", service);
        if (due < ready) {
            throw new IllegalArgumentException("Node " + id + " has due time before ready time");
        }
        this.id = id;
        this.delivery = delivery;
        this.pickup = pickup;
        this.ready = ready;
        this.due = due;
        this.service = service;
    }

    static void nonnegative(String name, double value) {
        if (!Double.isFinite(value) || value < 0.0) {
            throw new IllegalArgumentException(name + " must be finite and nonnegative: " + value);
        }
    }
}
