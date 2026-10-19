from __future__ import annotations

import argparse
import csv
import sys
import time
from pathlib import Path
from typing import List

from .problem import Problem
from .algorithm1_solver import PHSHOWOASolver, SolverConfig, RunResult


CSV_COLUMNS = [
    "instance",
    "algo",
    "run",
    "NV",
    "TD",
    "cost",
    "feasible",
    "violation_note",
]


def parse_args(argv: List[str] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Paper-Literal PH-SHOWOA Solver for VRPSPDTW (Nguyen et al., 2026)"
    )
    parser.add_argument(
        "--instance",
        type=str,
        required=True,
        help="Path or instance name to solve (e.g. data/Wang_Chen/RCdp1001.txt or RCdp1001)",
    )
    parser.add_argument(
        "--data_root",
        type=Path,
        default=Path("data/Wang_Chen"),
        help="Root directory for instances if only instance name is given",
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=1,
        help="Number of independent runs (seeds: seed_start .. seed_start + runs - 1)",
    )
    parser.add_argument(
        "--seed_start",
        type=int,
        default=42,
        help="First random seed (default: 42)",
    )
    parser.add_argument(
        "--pop_size",
        type=int,
        default=30,
        help="Population size (paper default: 30)",
    )
    parser.add_argument(
        "--max_iter",
        type=int,
        default=1000,
        help="Maximum iterations (paper default: 1000)",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Parallel worker threads for population updates",
    )
    parser.add_argument(
        "--output_csv",
        type=Path,
        default=None,
        help="CSV file to append or write run results",
    )
    return parser.parse_args(argv)


def resolve_instance_path(instance_arg: str, data_root: Path) -> Path:
    p = Path(instance_arg)
    if p.is_file():
        return p

    name = instance_arg.strip()
    name_low = name.lower()

    candidates = [
        data_root / name,
        data_root / name_low,
        data_root / f"{name}.txt",
        data_root / f"{name_low}.txt",
        data_root / f"{name}.vrpsdptw",
        data_root / f"{name_low}.vrpsdptw",
        data_root / f"explicit_{name}.vrpsdptw",
        data_root / f"explicit_{name_low}.vrpsdptw",
        data_root / "Wang_Chen" / f"{name}.txt",
        data_root / "Wang_Chen" / f"{name_low}.txt",
        data_root / "Wang_Chen" / f"explicit_{name_low}.vrpsdptw",
        Path("data/Wang_Chen") / f"{name}.txt",
        Path("data/Wang_Chen") / f"{name_low}.txt",
        Path("data/Wang_Chen") / f"explicit_{name_low}.vrpsdptw",
        Path("data/RCdp") / f"{name}.txt",
        Path("data/RCdp") / f"{name_low}.txt",
        Path("data/RCdp") / f"{name}.vrpsdptw",
        Path("data/RCdp") / f"{name_low}.vrpsdptw",
    ]
    for cand in candidates:
        if cand.is_file():
            return cand

    raise FileNotFoundError(f"Could not resolve instance: {instance_arg}")


def run_solver(args: argparse.Namespace) -> List[RunResult]:
    inst_path = resolve_instance_path(args.instance, args.data_root)
    problem = Problem.load(inst_path)
    print(f"Loaded instance {problem.name} from {inst_path} ({problem.num_customers} customers, capacity {problem.capacity})")

    results: List[RunResult] = []

    for run_idx in range(1, args.runs + 1):
        seed = args.seed_start + run_idx - 1
        config = SolverConfig(
            pop_size=args.pop_size,
            max_iter=args.max_iter,
            seed=seed,
            workers=args.workers,
        )
        solver = PHSHOWOASolver(problem, config)
        print(f"Starting run {run_idx}/{args.runs} (seed {seed}) with max_iter={args.max_iter}, pop_size={args.pop_size}...")
        res = solver.solve(run_index=run_idx)
        results.append(res)
        print(
            f"Run {run_idx:2d} finished in {res.elapsed_seconds:.2f}s | "
            f"NV={res.nv} | TD={res.td:.2f} | Cost={res.cost:.2f} | "
            f"Feasible={res.feasible} | Note='{res.violation_note}'"
        )

    # Write CSV if requested
    if args.output_csv is not None:
        args.output_csv.parent.mkdir(parents=True, exist_ok=True)
        write_header = not args.output_csv.exists() or args.output_csv.stat().st_size == 0
        with open(args.output_csv, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            if write_header:
                writer.writerow(CSV_COLUMNS)
            for r in results:
                writer.writerow([
                    r.instance,
                    r.algo,
                    r.run,
                    r.nv,
                    f"{r.td:.2f}",
                    f"{r.cost:.2f}",
                    r.feasible,
                    r.violation_note,
                ])
        print(f"Appended {len(results)} rows to {args.output_csv}")

    return results


def main() -> None:
    args = parse_args()
    run_solver(args)


if __name__ == "__main__":
    main()
