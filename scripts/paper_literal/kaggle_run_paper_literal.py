from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
from pathlib import Path
from typing import List

# Setup sys.path so src_paper_literal is importable
# Check current dir, /kaggle/working, /kaggle/input, etc.
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

from src_paper_literal.problem import Problem
from src_paper_literal.algorithm1_solver import PHSHOWOASolver, SolverConfig, RunResult
from src_paper_literal.cli import CSV_COLUMNS


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run Paper-Literal PH-SHOWOA on Kaggle"
    )
    parser.add_argument("--instance", type=str, required=True, help="Instance name (e.g. RCdp1001)")
    parser.add_argument("--data_root", type=Path, default=None, help="Root directory for dataset")
    parser.add_argument("--repeats", type=int, default=30, help="Number of runs (default: 30)")
    parser.add_argument("--seed_start", type=int, default=42, help="Starting random seed (default: 42)")
    parser.add_argument("--pop_size", type=int, default=30, help="Population size (default: 30)")
    parser.add_argument("--max_iter", type=int, default=1000, help="Max iterations (default: 1000)")
    parser.add_argument("--workers", type=int, default=4, help="Worker threads (default: 4)")
    default_out = Path("/kaggle/working/outputs") if Path("/kaggle/working").exists() else Path("outputs/kaggle_literal_test")
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
            data_root / "RCdp" / f"{inst}.txt",
            data_root / "RCdp" / f"{inst_low}.txt",
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
    print(f"KAGGLE PAPER-LITERAL RUNNER: {args.instance}")
    print(f"Repeats: {args.repeats} | Seed start: {args.seed_start} | Pop size: {args.pop_size} | Max iter: {args.max_iter}")
    print("=" * 70)

    inst_file = find_instance_file(args.instance, args.data_root)
    print(f"Using instance file: {inst_file}")

    problem = Problem.load(inst_file)
    problem.name = args.instance
    print(f"Loaded {problem.name}: {problem.num_customers} customers, capacity={problem.capacity}")

    out_dir = args.output_dir / args.instance
    out_dir.mkdir(parents=True, exist_ok=True)
    out_csv = out_dir / "runs.csv"

    results: List[RunResult] = []

    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(CSV_COLUMNS)

        for i in range(args.repeats):
            run_idx = i + 1
            seed = args.seed_start + i
            config = SolverConfig(
                pop_size=args.pop_size,
                max_iter=args.max_iter,
                seed=seed,
                workers=args.workers,
            )
            solver = PHSHOWOASolver(problem, config)
            res = solver.solve(run_index=run_idx)
            results.append(res)

            writer.writerow([
                res.instance,
                res.algo,
                res.run,
                res.nv,
                f"{res.td:.2f}",
                f"{res.cost:.2f}",
                res.feasible,
                res.violation_note,
            ])
            f.flush()

            print(
                f"[{run_idx:2d}/{args.repeats}] seed={seed} | "
                f"NV={res.nv} | TD={res.td:.2f} | Cost={res.cost:.2f} | "
                f"Feasible={res.feasible} | Time={res.elapsed_seconds:.2f}s"
            )

    # Write summary json
    summary = {
        "instance": args.instance,
        "algo": "PH-SHOWOA-PaperLiteral",
        "repeats": args.repeats,
        "seed_start": args.seed_start,
        "pop_size": args.pop_size,
        "max_iter": args.max_iter,
        "nv_best": min(r.nv for r in results),
        "nv_mean": sum(r.nv for r in results) / len(results),
        "td_best": min(r.td for r in results),
        "td_mean": sum(r.td for r in results) / len(results),
        "cost_best": min(r.cost for r in results),
        "cost_mean": sum(r.cost for r in results) / len(results),
        "all_feasible": all(r.feasible for r in results),
        "feasible_count": sum(1 for r in results if r.feasible),
    }
    with open(out_dir / "summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print("\n" + "=" * 70)
    print(f"FINISHED ALL {args.repeats} RUNS FOR {args.instance}")
    print(f"Results saved to: {out_csv}")
    print(f"Summary: {summary}")
    print("=" * 70)


if __name__ == "__main__":
    main()
