import subprocess, sys
from pathlib import Path
sys.path.insert(0, 'D:/Project/PH-SHOWOA/scripts/canonical')
from prepare_and_dispatch_canonical_65slots import get_kaggle_env

KAGGLE_EXE = r'C:\Users\LENOVO\miniconda3\envs\phshowoa\Scripts\kaggle.exe'
stop_root = Path('D:/Project/PH-SHOWOA/build_jobs_canonical/_stop_jobs')

for acc_dir in sorted(stop_root.iterdir()):
    if not acc_dir.is_dir():
        continue
    acc = acc_dir.name
    env = get_kaggle_env(acc)
    for job_dir in sorted(acc_dir.iterdir()):
        if not job_dir.is_dir():
            continue
        slug = job_dir.name
        # Read owner from kernel-metadata.json
        meta_file = job_dir / 'kernel-metadata.json'
        if meta_file.exists():
            import json
            meta = json.loads(meta_file.read_text(encoding='utf-8'))
            owner = meta.get('id', '').split('/')[0]
            ref = f"{owner}/{slug}"
            res = subprocess.run([KAGGLE_EXE, 'kernels', 'status', ref], env=env, capture_output=True, text=True)
            out = (res.stdout + res.stderr).strip()
            print(f"{acc:10s} | {ref:40s} -> {out}")
