import subprocess, sys
from pathlib import Path

sys.path.insert(0, 'D:/Project/PH-SHOWOA/scripts/canonical')
from prepare_and_dispatch_canonical_65slots import get_kaggle_env

KAGGLE_EXE = r'C:\Users\LENOVO\miniconda3\envs\phshowoa\Scripts\kaggle.exe'
accounts = ['account-e', 'account-f', 'account-m', 'default', 'account-b', 'account-c', 'account-d']

for acc in accounts:
    env = get_kaggle_env(acc)
    print(f"=== {acc} ACTIVE BATCH SESSIONS ===")
    res = subprocess.run([KAGGLE_EXE, 'kernels', 'list', '--mine', '--sort-by', 'dateRun'], env=env, capture_output=True, text=True)
    lines = res.stdout.strip().split('\n')
    for l in lines[:7]:
        print("  ", l)
