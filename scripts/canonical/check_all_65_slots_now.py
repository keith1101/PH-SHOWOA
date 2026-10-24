import subprocess, sys
from pathlib import Path

sys.path.insert(0, 'D:/Project/PH-SHOWOA/scripts/canonical')
from prepare_and_dispatch_canonical_65slots import compute_balanced_allocations, get_kaggle_env

KAGGLE_EXE = r'C:\Users\LENOVO\miniconda3\envs\phshowoa\Scripts\kaggle.exe'
allocations = compute_balanced_allocations()

status_counts = {}
slots_by_status = {}

for a in allocations:
    sid = a["slot_id"]
    slug = a["slug"]
    acc = a["account"]
    owner = a["owner"]
    ref = f"{owner}/{slug}"
    env = get_kaggle_env(acc)
    
    res = subprocess.run([KAGGLE_EXE, "kernels", "status", ref], env=env, capture_output=True, text=True)
    out = (res.stdout + res.stderr).strip()
    
    if "COMPLETE" in out:
        st = "COMPLETE"
    elif "RUNNING" in out:
        st = "RUNNING"
    elif "QUEUED" in out:
        st = "QUEUED"
    elif "404" in out or "Not Found" in out:
        st = "UNPUSHED (404)"
    else:
        st = f"OTHER: {out[:30]}"
        
    status_counts[st] = status_counts.get(st, 0) + 1
    slots_by_status.setdefault(st, []).append((sid, ref))

print("===============================================================================")
print(f"SLOT STATUS BREAKDOWN (Total: {len(allocations)} slots)")
print("===============================================================================")
for st, cnt in sorted(status_counts.items()):
    print(f"  {st:20s}: {cnt}")

print("\n--- Details of NON-COMPLETE slots ---")
for st, slots in slots_by_status.items():
    if st != "COMPLETE":
        print(f"\nStatus: {st} ({len(slots)} slots):")
        for sid, ref in slots:
            print(f"  Slot {sid:02d}: {ref}")
