"""Reproducible benchmark wrapper for the standalone Java PH-SHOWOA solver.

The Java solver owns feasibility validation and writes one JSON result plus one
history CSV per seed.  This wrapper compiles it once, executes one JVM per
seed, supports safe resume, and aggregates the paper-reference comparison.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from typing import Any, Iterable, Optional


ROOT = Path(__file__).resolve().parents[1]
TARGETS_CSV = ROOT / "tests" / "paper_performance_targets.csv"
JAVA_PROJECT = ROOT / "src_paper2skills"
JAVA_SOURCES = JAVA_PROJECT / "src" / "main" / "java"
JAVA_CLASSES = JAVA_PROJECT / "build" / "classes"
ARTIFACT_ROOT = ROOT / "batch_results"
SCHEMA_VERSION = "1"

DEFAULT_INSTANCES = [
    "RCdp1001", "RCdp5001", "RCdp5007", "RCdp5004", "RCdp101", "Cdp103",
    "RCdp205", "Rdp210", "RCdp207", "RCdp202", "Rdp103", "Cdp104",
    "Cdp102", "RCdp203", "Rdp203", "RCdp104",
]


@dataclass(frozen=True)
class Target:
    instance: str
    path: Path
    target_vehicles: int
    target_distance: float


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def java_source_digest() -> str:
    """Hash source content and relative paths so resumed results match the code."""
    digest = hashlib.sha256()
    for path in sorted(JAVA_SOURCES.rglob("*.java")):
        digest.update(path.relative_to(JAVA_PROJECT).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def load_targets() -> dict[str, Target]:
    targets: dict[str, Target] = {}
    with TARGETS_CSV.open(newline="", encoding="utf-8") as stream:
        for row in csv.DictReader(stream):
            target = Target(
                instance=row["instance"].strip(),
                path=ROOT / row["path"].strip(),
                target_vehicles=int(row["target_vehicles"]),
                target_distance=float(row["target_distance"]),
            )
            targets[target.instance.lower()] = target

    # These instances have no paper target in the local CSV, but are useful
    # for scale checks and work exactly like the paper-targeted instances.
    for path in sorted((ROOT / "data" / "Liu_Tang_Yao").glob("*.vrpsdptw")):
        targets.setdefault(path.stem.lower(), Target(path.stem, path, -1, math.nan))
    return targets


def resolve_instances(requested: Iterable[str], targets: dict[str, Target]) -> list[Target]:
    resolved: list[Target] = []
    seen: set[str] = set()
    missing: list[str] = []
    duplicate: list[str] = []
    for raw in requested:
        target = targets.get(raw.strip().lower())
        if target is None:
            missing.append(raw)
        elif target.instance.lower() in seen:
            duplicate.append(target.instance)
        else:
            seen.add(target.instance.lower())
            resolved.append(target)
    if missing:
        raise ValueError("Unknown benchmark instances: " + ", ".join(missing))
    if duplicate:
        raise ValueError("Duplicate benchmark instances after resolution: " + ", ".join(duplicate))
    if not resolved:
        raise ValueError("No benchmark instances were selected")
    for target in resolved:
        if not target.path.is_file():
            raise ValueError(f"Missing benchmark input for {target.instance}: {target.path}")
    return resolved


def command_exists(command: str) -> bool:
    return shutil.which(command) is not None


def compile_java(javac: str) -> None:
    if not command_exists(javac):
        raise RuntimeError(f"Cannot find javac executable: {javac}")
    sources = sorted(JAVA_SOURCES.rglob("*.java"))
    if not sources:
        raise RuntimeError(f"No Java sources under {JAVA_SOURCES}")
    JAVA_CLASSES.mkdir(parents=True, exist_ok=True)
    command = [javac, "-encoding", "UTF-8", "-source", "8", "-target", "8", "-Xlint:all",
               "-d", str(JAVA_CLASSES), *map(str, sources)]
    completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=False)
    if completed.returncode:
        detail = (completed.stderr or completed.stdout).strip()
        raise RuntimeError(f"Java compilation failed ({completed.returncode}):\n{detail}")


def fingerprint(target: Target, seed: int, args: argparse.Namespace, source_digest: str) -> str:
    payload = {
        "schema": SCHEMA_VERSION,
        "java_source_sha256": source_digest,
        "instance": target.instance,
        "input": str(target.path.resolve()),
        "input_sha256": sha256_file(target.path),
        "seed": seed,
        "iterations": args.iterations,
        "population": args.population,
        "workers": args.workers,
        "init_moves": args.init_moves,
        "init_temperature": args.init_temperature,
        "init_cooling": args.init_cooling,
        "init_min_temperature": args.init_min_temperature,
        "construction_attempts": args.construction_attempts,
        "ls_interval": args.ls_interval,
        "stagnation": args.stagnation,
        "epsilon": args.epsilon,
        "mutation_probability": args.mutation_probability,
        "diversification_fraction": args.diversification_fraction,
        "diversification_moves": args.diversification_moves,
        "java": args.java,
        "xmx": args.xmx,
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def solver_command(target: Target, seed: int, output_dir: Path, args: argparse.Namespace) -> list[str]:
    return [
        args.java, f"-Xmx{args.xmx}", "-cp", str(JAVA_CLASSES), "phshowoa.Main", str(target.path),
        "--iterations", str(args.iterations), "--population", str(args.population),
        "--workers", str(args.workers), "--seed", str(seed), "--runs", "1", "--output", str(output_dir),
        "--init-moves", str(args.init_moves), "--init-temperature", str(args.init_temperature),
        "--init-cooling", str(args.init_cooling), "--init-min-temperature", str(args.init_min_temperature),
        "--construction-attempts", str(args.construction_attempts), "--ls-interval", str(args.ls_interval),
        "--stagnation", str(args.stagnation), "--epsilon", str(args.epsilon),
        "--mutation-probability", str(args.mutation_probability),
        "--diversification-fraction", str(args.diversification_fraction),
        "--diversification-moves", str(args.diversification_moves), "--quiet",
    ]


def find_solver_result(directory: Path, target: Target, seed: int) -> Path:
    matches: list[Path] = []
    for candidate in directory.glob("*.json"):
        try:
            document = json.loads(candidate.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if document.get("instance", "").lower() == target.instance.lower() and document.get("config", {}).get("seed") == seed:
            matches.append(candidate)
    if len(matches) != 1:
        raise RuntimeError(f"Expected exactly one Java result for {target.instance}, seed {seed} in {directory}; found {len(matches)}")
    return matches[0]


def validate_solver_result(document: dict[str, Any], target: Target, seed: int) -> None:
    if document.get("instance", "").lower() != target.instance.lower():
        raise RuntimeError("Java result instance does not match requested instance")
    if document.get("config", {}).get("seed") != seed:
        raise RuntimeError("Java result seed does not match requested seed")
    if not document.get("feasible"):
        raise RuntimeError("Java solver reported an infeasible result")
    if sha256_file(target.path) != document.get("input_sha256"):
        raise RuntimeError("Java result input SHA-256 does not match the current instance")
    for key in ("vehicles", "distance", "operational_cost", "fitness", "elapsed_seconds"):
        value = document.get(key)
        if not isinstance(value, (int, float)) or not math.isfinite(value):
            raise RuntimeError(f"Java result has missing/non-finite {key}")
    if document["vehicles"] < 1 or document["distance"] < 0:
        raise RuntimeError("Java result has invalid vehicle count or distance")
    routes = document.get("routes")
    if not isinstance(routes, list) or len(routes) != document["vehicles"]:
        raise RuntimeError("Java result routes do not match vehicle count")


def run_one(target: Target, repeat: int, args: argparse.Namespace, source_digest: str, batch_dir: Path) -> dict[str, Any]:
    seed = args.seed + repeat
    run_dir = batch_dir / target.instance / "runs" / f"run_{repeat + 1:02d}_seed_{seed}"
    output_dir = run_dir / "solver_output"
    summary_path = run_dir / "summary.json"
    expected_fingerprint = fingerprint(target, seed, args, source_digest)
    if summary_path.is_file():
        try:
            cached = json.loads(summary_path.read_text(encoding="utf-8"))
            if cached.get("status") == "success" and cached.get("fingerprint") == expected_fingerprint:
                return cached
        except (OSError, json.JSONDecodeError):
            pass
    output_dir.mkdir(parents=True, exist_ok=True)
    command = solver_command(target, seed, output_dir, args)
    start = time.perf_counter()
    completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=False)
    wall_seconds = time.perf_counter() - start
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "log.txt").write_text(
        (completed.stdout or "") + ("\n--- STDERR ---\n" + completed.stderr if completed.stderr else ""),
        encoding="utf-8",
    )
    base = {
        "benchmark_schema_version": SCHEMA_VERSION,
        "fingerprint": expected_fingerprint,
        "status": "failed",
        "instance": target.instance,
        "input": str(target.path.resolve()),
        "seed": seed,
        "repeat": repeat + 1,
        "wall_seconds": wall_seconds,
        "command": command,
        "return_code": completed.returncode,
        "log_path": str((run_dir / "log.txt").resolve()),
    }
    if completed.returncode:
        summary_path.write_text(json.dumps(base, indent=2), encoding="utf-8")
        diagnostic = (completed.stderr or completed.stdout).strip()[-4000:]
        raise RuntimeError(f"Java solver failed for {target.instance}, seed {seed}; see {run_dir / 'log.txt'}\n{diagnostic}")
    result_path = find_solver_result(output_dir, target, seed)
    result = json.loads(result_path.read_text(encoding="utf-8"))
    validate_solver_result(result, target, seed)
    history_path = result_path.with_name(result_path.stem + "-history.csv")
    if not history_path.is_file():
        raise RuntimeError(f"Java solver history CSV is missing: {history_path}")
    base.update({
        "status": "success",
        "vehicles": result["vehicles"],
        "distance": result["distance"],
        "operational_cost": result["operational_cost"],
        "fitness": result["fitness"],
        "solver_seconds": result["elapsed_seconds"],
        "feasible": True,
        "counters": result.get("counters", {}),
        "solver_result": str(result_path.resolve()),
        "history_csv": str(history_path.resolve()),
    })
    summary_path.write_text(json.dumps(base, indent=2), encoding="utf-8")
    return base


def nan_if_empty(values: list[float]) -> float:
    return mean(values) if values else math.nan


def summarize(target: Target, runs: list[dict[str, Any]]) -> dict[str, Any]:
    vehicles = [run["vehicles"] for run in runs]
    distances = [run["distance"] for run in runs]
    costs = [run["operational_cost"] for run in runs]
    wall = [run["wall_seconds"] for run in runs]
    solver = [run["solver_seconds"] for run in runs]
    best_nv = min(vehicles)
    best_td_at_best_nv = min(run["distance"] for run in runs if run["vehicles"] == best_nv)
    best_index = min(range(len(runs)), key=lambda i: (runs[i]["vehicles"], runs[i]["distance"]))
    has_target = target.target_vehicles >= 0 and math.isfinite(target.target_distance) and target.target_distance > 0
    same_nv = [run["distance"] for run in runs if has_target and run["vehicles"] == target.target_vehicles]
    best_td_at_paper_nv = min(same_nv) if same_nv else math.nan
    return {
        "benchmark_schema_version": SCHEMA_VERSION,
        "instance": target.instance,
        "input": str(target.path.resolve()),
        "paper_nv": target.target_vehicles if has_target else math.nan,
        "paper_td": target.target_distance if has_target else math.nan,
        "repeats": len(runs),
        "feasible_runs": sum(1 for run in runs if run["feasible"]),
        "avg_nv": mean(vehicles), "avg_td": mean(distances), "avg_operational_cost": mean(costs),
        "best_nv": best_nv, "best_td_at_best_nv": best_td_at_best_nv,
        "best_operational_cost": min(costs), "best_seed": runs[best_index]["seed"],
        "best_td_at_paper_nv": best_td_at_paper_nv, "same_vehicle_runs": len(same_nv),
        "same_vehicle_gap_pct": ((best_td_at_paper_nv - target.target_distance) / target.target_distance * 100.0)
        if same_nv else math.nan,
        "avg_nv_gap": mean(vehicles) - target.target_vehicles if has_target else math.nan,
        "best_nv_gap": best_nv - target.target_vehicles if has_target else math.nan,
        "avg_td_gap_pct": ((mean(distances) - target.target_distance) / target.target_distance * 100.0)
        if has_target else math.nan,
        "best_nv_td_gap_pct": ((best_td_at_best_nv - target.target_distance) / target.target_distance * 100.0)
        if has_target else math.nan,
        "avg_wall_seconds": mean(wall), "avg_solver_seconds": mean(solver),
        "avg_sho_updates": nan_if_empty([run["counters"].get("sho") for run in runs if isinstance(run["counters"].get("sho"), (int, float))]),
        "avg_woa_updates": nan_if_empty([run["counters"].get("woa") for run in runs if isinstance(run["counters"].get("woa"), (int, float))]),
        "avg_sa_worse_accepted": nan_if_empty([run["counters"].get("sa_worse_accepted") for run in runs if isinstance(run["counters"].get("sa_worse_accepted"), (int, float))]),
        "avg_local_search": nan_if_empty([run["counters"].get("local_search") for run in runs if isinstance(run["counters"].get("local_search"), (int, float))]),
        "avg_diversification": nan_if_empty([run["counters"].get("diversification") for run in runs if isinstance(run["counters"].get("diversification"), (int, float))]),
    }


def csv_value(value: Any) -> Any:
    return "" if isinstance(value, float) and math.isnan(value) else value


def optional(value: float, digits: int = 2, suffix: str = "") -> str:
    return "n/a" if isinstance(value, float) and math.isnan(value) else f"{value:.{digits}f}{suffix}"


def write_reports(results: list[dict[str, Any]], args: argparse.Namespace, batch_dir: Path, source_digest: str) -> tuple[Path, Path]:
    fields = [
        "benchmark_schema_version", "instance", "input", "paper_nv", "paper_td", "repeats", "feasible_runs",
        "avg_nv", "avg_td", "avg_operational_cost", "best_nv", "best_td_at_best_nv", "best_operational_cost",
        "best_seed", "best_td_at_paper_nv", "same_vehicle_runs", "same_vehicle_gap_pct", "avg_nv_gap",
        "best_nv_gap", "avg_td_gap_pct", "best_nv_td_gap_pct", "avg_wall_seconds", "avg_solver_seconds",
        "avg_sho_updates", "avg_woa_updates", "avg_sa_worse_accepted", "avg_local_search", "avg_diversification",
    ]
    csv_path = batch_dir / "summary.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for result in results:
            writer.writerow({name: csv_value(result[name]) for name in fields})

    markdown_path = batch_dir / "report.md"
    with markdown_path.open("w", encoding="utf-8") as stream:
        stream.write(f"# Java PH-SHOWOA benchmark ({args.repeats} repeats)\n\n")
        stream.write("This report measures the Java implementation in `src_paper2skills`. Paper values are descriptive references only: the Java implementation documents deliberate corrections and discrete-operator choices, so a lower TD alone does not establish a paper comparison claim.\n\n")
        stream.write(f"- Java source SHA-256: `{source_digest}`\n")
        stream.write(f"- Iterations: `{args.iterations}`; population: `{args.population}`; workers: `{args.workers}`\n")
        stream.write(f"- Seeds: `{args.seed}` through `{args.seed + args.repeats - 1}`\n")
        stream.write(f"- Java heap: `{args.xmx}`; Java executable: `{args.java}`\n")
        stream.write(f"- Per-run artifacts: `{batch_dir.relative_to(ROOT)}/<instance>/runs/`\n\n")
        stream.write("| Instance | Paper NV | Paper TD | Avg NV | Best NV | TD @ Best NV | TD @ Paper NV | Same-NV gap | Feasible | Avg wall time |\n")
        stream.write("| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | :---: | ---: |\n")
        for result in results:
            stream.write(
                f"| {result['instance']} | {optional(result['paper_nv'], 0)} | {optional(result['paper_td'])} | "
                f"{result['avg_nv']:.2f} | {result['best_nv']} | {result['best_td_at_best_nv']:.2f} | "
                f"{optional(result['best_td_at_paper_nv'])} | {optional(result['same_vehicle_gap_pct'], suffix='%')} | "
                f"{result['feasible_runs']}/{result['repeats']} | {result['avg_wall_seconds']:.3f}s |\n"
            )
        stream.write("\n`TD @ Paper NV` and `Same-NV gap` are blank when no run uses the paper's NV. The lexicographic Java solver must be compared in that context. `Avg wall time` includes JVM process launch and result I/O; `avg_solver_seconds` in `summary.csv` is the solver's internal timing.\n")
    return csv_path, markdown_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Benchmark the standalone Java PH-SHOWOA solver.")
    parser.add_argument("--instances", nargs="+", default=DEFAULT_INSTANCES, help="Paper-targeted instance names, case-insensitive.")
    parser.add_argument("--repeats", type=int, default=30, help="Independent seeds per instance.")
    parser.add_argument("--iterations", type=int, default=1000)
    parser.add_argument("--population", type=int, default=30)
    parser.add_argument("--workers", type=int, default=max(1, min(30, (os_cpu_count() or 1))))
    parser.add_argument("--seed", type=int, default=42, help="Base seed; each repeat increments it by one.")
    parser.add_argument("--java", default="java")
    parser.add_argument("--javac", default="javac")
    parser.add_argument("--xmx", default="1g", help="JVM maximum heap, for example 1g or 2048m.")
    parser.add_argument("--skip-build", action="store_true", help="Reuse existing Java class files without compiling.")
    parser.add_argument("--output-tag", default=None, help="Directory name below batch_results.")
    parser.add_argument("--init-moves", type=int, default=20)
    parser.add_argument("--init-temperature", type=float, default=1.0)
    parser.add_argument("--init-cooling", type=float, default=0.90)
    parser.add_argument("--init-min-temperature", type=float, default=0.01)
    parser.add_argument("--construction-attempts", type=int, default=200)
    parser.add_argument("--ls-interval", type=int, default=25)
    parser.add_argument("--stagnation", type=int, default=50)
    parser.add_argument("--epsilon", type=float, default=1e-4)
    parser.add_argument("--mutation-probability", type=float, default=0.35)
    parser.add_argument("--diversification-fraction", type=float, default=0.20)
    parser.add_argument("--diversification-moves", type=int, default=5)
    return parser


def os_cpu_count() -> Optional[int]:
    try:
        import os
        return os.cpu_count()
    except (ImportError, AttributeError):
        return None


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.repeats < 1:
        parser.error("--repeats must be positive")
    if not command_exists(args.java):
        parser.error(f"Cannot find Java executable: {args.java}")
    try:
        selected = resolve_instances(args.instances, load_targets())
    except ValueError as error:
        parser.error(str(error))
    if args.output_tag is None:
        args.output_tag = f"java_paper_run_{args.repeats}r_{args.iterations}it_pop{args.population}_w{args.workers}"
    batch_dir = ARTIFACT_ROOT / args.output_tag
    source_digest = java_source_digest()
    if args.skip_build:
        if not (JAVA_CLASSES / "phshowoa" / "Main.class").is_file():
            parser.error(f"--skip-build requested but Java classes are missing under {JAVA_CLASSES}")
    else:
        print("Compiling Java PH-SHOWOA...", flush=True)
        try:
            compile_java(args.javac)
        except RuntimeError as error:
            parser.error(str(error))
    print(f"Starting Java benchmark: {len(selected)} instances × {args.repeats} seeds.", flush=True)
    results: list[dict[str, Any]] = []
    for index, target in enumerate(selected, 1):
        print(f"[{index}/{len(selected)}] {target.instance}", flush=True)
        runs = []
        for repeat in range(args.repeats):
            run = run_one(target, repeat, args, source_digest, batch_dir)
            runs.append(run)
            print(f"  {repeat + 1:02d}/{args.repeats} seed={run['seed']} NV={run['vehicles']} TD={run['distance']:.6f} "
                  f"feasible=yes wall={run['wall_seconds']:.3f}s", flush=True)
        result = summarize(target, runs)
        results.append(result)
        print(f"  best: NV={result['best_nv']} TD={result['best_td_at_best_nv']:.6f}; "
              f"average: NV={result['avg_nv']:.2f} TD={result['avg_td']:.6f}", flush=True)
    csv_path, markdown_path = write_reports(results, args, batch_dir, source_digest)
    print(f"Completed. CSV: {csv_path}\nReport: {markdown_path}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
