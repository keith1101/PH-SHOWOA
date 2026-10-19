import csv
import sys
import statistics
from pathlib import Path

PROJECT_ROOT = Path("D:/Project/PH-SHOWOA")
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
from update_google_sheet_pop30 import parse_all_runs, SHEET_INSTANCES

def generate_csvs():
    records = parse_all_runs()
    outputs_dir = PROJECT_ROOT / "outputs"
    outputs_dir.mkdir(parents=True, exist_ok=True)
    
    # -------------------------------------------------------------
    # 1. SUMMARY CSV: Exactly 65 instances with Mean ± s
    # Columns: instance, algo, run, NV, TD, cost
    # -------------------------------------------------------------
    summary_file = outputs_dir / "ph_showoa_benchmark_summary.csv"
    summary_rows = []
    
    # Also prepare all runs detail rows (1950 rows)
    detail_file = outputs_dir / "ph_showoa_all_1950_runs.csv"
    detail_rows = []
    
    # Combined file with individual runs + summary row per instance
    combined_file = outputs_dir / "ph_showoa_comprehensive_runs_and_summary.csv"
    combined_rows = []
    
    for inst in SHEET_INSTANCES:
        runs = records.get(inst, {})
        n_runs = len(runs)
        if not runs:
            continue
            
        # Sort seeds deterministically
        sorted_seeds = sorted(runs.keys())
        
        nvs = [runs[s][0] for s in sorted_seeds]
        tds = [runs[s][1] for s in sorted_seeds]
        costs = [2000.0 * runs[s][0] + runs[s][1] for s in sorted_seeds]
        
        # NV formatting
        nv_avg = statistics.mean(nvs)
        nv_min, nv_max = min(nvs), max(nvs)
        if nv_min == nv_max:
            nv_str = str(int(round(nv_avg)))
        else:
            nv_std = statistics.stdev(nvs) if len(nvs) > 1 else 0.0
            nv_str = f"{nv_avg:.2f} \u00b1 {nv_std:.2f}"
            
        # TD formatting
        td_avg = statistics.mean(tds)
        td_std = statistics.stdev(tds) if len(tds) > 1 else 0.0
        td_str = f"{td_avg:.2f} \u00b1 {td_std:.2f}"
        
        # Cost formatting (cost = 2000 * NV + TD)
        cost_avg = statistics.mean(costs)
        cost_std = statistics.stdev(costs) if len(costs) > 1 else 0.0
        if cost_std == 0.0:
            cost_str = f"{cost_avg:.2f} \u00b1 0.00"
        else:
            cost_str = f"{cost_avg:.2f} \u00b1 {cost_std:.2f}"
            
        summary_rows.append({
            "instance": inst,
            "algo": "PH-SHOWOA",
            "run": n_runs,
            "NV": nv_str,
            "TD": td_str,
            "cost": cost_str
        })
        
        # Detail rows
        for run_idx, s in enumerate(sorted_seeds, 1):
            r_nv = int(runs[s][0]) if runs[s][0].is_integer() else runs[s][0]
            r_td = round(runs[s][1], 2)
            r_cost = round(2000.0 * runs[s][0] + runs[s][1], 2)
            
            d_row = {
                "instance": inst,
                "algo": "PH-SHOWOA",
                "run": run_idx,
                "seed": s,
                "NV": r_nv,
                "TD": r_td,
                "cost": r_cost
            }
            detail_rows.append(d_row)
            
            combined_rows.append({
                "instance": inst,
                "algo": "PH-SHOWOA",
                "run": str(run_idx),
                "NV": str(r_nv),
                "TD": f"{r_td:.2f}",
                "cost": f"{r_cost:.2f}"
            })
            
        combined_rows.append({
            "instance": inst,
            "algo": "PH-SHOWOA",
            "run": f"Average ({n_runs} runs)",
            "NV": nv_str,
            "TD": td_str,
            "cost": cost_str
        })

    # Write summary CSV
    with open(summary_file, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["instance", "algo", "run", "NV", "TD", "cost"])
        writer.writeheader()
        writer.writerows(summary_rows)
    print(f"Generated summary CSV (65 instances): {summary_file}")

    # Write detailed CSV
    with open(detail_file, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["instance", "algo", "run", "seed", "NV", "TD", "cost"])
        writer.writeheader()
        writer.writerows(detail_rows)
    print(f"Generated all runs CSV (1950 runs): {detail_file}")

    # Write combined CSV
    with open(combined_file, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["instance", "algo", "run", "NV", "TD", "cost"])
        writer.writeheader()
        writer.writerows(combined_rows)
    print(f"Generated combined CSV: {combined_file}")

if __name__ == "__main__":
    generate_csvs()
