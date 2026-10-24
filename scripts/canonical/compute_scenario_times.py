import sys
from pathlib import Path
from collections import defaultdict
import numpy as np

sys.path.insert(0, 'D:/Project/PH-SHOWOA/scripts/canonical')
from prepare_and_dispatch_canonical_65slots import compute_balanced_allocations

allocations = compute_balanced_allocations()

# Load exact times from V2 and V3
v2_root = Path("D:/Project/Kaggle/output_canonical_v2")
v2_times = defaultdict(list)
for p in v2_root.rglob("runs.csv"):
    with open(p, "r", encoding="utf-8") as f:
        import csv
        reader = csv.DictReader(f)
        for r in reader:
            v2_times[r["instance"]].append(float(r["elapsed_seconds"]))

v3_root = Path("D:/Project/Kaggle/output_canonical_v3")
v3_times = defaultdict(list)
if v3_root.exists():
    for p in v3_root.rglob("runs.csv"):
        with open(p, "r", encoding="utf-8") as f:
            import csv
            reader = csv.DictReader(f)
            for r in reader:
                v3_times[r["instance"]].append(float(r["elapsed_seconds"]))

# Speedup ratio:
v3_ratios = [np.mean(v3_times[k]) / np.mean(v2_times[k]) for k in v3_times]
speedup = np.mean(v3_ratios)

# Total CPU Time
total_v2_sec = sum(sum(v) for v in v2_times.values())
total_v2_hours = total_v2_sec / 3600.0

total_v3_est_sec = total_v2_sec * speedup
total_v3_est_hours = total_v3_est_sec / 3600.0

# 65 Slots statistics
slot_secs = [a["est_sec"] * speedup for a in allocations]
slot_mins = [s / 60.0 for s in slot_secs]

mean_slot = np.mean(slot_mins)
min_slot = np.min(slot_mins)
max_slot = np.max(slot_mins)
std_slot = np.std(slot_mins)

print("=== STATS ===")
print(f"Total V2 CPU: {total_v2_hours:.2f} h ({total_v2_sec:,.1f} s)")
print(f"Total V3 CPU (at {speedup:.3f}x): {total_v3_est_hours:.2f} h ({total_v3_est_sec:,.1f} s)")
print(f"Slot duration: Mean={mean_slot:.1f}m, Min={min_slot:.1f}m, Max={max_slot:.1f}m, Std={std_slot:.1f}m")

# Wave 1 status at current time (elapsed ~100 min):
# 16 slots complete (elapsed 70-95 min)
# 34 slots running (at ~100 min mark, max slot is ~94 min V3 adjusted, meaning they are within minutes of finishing!)
# 2 slots recently pushed (Slot 39, 54): will take ~88-90 min. Finish at ~100 + 90 = 190 min (~02:25).
# 15 pending slots:
# If pending slots wait for their own accounts (Account E, F, M, Default):
# Account E: Slots 18, 19 (93.8 min). Will finish at ~100 + 94 = ~194 min (~02:30).
# Account F: Slots 20-24 (93.2 min). If starts after current jobs finish (in ~15-20 min): finishes at ~20 + 93 = ~113 min from now (~02:48).
# Account M: Slots 55-59 (87.8 min). If starts after current jobs finish.
# Account Default: Slots 62-64 (93.3 min).

# If re-allocated to FREE accounts (Account B, C, D) right now:
# 15 pending slots divided among Account B (5 slots), Account C (5 slots), Account D (5 slots):
# ALL 15 SLOTS RUN CONCURRENTLY IN PARALLEL!
# Duration = max(pending slot) = ~93.8 min (~1h34m)!
# Everything completes at: 00:58 + 94 min = 02:32!
