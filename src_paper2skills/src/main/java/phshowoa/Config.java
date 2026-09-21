package phshowoa;

/** Paper defaults plus explicitly identified choices for unspecified procedures. */
public final class Config {
    public int iterations = 1000;
    public int populationSize = 30;
    public int workers = Math.max(1, Math.min(30, Runtime.getRuntime().availableProcessors()));
    public long seed = 42;
    public int localSearchInterval = 25;
    public int stagnationIterations = 50;
    public double improvementEpsilon = 1e-4;
    public double mutationProbability = 0.35;
    // Algorithm 2 provides no numerical settings for the following controls.
    public double initTemperature = 1.0;
    public double initCooling = 0.90;
    public double initMinTemperature = 0.01;
    public int initMoves = 20;
    public int constructionAttempts = 200;
    // DIVERSIFY is named, but its mechanics are not defined in the paper.
    public double diversificationFraction = 0.20;
    public int diversificationMoves = 5;

    public void validate() {
        if (iterations < 0 || populationSize < 1 || workers < 1 || initMoves < 0
                || constructionAttempts < 1 || localSearchInterval < 1 || stagnationIterations < 1
                || diversificationMoves < 1) throw new IllegalArgumentException("Invalid nonnegative/positive integer setting");
        if (!Double.isFinite(initTemperature) || !Double.isFinite(initMinTemperature)
                || initMinTemperature <= 0 || initTemperature <= initMinTemperature
                || !(initCooling > 0 && initCooling < 1))
            throw new IllegalArgumentException("SA initialization needs T0 > Tmin > 0 and 0 < cooling < 1");
        if (!(mutationProbability >= 0 && mutationProbability <= 1)
                || !(diversificationFraction > 0 && diversificationFraction <= 1)
                || !Double.isFinite(improvementEpsilon) || improvementEpsilon < 0)
            throw new IllegalArgumentException("Invalid probability or improvement epsilon");
        double stages = Math.ceil((Math.log(initMinTemperature) - Math.log(initTemperature)) / Math.log(initCooling));
        if (initMoves > 0 && (!Double.isFinite(stages) || stages > 100000))
            throw new IllegalArgumentException("Initialization cooling schedule exceeds 100000 stages");
        if (initMoves > 0) {
            for (double temperature = initTemperature; temperature > initMinTemperature;) {
                double next = temperature * initCooling;
                if (!(next < temperature))
                    throw new IllegalArgumentException("Initialization temperature stalls at floating-point precision");
                temperature = next;
            }
        }
    }

    public Config copy() {
        Config c = new Config();
        c.iterations = iterations; c.populationSize = populationSize; c.workers = workers; c.seed = seed;
        c.localSearchInterval = localSearchInterval; c.stagnationIterations = stagnationIterations;
        c.improvementEpsilon = improvementEpsilon; c.mutationProbability = mutationProbability;
        c.initTemperature = initTemperature; c.initCooling = initCooling; c.initMinTemperature = initMinTemperature;
        c.initMoves = initMoves; c.constructionAttempts = constructionAttempts;
        c.diversificationFraction = diversificationFraction; c.diversificationMoves = diversificationMoves;
        return c;
    }
}
