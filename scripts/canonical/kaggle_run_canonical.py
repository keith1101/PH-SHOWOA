from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
from pathlib import Path
from typing import List

# Setup sys.path so src_canonical is importable
search_paths = [
    Path.cwd(),
    Path(__file__).resolve().parents[2],
    Path("/kaggle/working"),
    Path("/kaggle/input/phshowoa-code"),
    Path("/kaggle/input/datasets/keith1101/phshowoa-code"),
]
for p in search_paths:
    if p.exists() and str(p) not in sys.path:
        sys.path.insert(0, str(p))

from src_canonical.problem import Problem
from src_canonical.algorithm1_solver import PHSHOWOASolver, SolverConfig, RunResult


CSV_COLUMNS = [
    "instance",
    "algo",
    "run",
    "seed",
    "NV",
    "TD",
    "cost",
    "feasible",
    "violation_note",
    "elapsed_seconds",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run Canonical Paper-Aligned PH-SHOWOA on Kaggle"
    )
    parser.add_argument("--instance", type=str, required=True, help="Instance name (e.g. RCdp1001)")
    parser.add_argument("--data_root", type=Path, default=None, help="Root directory for dataset")
    parser.add_argument("--repeats", type=int, default=30, help="Number of runs (default: 30)")
    parser.add_argument("--seed_start", type=int, default=42, help="Starting random seed (default: 42)")
    parser.add_argument("--pop_size", type=int, default=30, help="Population size (default: 30)")
    parser.add_argument("--max_iter", type=int, default=1000, help="Max iterations (default: 1000)")
    parser.add_argument("--workers", type=int, default=1, help="Worker threads (default: 1)")
    default_out = Path("/kaggle/working/outputs") if Path("/kaggle/working").exists() else Path("outputs/kaggle_canonical_test")
    parser.add_argument("--output_dir", type=Path, default=default_out, help="Output directory")
    return parser.parse_args()


def find_instance_file(instance_name: str, data_root: Path | None) -> Path:
    candidates = []
    inst = instance_name.strip()
    inst_low = inst.lower()

    if data_root is not None:
        candidates.extend([
            data_root / f"{inst}.txt",
            data_root / f"{inst_low}.txt",
            data_root / f"{inst}.vrpsdptw",
            data_root / f"{inst_low}.vrpsdptw",
            data_root / f"explicit_{inst}.vrpsdptw",
            data_root / f"explicit_{inst_low}.vrpsdptw",
            data_root / "Wang_Chen" / f"{inst}.txt",
            data_root / "Wang_Chen" / f"{inst_low}.txt",
            data_root / "Wang_Chen" / f"explicit_{inst}.vrpsdptw",
            data_root / "Wang_Chen" / f"explicit_{inst_low}.vrpsdptw",
        ])

    kaggle_data_roots = [
        Path("/kaggle/working/data/Wang_Chen"),
        Path("/kaggle/input/ph-showoa"),
        Path("/kaggle/input/datasets/keith1101/ph-showoa"),
        Path("/kaggle/input/ph-showoa/data/Wang_Chen"),
        Path("/kaggle/input/datasets/keith1101/ph-showoa/data/Wang_Chen"),
        Path("data/Wang_Chen"),
        Path("data/RCdp"),
    ]
    for d in kaggle_data_roots:
        candidates.extend([
            d / f"{inst}.txt",
            d / f"{inst_low}.txt",
            d / f"{inst}.vrpsdptw",
            d / f"{inst_low}.vrpsdptw",
            d / f"explicit_{inst}.vrpsdptw",
            d / f"explicit_{inst_low}.vrpsdptw",
            d / "Wang_Chen" / f"{inst}.txt",
            d / "Wang_Chen" / f"{inst_low}.txt",
            d / "Wang_Chen" / f"explicit_{inst}.vrpsdptw",
            d / "Wang_Chen" / f"explicit_{inst_low}.vrpsdptw",
            d / "data" / "Wang_Chen" / f"{inst}.txt",
            d / "data" / "Wang_Chen" / f"{inst_low}.txt",
        ])

    for cand in candidates:
        if cand.is_file():
            return cand

    raise FileNotFoundError(f"Could not locate instance file for: {instance_name}")


def main() -> None:
    args = parse_args()
    print("=" * 70)
    print(f"KAGGLE CANONICAL RUNNER: {args.instance}")
    print(f"Repeats: {args.repeats}, Seed start: {args.seed_start}")
    print(f"Pop size: {args.pop_size}, Max iter: {args.max_iter}")
    print("=" * 70)

    inst_file = find_instance_file(args.instance, args.data_root)
    print(f"Loading instance from: {inst_file}")
    problem = Problem.load(inst_file)
    print(f"Instance loaded: {problem.name} ({problem.num_customers} customers, Q={problem.capacity}, maxV={problem.max_vehicles})")

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    runs_csv_path = out_dir / "runs.csv"
    summary_json_path = out_dir / f"summary_{problem.name}_{args.seed_start}_{args.repeats}.json"
    best_sol_path = out_dir / f"best_solution_{problem.name}.txt"

    if not runs_csv_path.exists():
        with open(runs_csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(CSV_COLUMNS)

    results: List[RunResult] = []
    t_start_total = time.time()

    for run_idx in range(1, args.repeats + 1):
        run_seed = args.seed_start + (run_idx - 1)
        global_run_no = run_seed - 42 + 1
        config = SolverConfig(
            pop_size=args.pop_size,
            max_iter=args.max_iter,
            seed=run_seed,
            workers=args.workers,
        )
        solver = PHSHOWOASolver(problem, config)
        res = solver.solve(run_index=global_run_no)
        results.append(res)

        # Append to CSV
        with open(runs_csv_path, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                res.instance,
                res.algo,
                res.run,
                res.seed,
                res.nv,
                f"{res.td:.2f}",
                f"{res.cost:.2f}",
                res.feasible,
                res.violation_note,
                f"{res.elapsed_seconds:.2f}",
            ])

        print(
            f"Run {res.run:02d}/{args.repeats:02d} (seed={res.seed}): "
            f"NV={res.nv}, TD={res.td:.2f}, Cost={res.cost:.2f}, "
            f"Feasible={res.feasible} ({res.elapsed_seconds:.2f}s)"
        )

    t_total = time.time() - t_start_total

    # Summary statistics
    feasible_results = [r for r in results if r.feasible]
    feas_rate = len(feasible_results) / len(results)

    best_res = min(results, key=lambda r: (not r.feasible, r.nv, r.td))
    mean_nv = sum(r.nv for r in results) / len(results)
    mean_td = sum(r.td for r in results) / len(results)
    mean_cost = sum(r.cost for r in results) / len(results)

    summary_data = {
        "instance": problem.name,
        "algo": "PH-SHOWOA-Canonical",
        "total_runs": len(results),
        "feasible_runs": len(feasible_results),
        "feasibility_rate": feas_rate,
        "mean_nv": round(mean_nv, 4),
        "mean_td": round(mean_td, 4),
        "mean_cost": round(mean_cost, 4),
        "best_nv": best_res.nv,
        "best_td": round(best_res.td, 4),
        "best_cost": round(best_res.cost, 4),
        "total_elapsed_seconds": round(t_total, 2),
    }

    with open(summary_json_path, "w", encoding="utf-8") as f:
        json.dump(summary_data, f, indent=2)

    with open(best_sol_path, "w", encoding="utf-8") as f:
        f.write(f"Instance: {problem.name}\n")
        f.write(f"Best NV: {best_res.nv}, Best TD: {best_res.td:.2f}, Cost: {best_res.cost:.2f}\n")
        f.write(f"Feasible: {best_res.feasible}\n")
        f.write("Routes:\n")
        if best_res.best_solution:
            for idx, r in enumerate(best_res.best_solution.routes, 1):
                f.write(f"  Route {idx}: 0 -> {' -> '.join(map(str, r))} -> 0\n")

    print("=" * 70)
    print(f"FINISHED {len(results)} RUNS in {t_total:.1f}s")
    print(f"Feasible: {len(feasible_results)}/{len(results)} ({feas_rate*100:.1f}%)")
    print(f"Best NV: {best_res.nv}, Best TD: {best_res.td:.2f}")
    print(f"Mean NV: {mean_nv:.2f}, Mean TD: {mean_td:.2f}")
    print(f"Results written to: {out_dir}")
    print("=" * 70)


if __name__ == "__main__":
    main()
