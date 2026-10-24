import csv
from pathlib import Path
from collections import defaultdict
import numpy as np

# 1. Load exact empirical data from output_canonical_v2 (1,950 runs)
v2_root = Path("D:/Project/Kaggle/output_canonical_v2")
times_by_inst = defaultdict(list)
for p in v2_root.rglob("runs.csv"):
    with open(p, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            times_by_inst[r["instance"]].append(float(r["elapsed_seconds"]))

# 2. Check current output_canonical_v3 (runs harvested in current run)
v3_root = Path("D:/Project/Kaggle/output_canonical_v3")
v3_times_by_inst = defaultdict(list)
v3_harvested_slots = set()
if v3_root.exists():
    for p in v3_root.rglob("runs.csv"):
        v3_harvested_slots.add(p.parent.parent.name)
        with open(p, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for r in reader:
                v3_times_by_inst[r["instance"]].append(float(r["elapsed_seconds"]))

print("===============================================================================")
print("EMPIRICAL RUNTIME DATA SUMMARY (from 1,950 baseline runs in output_canonical_v2)")
print("===============================================================================")

groups = {
    "Small (9 insts)": ["RCdp1001", "RCdp1004", "RCdp1007", "RCdp2501", "RCdp2504", "RCdp2507", "RCdp5001", "RCdp5004", "RCdp5007"],
    "Type 1 Cdp (9 insts)": [f"Cdp10{i}" for i in range(1, 10)],
    "Type 1 RCdp (8 insts)": [f"RCdp10{i}" for i in range(1, 9)],
    "Type 1 Rdp (12 insts)": [f"Rdp10{i}" for i in range(1, 10)] + ["Rdp110", "Rdp111", "Rdp112"],
    "Type 2 Cdp (8 insts)": [f"Cdp20{i}" for i in range(1, 9)],
    "Type 2 RCdp (8 insts)": [f"RCdp20{i}" for i in range(1, 9)],
    "Type 2 Rdp (11 insts)": [f"Rdp20{i}" for i in range(1, 10)] + ["Rdp210", "Rdp211"],
}

total_benchmark_sec = 0.0
for gname, inst_list in groups.items():
    g_secs = []
    for inst in inst_list:
        v = times_by_inst[inst]
        g_secs.extend(v)
        total_benchmark_sec += sum(v)
    mean_s = np.mean(g_secs)
    std_s = np.std(g_secs)
    min_s = np.min(g_secs)
    max_s = np.max(g_secs)
    total_g_hours = sum(g_secs) / 3600.0
    print(f"{gname:25s} | Runs: {len(g_secs):4d} | Mean: {mean_s:6.1f}s | Min-Max: [{min_s:5.1f}s - {max_s:5.1f}s] | Total: {total_g_hours:5.2f} CPU-h")

print(f"\nTOTAL BENCHMARK CPU TIME (65 insts x 30 runs = 1,950 runs):")
print(f"  In seconds: {total_benchmark_sec:,.1f} s")
print(f"  In hours  : {total_benchmark_sec/3600.0:,.2f} CPU Hours")

# 3. Check V3 actual runtimes comparison (Direction B vs Direction A)
if v3_times_by_inst:
    print("\n-------------------------------------------------------------------------------")
    print(f"DIRECTION B ACTUAL MEASURED TIMES IN CURRENT RUN (V3: {sum(len(v) for v in v3_times_by_inst.values())} runs harvested)")
    print("-------------------------------------------------------------------------------")
    ratios = []
    for inst, v3_times in sorted(v3_times_by_inst.items()):
        v2_mean = np.mean(times_by_inst[inst])
        v3_mean = np.mean(v3_times)
        ratio = v3_mean / max(1e-5, v2_mean)
        ratios.append(ratio)
        print(f"  {inst:10s} | V2 Baseline: {v2_mean:6.1f}s | V3 Current: {v3_mean:6.1f}s | Ratio: {ratio:5.2f}x (N={len(v3_times)})")
    print(f"Overall Speed Ratio (V3 / V2): {np.mean(ratios):.3f}x")
