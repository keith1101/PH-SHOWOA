package phshowoa;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

public final class Result {
    public final Solution best;
    public final List<Progress> history;
    public final long shoUpdates, woaUpdates, saWorseAccepted;
    public final int localSearchCalls, diversifications;
    public final double elapsedSeconds;

    public static final class Progress {
        public final int iteration, vehicles, distinctSolutions;
        public final double distance;
        Progress(int iteration, Solution best, Evaluator evaluator, List<Solution> population) {
            this.iteration = iteration; this.vehicles = best.vehicles();
            this.distance = evaluator.distance(best);
            this.distinctSolutions = new java.util.HashSet<Solution>(population).size();
        }
    }

    Result(Solution best, List<Progress> history, long sho, long woa, long worse,
           int localSearchCalls, int diversifications, double seconds) {
        this.best = best; this.history = Collections.unmodifiableList(new ArrayList<Progress>(history));
        this.shoUpdates = sho; this.woaUpdates = woa; this.saWorseAccepted = worse;
        this.localSearchCalls = localSearchCalls; this.diversifications = diversifications;
        this.elapsedSeconds = seconds;
    }
}
