import sys
from pathlib import Path
from collections import defaultdict
import numpy as np

sys.path.insert(0, 'D:/Project/PH-SHOWOA/scripts/canonical')
from prepare_and_dispatch_canonical_65slots import compute_balanced_allocations

allocations = compute_balanced_allocations()

# We know the speedup factor of V3 vs V2 is 0.847
SPEEDUP = 0.847

# Harvested slots in V3
v3_root = Path("D:/Project/Kaggle/output_canonical_v3")
harvested_slots = set()
for d in v3_root.iterdir():
    if d.is_dir() and d.name.startswith("ph-canon-slot"):
        harvested_slots.add(d.name)

# Slots pushed in Wave 1 and currently RUNNING
# Total slots: 65
# Complete / Harvested: 16 slots (00, 01, 02, 03, 04, 07, 08, 09, 10, 11, 12, 13, 35, 46, 50, 60)
# Recently pushed: 39, 54
# Unpushed / Pending: 18, 19, 20, 21, 22, 23, 24, 55, 56, 57, 58, 59, 62, 63, 64 (15 slots)
# Running: all others (34 slots)

complete_slots = {0, 1, 2, 3, 4, 7, 8, 9, 10, 11, 12, 13, 35, 46, 50, 60}
pending_slots = {18, 19, 20, 21, 22, 23, 24, 55, 56, 57, 58, 59, 62, 63, 64}
just_pushed_slots = {39, 54}

# Elapsed time since Wave 1 was dispatched: ~23:15 to 00:55 = ~100 minutes.
ELAPSED_MINUTES = 100.0

print("===============================================================================")
print("EXACT ACCOUNT-BY-ACCOUNT COMPLETION TIMELINE ESTIMATE")
print("===============================================================================")

account_timelines = {}

for acc_idx in range(13):
    acc_slots = allocations[acc_idx*5 : (acc_idx+1)*5]
    acc_name = acc_slots[0]["account"]
    owner = acc_slots[0]["owner"]
    
    # Calculate finish time of running slots in Wave 1
    running_remaining = []
    pending_times = []
    
    for s in acc_slots:
        sid = s["slot_id"]
        # V3 adjusted time:
        v3_slot_min = s["est_min"] * SPEEDUP
        if sid in complete_slots:
            # Already completed
            pass
        elif sid in pending_slots:
            pending_times.append((sid, v3_slot_min))
        elif sid in just_pushed_slots:
            # Just started, remaining = v3_slot_min
            running_remaining.append((sid, v3_slot_min))
        else:
            # Running since start (elapsed ~100 min)
            rem = max(0.0, v3_slot_min - ELAPSED_MINUTES)
            running_remaining.append((sid, rem))
            
    # Max time for Wave 1 on this account to free a slot
    if running_remaining:
        wave1_finish = max(r[1] for r in running_remaining)
        wave1_first_free = min(r[1] for r in running_remaining)
    else:
        wave1_finish = 0.0
        wave1_first_free = 0.0
        
    # Wave 2 time: pending slots run when slots free up
    # In each account, there are at most 5 concurrent slots.
    # If 5 slots pending (e.g. account-f, account-m), they will start as soon as current account jobs finish.
    # The max time of pending slots:
    if pending_times:
        wave2_duration = max(p[1] for p in pending_times)
    else:
        wave2_duration = 0.0
        
    # Total finish time from now for this account:
    total_acc_remaining = wave1_finish + wave2_duration
    
    account_timelines[acc_name] = {
        "owner": owner,
        "running_slots": [r[0] for r in running_remaining],
        "pending_slots": [p[0] for p in pending_times],
        "wave1_rem_min": round(wave1_finish, 1),
        "wave2_duration_min": round(wave2_duration, 1),
        "total_remaining_min": round(total_acc_remaining, 1)
    }

for acc, data in account_timelines.items():
    print(f"{acc:10s} ({data['owner']:15s}) | Wave 1 Rem: {data['wave1_rem_min']:5.1f}m | Pending ({len(data['pending_slots'])}): {data['pending_slots']} | Wave 2: {data['wave2_duration_min']:5.1f}m | Total Remaining: {data['total_remaining_min']:5.1f}m")

max_acc = max(account_timelines.items(), key=lambda x: x[1]["total_remaining_min"])
print("-------------------------------------------------------------------------------")
print(f"BOTTLENECK ACCOUNT: {max_acc[0]} ({max_acc[1]['owner']}) with {max_acc[1]['total_remaining_min']} minutes remaining.")
