import subprocess, sys, time, json
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, 'D:/Project/PH-SHOWOA/scripts/canonical')
from prepare_and_dispatch_canonical_65slots import compute_balanced_allocations, get_kaggle_env

allocations = compute_balanced_allocations()

# Check output_canonical_v3 to see which slots are downloaded
harvest_dir = Path("D:/Project/Kaggle/output_canonical_v3")
downloaded_slots = set()
for d in harvest_dir.iterdir():
    if d.is_dir() and d.name.startswith("ph-canon-slot"):
        downloaded_slots.add(d.name)

# Group allocations by account
by_account = defaultdict(list)
for a in allocations:
    by_account[a["account"]].append(a)

print(f"Total slots: {len(allocations)}")
print(f"Downloaded slots: {len(downloaded_slots)}")

# Check each account's status
account_summary = []
for acc, slots in by_account.items():
    owner = slots[0]["owner"]
    done_count = sum(1 for s in slots if s["slug"] in downloaded_slots)
    total_min = sum(s["est_min"] for s in slots)
    account_summary.append({
        "account": acc,
        "owner": owner,
        "slots": slots,
        "done": done_count,
        "total_min": total_min
    })

print("\n=== ACCOUNT BREAKDOWN ===")
for asumm in account_summary:
    slot_ids = [s["slot_id"] for s in asumm["slots"]]
    print(f"{asumm['account']:10s} ({asumm['owner']:16s}): Slots {slot_ids[0]:02d}-{slot_ids[-1]:02d} | Done: {asumm['done']}/5 | Total Slot Est: {asumm['total_min']} min")
