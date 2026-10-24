import subprocess, sys
sys.path.insert(0, 'D:/Project/PH-SHOWOA/scripts/canonical')
from prepare_and_dispatch_canonical_65slots import compute_balanced_allocations, get_kaggle_env

KAGGLE_EXE = r'C:\Users\LENOVO\miniconda3\envs\phshowoa\Scripts\kaggle.exe'
allocations = compute_balanced_allocations()

sids = [18, 19, 20, 21, 22, 23, 24, 55, 56, 57, 58, 59, 62, 63, 64]
for sid in sids:
    a = allocations[sid]
    ref = f"{a['owner']}/{a['slug']}"
    env = get_kaggle_env(a['account'])
    res = subprocess.run([KAGGLE_EXE, 'kernels', 'status', ref], env=env, capture_output=True, text=True)
    out = (res.stdout + res.stderr).strip()
    print(f"Slot {sid:02d} | {ref:35s} -> {out}")
