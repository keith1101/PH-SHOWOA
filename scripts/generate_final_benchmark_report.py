import csv
import sys
from pathlib import Path
from statistics import mean

PROJECT_ROOT = Path("D:/Project/PH-SHOWOA")
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
from update_google_sheet_pop30 import parse_all_runs, SHEET_INSTANCES

TARGETS_CSV = PROJECT_ROOT / "tests" / "paper_performance_targets.csv"

def load_paper_targets():
    targets = {}
    if not TARGETS_CSV.exists():
        return targets
    with open(TARGETS_CSV, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            inst = row["instance"]
            targets[inst.lower()] = {
                "instance": inst,
                "target_vehicles": float(row["target_vehicles"]),
                "target_distance": float(row["target_distance"]),
                "size": int(row.get("size", 100)),
                "table": int(row.get("table", 0))
            }
    return targets

def format_sec(sec):
    s = int(round(sec))
    h = s // 3600
    m = (s % 3600) // 60
    s = s % 60
    if h > 0:
        return f"{h}h{m:02d}m{s:02d}s"
    elif m > 0:
        return f"{m}m{s:02d}s"
    else:
        return f"{s}s"

def main():
    records = parse_all_runs()
    targets = load_paper_targets()
    
    print("\n" + "="*115)
    print(f"{'INSTANCE':<10} | {'RUNS':<5} | {'OUR NV':<8} | {'P-NV':<6} | {'OUR TD':<10} | {'P-TD':<10} | {'DIFF TD (%)':<12} | {'AVG TIME':<10} | {'STATUS':<10}")
    print("="*115)
    
    report_rows = []
    
    for inst in SHEET_INSTANCES:
        runs = records.get(inst, {})
        n_runs = len(runs)
        
        nvs = [r[0] for r in runs.values()]
        tds = [r[1] for r in runs.values()]
        times = [r[2] for r in runs.values()]
        
        mean_nv = mean(nvs) if nvs else 0
        min_nv = min(nvs) if nvs else 0
        mean_td = mean(tds) if tds else 0
        min_td = min(tds) if tds else 0
        avg_time = mean(times) if times else 0
        
        target_info = targets.get(inst.lower(), {})
        p_nv = target_info.get("target_vehicles", None)
        p_td = target_info.get("target_distance", None)
        
        if p_td is not None and p_td > 0:
            diff_td = ((mean_td - p_td) / p_td) * 100.0
            diff_td_str = f"{diff_td:+.2f}%"
        else:
            diff_td_str = "N/A"
            
        p_nv_str = f"{p_nv:.0f}" if p_nv is not None else "N/A"
        p_td_str = f"{p_td:.2f}" if p_td is not None else "N/A"
        
        status = "COMPLETED" if n_runs >= 30 else f"INC ({n_runs}/30)"
        
        print(f"{inst:<10} | {n_runs:<5} | {mean_nv:<8.2f} | {p_nv_str:<6} | {mean_td:<10.2f} | {p_td_str:<10} | {diff_td_str:<12} | {format_sec(avg_time):<10} | {status:<10}")
        
        report_rows.append({
            "instance": inst,
            "runs": n_runs,
            "our_mean_nv": round(mean_nv, 2),
            "our_min_nv": round(min_nv, 2),
            "paper_nv": p_nv,
            "our_mean_td": round(mean_td, 2),
            "our_min_td": round(min_td, 2),
            "paper_td": p_td,
            "diff_td_pct": round(diff_td, 2) if p_td else None,
            "avg_time_sec": round(avg_time, 2),
            "avg_time_str": format_sec(avg_time),
            "status": status
        })
        
    print("="*115)
    
    out_csv = PROJECT_ROOT / "outputs" / "final_benchmark_summary_65instances.csv"
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(report_rows[0].keys()))
        writer.writeheader()
        writer.writerows(report_rows)
        
    print(f"\nFinal report saved to: {out_csv}")

if __name__ == "__main__":
    main()
