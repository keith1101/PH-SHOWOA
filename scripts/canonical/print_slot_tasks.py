import sys
from pathlib import Path

sys.path.insert(0, 'D:/Project/PH-SHOWOA/scripts/canonical')
from prepare_and_dispatch_canonical_65slots import compute_balanced_allocations

allocations = compute_balanced_allocations()

for a in allocations:
    sid = a["slot_id"]
    slug = a["slug"]
    acc = a["account"]
    owner = a["owner"]
    est_m = a["est_min"]
    task_desc = ", ".join([f"{t['instance']} (s{t['seed_start']} x{t['repeats']})" for t in a["tasks"]])
    print(f"Slot {sid:02d} | {acc:10s} | {owner:15s} | {est_m:5.1f}m | {task_desc}")
