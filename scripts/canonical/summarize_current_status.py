import csv
from pathlib import Path
from collections import Counter

csv_path = Path("D:/Project/PH-SHOWOA/outputs/ph_showoa_canonical_results.csv")
if not csv_path.exists():
    print("CSV not found.")
    exit(0)

counts = Counter()
feas_counts = Counter()
total_rows = 0

with open(csv_path, mode="r", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    for row in reader:
        inst = row["instance"]
        counts[inst] += 1
        if row.get("feasible", "True") in ("True", "1", "true"):
            feas_counts[inst] += 1
        total_rows += 1

print(f"Total Harvested Runs: {total_rows}")
print(f"Total Unique Instances: {len(counts)}/65")
print(f"Overall Feasibility: {sum(feas_counts.values())}/{total_rows} ({sum(feas_counts.values())/max(1, total_rows)*100:.2f}%)")

completed = [inst for inst, c in sorted(counts.items()) if c >= 30]
partial = [inst for inst, c in sorted(counts.items()) if c < 30]

print(f"\n--- Fully Completed Instances (30/30 runs) [{len(completed)} instances] ---")
for inst in completed:
    print(f"  {inst:10s}: {counts[inst]}/30 runs (feas: {feas_counts[inst]})")

print(f"\n--- In-Progress / Partial Instances [{len(partial)} instances] ---")
for inst in partial:
    print(f"  {inst:10s}: {counts[inst]}/30 runs (feas: {feas_counts[inst]})")
