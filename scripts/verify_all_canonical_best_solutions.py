from __future__ import annotations

import csv
import json
import os
import glob
from pathlib import Path
import sys

# Ensure workspace is on path
WORKSPACE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKSPACE))

from src_canonical.problem import Problem
from src_canonical.solution import Solution
from src_canonical.algorithm9_feasibility import check_feasibility_canonical


def main():
    targets_file = WORKSPACE / "tests" / "paper_performance_targets.csv"
    if not targets_file.exists():
        print(f"Error: {targets_file} not found")
        return

    with open(targets_file, "r", encoding="utf-8") as f:
        targets = list(csv.DictReader(f))

    print(f"Loaded {len(targets)} targets from {targets_file}")

    import sys
    canonical_out_dir = Path("D:/Project/Kaggle/output_canonical_v2")
    if len(sys.argv) > 1:
        canonical_out_dir = Path(sys.argv[1])
    elif not canonical_out_dir.exists():
        canonical_out_dir = Path("D:/Project/Kaggle/output_canonical")
    results = []

    verified_count = 0
    better_nv = 0
    equal_nv = 0
    worse_nv = 0
    better_cost = 0
    worse_cost = 0

    for row in targets:
        inst = row["instance"]
        prob_path = WORKSPACE / row["path"]
        target_nv = int(row["target_vehicles"])
        target_td = float(row["target_distance"])
        target_cost = 2000.0 * target_nv + target_td
        table_num = row.get("table", "")

        # Find best_solution.txt and runs.csv
        inst_dir = canonical_out_dir / inst
        best_sol_files = list(inst_dir.glob("**/best_solution.txt"))
        runs_files = list(inst_dir.glob("**/runs.csv"))

        if not best_sol_files:
            print(f"WARNING: No best_solution.txt found for {inst}")
            continue

        best_sol_path = best_sol_files[0]
        runs_path = runs_files[0] if runs_files else None

        # Parse best_solution.txt
        routes = []
        best_txt_nv = None
        best_txt_td = None
        best_txt_cost = None

        with open(best_sol_path, "r", encoding="utf-8") as f:
            for line in f:
                line_str = line.strip()
                if line_str.startswith("Best NV:"):
                    # Best NV: 11, Best TD: 1109.50, Cost: 23109.50
                    parts = line_str.split(",")
                    for p in parts:
                        p = p.strip()
                        if p.startswith("Best NV:"):
                            best_txt_nv = int(p.split(":")[1])
                        elif p.startswith("Best TD:"):
                            best_txt_td = float(p.split(":")[1])
                        elif p.startswith("Cost:"):
                            best_txt_cost = float(p.split(":")[1])
                elif "Route " in line_str and "->" in line_str:
                    route_part = line_str.split(":", 1)[1]
                    nodes = [int(x.strip()) for x in route_part.split("->") if x.strip()]
                    custs = [x for x in nodes if x != 0]
                    if custs:
                        routes.append(custs)

        # Parse runs.csv to get the matching run and seed
        best_run_info = {}
        if runs_path and runs_path.exists():
            with open(runs_path, "r", encoding="utf-8") as f:
                runs = list(csv.DictReader(f))
                # Matching run
                matches = [
                    r for r in runs
                    if int(r["NV"]) == len(routes) and abs(float(r["TD"]) - best_txt_td) < 1e-1
                ]
                if matches:
                    best_run_info = matches[0]
                else:
                    # fallback to argmin
                    best_run_info = min(runs, key=lambda x: (int(x["NV"]), float(x["TD"])))

        # Load problem and verify
        prob = Problem.load(prob_path)
        sol = Solution(routes, prob)

        # Independent feasibility check
        is_feasible, violation_msg = check_feasibility_canonical(sol, prob)

        # Double check exact values
        calc_nv = sol.nv
        calc_td = round(sol.td, 2)
        calc_cost = round(sol.cost, 2)

        if is_feasible:
            verified_count += 1
        else:
            print(f"FEASIBILITY VIOLATION on {inst}: {violation_msg}")

        # Metrics comparison
        diff_nv = calc_nv - target_nv
        pct_td = ((calc_td - target_td) / target_td) * 100.0
        pct_cost = ((calc_cost - target_cost) / target_cost) * 100.0

        if diff_nv < 0:
            better_nv += 1
        elif diff_nv == 0:
            equal_nv += 1
        else:
            worse_nv += 1

        if calc_cost <= target_cost:
            better_cost += 1
        else:
            worse_cost += 1

        # Format routes for export
        routes_formatted = [[0] + r + [0] for r in routes]

        # Categorize
        if inst.startswith("RCdp100") or inst.startswith("RCdp250") or inst.startswith("RCdp500"):
            category = "Small (Wang & Chen)"
        elif inst.startswith("Cdp1"):
            category = "Medium C1 (Clustered, Short TW)"
        elif inst.startswith("Cdp2"):
            category = "Medium C2 (Clustered, Long TW)"
        elif inst.startswith("Rdp1"):
            category = "Medium R1 (Random, Short TW)"
        elif inst.startswith("Rdp2"):
            category = "Medium R2 (Random, Long TW)"
        elif inst.startswith("RCdp1"):
            category = "Medium RC1 (Mixed, Short TW)"
        elif inst.startswith("RCdp2"):
            category = "Medium RC2 (Mixed, Long TW)"
        else:
            category = "Other"

        record = {
            "instance": inst,
            "category": category,
            "table": table_num,
            "target": {
                "nv": target_nv,
                "td": target_td,
                "cost": target_cost
            },
            "canonical_best": {
                "nv": calc_nv,
                "td": calc_td,
                "cost": calc_cost,
                "run": int(best_run_info.get("run", -1)),
                "seed": int(best_run_info.get("seed", -1)),
                "elapsed_seconds": float(best_run_info.get("elapsed_seconds", 0.0))
            },
            "comparison": {
                "diff_nv": diff_nv,
                "pct_td": round(pct_td, 2),
                "pct_cost": round(pct_cost, 2),
                "cost_status": "BEAT_OR_EQUAL" if calc_cost <= target_cost else "HIGHER_COST",
                "nv_status": "FEWER_VEHICLES" if diff_nv < 0 else ("EQUAL_VEHICLES" if diff_nv == 0 else "MORE_VEHICLES")
            },
            "feasibility": {
                "is_feasible": is_feasible,
                "violation_msg": violation_msg
            },
            "routes": routes_formatted
        }
        results.append(record)

    print(f"\nVerification finished: {verified_count}/{len(results)} solutions are strictly feasible!")
    print(f"Fleet comparison: {better_nv} better (<), {equal_nv} equal (=), {worse_nv} worse (>)")
    print(f"Hierarchical Cost comparison: {better_cost} <= target, {worse_cost} > target")

    # Save to JSON
    out_json = WORKSPACE / "outputs" / "canonical_best_solutions_verified.json"
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"Saved verified JSON to: {out_json}")

    # Save to CSV
    out_csv = WORKSPACE / "outputs" / "canonical_best_solutions_summary.csv"
    with open(out_csv, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "instance", "category", "table",
            "paper_NV", "paper_TD", "paper_cost",
            "canon_NV", "canon_TD", "canon_cost",
            "diff_NV", "gap_TD_pct", "gap_cost_pct",
            "best_seed", "best_run", "is_feasible", "violation_msg"
        ])
        for r in results:
            writer.writerow([
                r["instance"], r["category"], r["table"],
                r["target"]["nv"], r["target"]["td"], r["target"]["cost"],
                r["canonical_best"]["nv"], r["canonical_best"]["td"], r["canonical_best"]["cost"],
                r["comparison"]["diff_nv"], r["comparison"]["pct_td"], r["comparison"]["pct_cost"],
                r["canonical_best"]["seed"], r["canonical_best"]["run"],
                r["feasibility"]["is_feasible"], r["feasibility"]["violation_msg"]
            ])
    print(f"Saved summary CSV to: {out_csv}")


if __name__ == "__main__":
    main()
