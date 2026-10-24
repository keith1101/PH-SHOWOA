import subprocess, sys
sys.path.insert(0, 'D:/Project/PH-SHOWOA/scripts/canonical')
from prepare_and_dispatch_canonical_65slots import build_allocations, get_kaggle_env

KAGGLE_EXE = r'C:\Users\LENOVO\miniconda3\envs\phshowoa\Scripts\kaggle.exe'
old_allocs = build_allocations()

target_accs = {'default', 'account-e', 'account-f', 'account-m'}
for job in old_allocs:
    acc = job['account']
    if acc in target_accs:
        ref = f"{job['owner']}/{job['slug']}"
        env = get_kaggle_env(acc)
        res = subprocess.run([KAGGLE_EXE, 'kernels', 'status', ref], env=env, capture_output=True, text=True)
        out = (res.stdout + res.stderr).strip()
        print(f"{acc:10s} | {ref:40s} -> {out}")
