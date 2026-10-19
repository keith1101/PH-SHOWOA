import sys
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, "D:/Project/PH-SHOWOA/scripts")
from update_google_sheet_pop30 import parse_all_runs, SHEET_INSTANCES

records = parse_all_runs()

print("\n" + "="*70)
print(f"BENCHMARK STATUS OVERVIEW (Total target instances: {len(SHEET_INSTANCES)})")
print("="*70)

complete = [k for k in SHEET_INSTANCES if len(records.get(k, {})) >= 30]
incomplete = [k for k in SHEET_INSTANCES if len(records.get(k, {})) < 30]

print(f"Completed (>=30 runs): {len(complete)} / {len(SHEET_INSTANCES)} ({len(complete)/len(SHEET_INSTANCES)*100:.1f}%)")
print(f"Incomplete (<30 runs): {len(incomplete)} / {len(SHEET_INSTANCES)}")
print("-"*70)

target_seeds = set(range(42, 72))

for inst in incomplete:
    runs = records.get(inst, {})
    present = sorted(runs.keys())
    missing = sorted(list(target_seeds - set(present)))
    print(f"  {inst:10s} : {len(runs):2d}/30 runs | Missing {len(missing)} seeds: {missing}")

print("="*70)
