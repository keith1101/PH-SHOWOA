package phshowoa;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;

/** Standalone Java entry point; no Python, C++, Maven, or third-party runtime required. */
public final class Main {
    private Main() { }

    public static void main(String[] args) {
        try { run(args); }
        catch (Exception e) { System.err.println("ERROR: " + e.getMessage()); System.exit(2); }
    }

    private static void run(String[] args) throws Exception {
        Config config = new Config();
        List<Path> inputs = new ArrayList<Path>();
        int runs = 1;
        Path output = Paths.get("src_paper2skills", "results");
        boolean quiet = false;
        for (int i = 0; i < args.length; i++) {
            String arg = args[i];
            if (arg.equals("--help") || arg.equals("-h")) { help(); return; }
            if (arg.equals("--quiet")) { quiet = true; continue; }
            if (!arg.startsWith("--")) { inputs.add(Paths.get(arg)); continue; }
            if (i + 1 == args.length) throw new IllegalArgumentException("Missing value for " + arg);
            String value = args[++i];
            switch (arg) {
                case "--iterations": config.iterations = Integer.parseInt(value); break;
                case "--population": config.populationSize = Integer.parseInt(value); break;
                case "--workers": config.workers = Integer.parseInt(value); break;
                case "--seed": config.seed = Long.parseLong(value); break;
                case "--runs": runs = Integer.parseInt(value); break;
                case "--output": output = Paths.get(value); break;
                case "--init-moves": config.initMoves = Integer.parseInt(value); break;
                case "--init-temperature": config.initTemperature = Double.parseDouble(value); break;
                case "--init-cooling": config.initCooling = Double.parseDouble(value); break;
                case "--init-min-temperature": config.initMinTemperature = Double.parseDouble(value); break;
                case "--construction-attempts": config.constructionAttempts = Integer.parseInt(value); break;
                case "--ls-interval": config.localSearchInterval = Integer.parseInt(value); break;
                case "--stagnation": config.stagnationIterations = Integer.parseInt(value); break;
                case "--epsilon": config.improvementEpsilon = Double.parseDouble(value); break;
                case "--mutation-probability": config.mutationProbability = Double.parseDouble(value); break;
                case "--diversification-fraction": config.diversificationFraction = Double.parseDouble(value); break;
                case "--diversification-moves": config.diversificationMoves = Integer.parseInt(value); break;
                default: throw new IllegalArgumentException("Unknown option " + arg);
            }
        }
        if (inputs.isEmpty()) throw new IllegalArgumentException("Provide at least one instance path; see --help");
        if (runs < 1) throw new IllegalArgumentException("--runs must be positive");
        config.validate();
        Files.createDirectories(output);
        long baseSeed = config.seed;
        List<String> summary = new ArrayList<String>();
        summary.add("instance,input,run,seed,vehicles,distance,operational_cost,fitness,seconds,sho_updates,woa_updates,sa_worse_accepted,local_search_calls,diversifications");
        for (int instance = 0; instance < inputs.size(); instance++) {
            Path path = inputs.get(instance).toAbsolutePath().normalize();
            Problem problem = InstanceReader.read(path);
            Evaluator evaluator = new Evaluator(problem);
            String hash = sha256(path);
            for (int run = 0; run < runs; run++) {
                config.seed = Math.addExact(baseSeed, run);
                if (!quiet) System.err.printf(Locale.ROOT,
                        "%s | customers=%d J=%d | run=%d/%d seed=%d workers=%d%n",
                        problem.name, problem.nodes.length - 1, problem.vehicles, run + 1, runs, config.seed, config.workers);
                Result result = new Solver(problem, config).solve(quiet ? null : progress -> {
                    if (progress.iteration < 0 || (progress.iteration + 1) % 100 == 0)
                        System.err.printf(Locale.ROOT, "  iteration=%d NV=%d TD=%.6f distinct=%d%n",
                                progress.iteration, progress.vehicles, progress.distance, progress.distinctSolutions);
                });
                if (!evaluator.isFeasible(result.best)) throw new IllegalStateException("Output failed final feasibility audit");
                String stem = String.format(Locale.ROOT, "%02d-%s-seed-%d", instance + 1,
                        problem.name.replaceAll("[^A-Za-z0-9._-]", "_"), config.seed);
                Files.write(output.resolve(stem + ".json"), json(problem, evaluator, config, result, path, hash)
                        .getBytes(StandardCharsets.UTF_8));
                List<String> trace = new ArrayList<String>();
                trace.add("iteration,vehicles,distance,distinct_solutions");
                for (Result.Progress p : result.history) trace.add(p.iteration + "," + p.vehicles + "," + p.distance + "," + p.distinctSolutions);
                Files.write(output.resolve(stem + "-history.csv"), trace, StandardCharsets.UTF_8);
                summary.add(csv(problem.name) + "," + csv(path.toString()) + "," + (run + 1) + "," + config.seed
                        + "," + result.best.vehicles() + "," + evaluator.distance(result.best)
                        + "," + evaluator.operationalCost(result.best) + "," + evaluator.fitness(result.best)
                        + "," + result.elapsedSeconds + "," + result.shoUpdates + "," + result.woaUpdates
                        + "," + result.saWorseAccepted + "," + result.localSearchCalls + "," + result.diversifications);
                Files.write(output.resolve("summary.csv"), summary, StandardCharsets.UTF_8);
                System.out.printf(Locale.ROOT, "%s seed=%d NV=%d TD=%.6f cost=%.6f seconds=%.3f feasible=true%n",
                        problem.name, config.seed, result.best.vehicles(), evaluator.distance(result.best),
                        evaluator.operationalCost(result.best), result.elapsedSeconds);
                System.out.println("  " + output.resolve(stem + ".json").toAbsolutePath().normalize());
            }
        }
    }

    private static String json(Problem p, Evaluator e, Config c, Result r, Path path, String hash) {
        StringBuilder b = new StringBuilder();
        b.append("{\n  \"implementation\": \"PH-SHOWOA Java paper2skills, corrected Section 3 / Algorithm 1\",\n");
        b.append("  \"instance\": ").append(quote(p.name)).append(",\n  \"input\": ").append(quote(path.toString()));
        b.append(",\n  \"input_sha256\": ").append(quote(hash));
        b.append(",\n  \"java_version\": ").append(quote(System.getProperty("java.version")));
        b.append(",\n  \"config\": {\"seed\": ").append(c.seed).append(", \"iterations\": ").append(c.iterations)
                .append(", \"population\": ").append(c.populationSize).append(", \"workers\": ").append(c.workers)
                .append(", \"init_moves\": ").append(c.initMoves).append(", \"init_temperature\": ").append(c.initTemperature)
                .append(", \"init_cooling\": ").append(c.initCooling).append(", \"init_min_temperature\": ").append(c.initMinTemperature)
                .append(", \"construction_attempts\": ").append(c.constructionAttempts)
                .append(", \"local_search_interval\": ").append(c.localSearchInterval)
                .append(", \"stagnation_iterations\": ").append(c.stagnationIterations)
                .append(", \"epsilon\": ").append(c.improvementEpsilon)
                .append(", \"mutation_probability\": ").append(c.mutationProbability)
                .append(", \"diversification_fraction\": ").append(c.diversificationFraction)
                .append(", \"diversification_moves\": ").append(c.diversificationMoves).append("},\n");
        b.append("  \"objective\": {\"priority\": \"vehicles_then_distance\", \"vehicle_weight\": ")
                .append(e.vehicleWeight).append(", \"distance_weight\": ").append(e.distanceWeight)
                .append(", \"dispatch_cost\": ").append(p.dispatchCost)
                .append(", \"unit_cost\": ").append(p.unitCost).append("},\n");
        b.append("  \"vehicles\": ").append(r.best.vehicles()).append(",\n  \"distance\": ").append(e.distance(r.best))
                .append(",\n  \"operational_cost\": ").append(e.operationalCost(r.best))
                .append(",\n  \"fitness\": ").append(e.fitness(r.best)).append(",\n  \"feasible\": true,\n");
        b.append("  \"elapsed_seconds\": ").append(r.elapsedSeconds).append(",\n  \"counters\": {\"sho\": ")
                .append(r.shoUpdates).append(", \"woa\": ").append(r.woaUpdates).append(", \"sa_worse_accepted\": ")
                .append(r.saWorseAccepted).append(", \"local_search\": ").append(r.localSearchCalls)
                .append(", \"diversification\": ").append(r.diversifications).append("},\n");
        b.append("  \"routes\": [\n");
        for (int i = 0; i < r.best.routes.size(); i++) {
            List<Integer> route = r.best.routes.get(i);
            b.append("    [").append(p.nodes[0].id);
            for (int customer : route) b.append(", ").append(p.nodes[customer].id);
            b.append(", ").append(p.nodes[0].id).append("]");
            if (i + 1 < r.best.routes.size()) b.append(',');
            b.append('\n');
        }
        b.append("  ]\n}\n");
        return b.toString();
    }

    private static String quote(String s) {
        StringBuilder b = new StringBuilder("\"");
        for (int i = 0; i < s.length(); i++) {
            char ch = s.charAt(i);
            if (ch == '"' || ch == '\\') b.append('\\').append(ch);
            else if (ch < 32) b.append(String.format(Locale.ROOT, "\\u%04x", (int) ch));
            else b.append(ch);
        }
        return b.append('"').toString();
    }

    private static String csv(String s) { return "\"" + s.replace("\"", "\"\"") + "\""; }
    private static String sha256(Path path) throws Exception {
        byte[] digest = MessageDigest.getInstance("SHA-256").digest(Files.readAllBytes(path));
        StringBuilder result = new StringBuilder();
        for (byte v : digest) result.append(String.format(Locale.ROOT, "%02x", v & 255));
        return result.toString();
    }

    private static void help() {
        System.out.println("Usage: java -cp src_paper2skills/build/classes phshowoa.Main INSTANCE [INSTANCE ...] [OPTIONS]\n"
                + "  --iterations 1000 --population 30 --workers N --seed 42 --runs 1\n"
                + "  --output DIR --quiet\n"
                + "  --init-moves 20 --init-temperature 1 --init-cooling .9 --init-min-temperature .01\n"
                + "  --construction-attempts 200 --ls-interval 25 --stagnation 50 --epsilon .0001\n"
                + "  --mutation-probability .35 --diversification-fraction .2 --diversification-moves 5\n"
                + "Paper repetition protocol: --runs 30 (seeds baseSeed through baseSeed+29).\n"
                + "Each output directory is one batch; reuse overwrites matching runs and summary.csv.");
    }
}
