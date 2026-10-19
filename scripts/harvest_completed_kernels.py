import os
import subprocess
from pathlib import Path

KAGGLE_EXE = r"C:\Users\LENOVO\miniconda3\envs\phshowoa\Scripts\kaggle.exe"
CREDS_ROOT = Path(r"D:\Project\Kaggle\credentials")
OUTPUT_ROOT = Path(r"D:\Project\Kaggle\output")

JOBS = [
    # account, owner, instance, seeds
    ("account-b", "kanhan162", "Cdp202", [42, 48, 54, 60, 66]),
    ("account-c", "dautromduoicuop", "Cdp203", [42, 48, 54, 60, 66]),
    ("account-d", "keith1101", "Cdp205", [42, 48, 54, 60, 66]),
    ("account-e", "giahaohuynh", "Cdp208", [42, 48, 54, 60, 66]),
]

print("=== Harvesting completed kernel outputs from accounts B, C, D, E ===")
for acc, owner, inst, seeds in JOBS:
    env = os.environ.copy()
    env["KAGGLE_CONFIG_DIR"] = str(CREDS_ROOT / acc)
    
    inst_dir = OUTPUT_ROOT / inst.lower()
    inst_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"\n[{acc} - {owner} - {inst}] -> Saving to {inst_dir}")
    for s in seeds:
        slug = f"ph-showoa-pop30-{inst.lower()}-s{s}-n6"
        target_subfolder = inst_dir / slug
        target_subfolder.mkdir(parents=True, exist_ok=True)
        
        cmd = [KAGGLE_EXE, "kernels", "output", f"{owner}/{slug}", "-p", str(target_subfolder)]
        res = subprocess.run(cmd, env=env, capture_output=True, text=True)
        print(f"  {slug}: {res.stdout.strip()} (err: {res.stderr.strip()})")

print("\nHarvest complete.")
