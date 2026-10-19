from __future__ import annotations

import csv
import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src_paper_literal.problem import Problem
from src_paper_literal.algorithm1_solver import PHSHOWOASolver, SolverConfig
from src_paper_literal.cli import CSV_COLUMNS


def run_smoke_test() -> None:
    print("=== RUNNING PAPER-LITERAL LOCAL SMOKE TEST ===")
    inst_path = PROJECT_ROOT / "data" / "Wang_Chen" / "RCdp1001.txt"
    if not inst_path.is_file():
        inst_path = PROJECT_ROOT / "data" / "RCdp" / "RCdp1001.txt"
    if not inst_path.is_file():
        raise FileNotFoundError(f"RCdp1001 instance not found at {inst_path}")

    problem = Problem.load(inst_path)
    print(f"Loaded problem: {problem.name} ({problem.num_customers} customers)")

    config = SolverConfig(
        pop_size=10,
        max_iter=5,
        seed=42,
        local_search_interval=2,
        workers=1,
    )
    solver = PHSHOWOASolver(problem, config)
    res = solver.solve(run_index=1)

    print("\nSmoke test run finished:")
    print(f"  Instance       : {res.instance}")
    print(f"  Algorithm      : {res.algo}")
    print(f"  Run            : {res.run}")
    print(f"  NV             : {res.nv}")
    print(f"  TD             : {res.td:.2f}")
    print(f"  Cost           : {res.cost:.2f}")
    print(f"  Feasible       : {res.feasible}")
    print(f"  Violation Note : {res.violation_note}")
    print(f"  Elapsed        : {res.elapsed_seconds:.2f}s")

    # Assertions
    assert res.algo == "PH-SHOWOA-PaperLiteral"
    assert res.nv >= 1
    assert res.td > 0.0
    assert abs(res.cost - (2000.0 * res.nv + res.td)) < 1e-4

    # Verify CSV output
    out_csv = PROJECT_ROOT / "outputs" / "smoke_test_paper_literal.csv"
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(CSV_COLUMNS)
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

    print(f"\nWritten result to: {out_csv}")
    with open(out_csv, "r", encoding="utf-8") as f:
        reader = list(csv.reader(f))
        assert reader[0] == CSV_COLUMNS
        assert len(reader) == 2
        print(f"Header: {reader[0]}")
        print(f"Row 1 : {reader[1]}")

    print("\n[OK] Smoke test completed successfully!")


if __name__ == "__main__":
    run_smoke_test()
