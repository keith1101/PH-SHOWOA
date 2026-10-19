import csv
import sys
from pathlib import Path

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

    results = []

    print("\n" + "="*125)
    print(f"{'STT':<4} | {'INSTANCE':<10} | {'BEST NV':<8} | {'PAPER NV':<8} | {'BEST TD':<10} | {'PAPER TD':<10} | {'DIFF TD (%)':<12} | {'SEED':<6} | {'RUN TIME':<10}")
    print("="*125)

    better_or_tie_nv = 0
    better_or_tie_td = 0
    better_nv_count = 0

    for idx, inst in enumerate(SHEET_INSTANCES, 1):
        runs = records.get(inst, {})
        if not runs:
            continue

        # Lexicographical best: min NV, then min TD
        best_seed = min(runs.keys(), key=lambda s: (runs[s][0], runs[s][1]))
        best_nv, best_td, best_sec = runs[best_seed]

        target = targets.get(inst.lower(), {})
        p_nv = target.get("target_vehicles", None)
        p_td = target.get("target_distance", None)

        if p_td and p_td > 0:
            diff_td = ((best_td - p_td) / p_td) * 100.0
            diff_td_str = f"{diff_td:+.2f}%"
            if diff_td <= 0.05:
                better_or_tie_td += 1
        else:
            diff_td_str = "N/A"
            diff_td = None

        if p_nv is not None:
            if best_nv <= p_nv:
                better_or_tie_nv += 1
            if best_nv < p_nv:
                better_nv_count += 1

        p_nv_str = f"{p_nv:.0f}" if p_nv is not None else "N/A"
        p_td_str = f"{p_td:.2f}" if p_td is not None else "N/A"

        print(f"{idx:<4} | {inst:<10} | {best_nv:<8.0f} | {p_nv_str:<8} | {best_td:<10.2f} | {p_td_str:<10} | {diff_td_str:<12} | {best_seed:<6} | {format_sec(best_sec):<10}")

        results.append({
            "stt": idx,
            "instance": inst,
            "best_nv": int(best_nv),
            "paper_nv": int(p_nv) if p_nv else None,
            "best_td": round(best_td, 2),
            "paper_td": p_td,
            "diff_td_pct": round(diff_td, 2) if diff_td is not None else None,
            "best_seed": best_seed,
            "run_time_sec": round(best_sec, 2),
            "run_time_str": format_sec(best_sec)
        })

    print("="*125)
    print(f"\nSummary:")
    print(f"  - Total instances analyzed: {len(results)} / 65")
    print(f"  - Instances where PH-SHOWOA BEST NV < Paper NV (fewer vehicles): {better_nv_count} instances")
    print(f"  - Instances where PH-SHOWOA BEST NV <= Paper NV (equal or fewer): {better_or_tie_nv} / {len(results)} ({better_or_tie_nv/len(results)*100:.1f}%)")
    print(f"  - Instances where PH-SHOWOA BEST TD <= Paper TD (shorter distance): {better_or_tie_td} / {len(results)} ({better_or_tie_td/len(results)*100:.1f}%)")

    out_csv = PROJECT_ROOT / "outputs" / "best_solutions_65instances.csv"
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(results[0].keys()))
        writer.writeheader()
        writer.writerows(results)

    print(f"\nSaved CSV to: {out_csv}")

if __name__ == "__main__":
    main()
