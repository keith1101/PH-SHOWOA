from __future__ import annotations

import argparse
import base64
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, List

PROJECT_ROOT = Path("D:/Project/PH-SHOWOA")
KAGGLE_EXE = r"C:\Users\LENOVO\miniconda3\envs\phshowoa\Scripts\kaggle.exe"
CREDS_ROOT = Path("D:/Project/Kaggle/credentials")
JOBS_ROOT = PROJECT_ROOT / "build_jobs_paper_literal"

# 13 Active accounts (excluding account-a)
ACCOUNTS = [
    {"account": "account-b", "owner": "kanhan162"},
    {"account": "account-c", "owner": "dautromduoicuop"},
    {"account": "account-d", "owner": "keith1101"},
    {"account": "account-e", "owner": "giahaohuynh"},
    {"account": "account-f", "owner": "huynhkhackiet"},
    {"account": "account-g", "owner": "vochithanh"},
    {"account": "account-h", "owner": "vnguynduykhoa"},
    {"account": "account-i", "owner": "ketvong"},
    {"account": "account-j", "owner": "huybahihi"},
    {"account": "account-k", "owner": "kaigaming"},
    {"account": "account-l", "owner": "kingaminghehe"},
    {"account": "account-m", "owner": "khahccngng"},
    {"account": "default", "owner": "tafuhihi"},
]

# Exact 65 Wang & Chen instances
SHEET_INSTANCES = [
    # 9 small
    "RCdp1001", "RCdp1004", "RCdp1007",
    "RCdp2501", "RCdp2504", "RCdp2507",
    "RCdp5001", "RCdp5004", "RCdp5007",
    # 56 medium
    "RCdp101", "RCdp102", "RCdp103", "RCdp104", "RCdp105", "RCdp106", "RCdp107", "RCdp108",
    "RCdp201", "RCdp202", "RCdp203", "RCdp204", "RCdp205", "RCdp206", "RCdp207", "RCdp208",
    "Cdp101", "Cdp102", "Cdp103", "Cdp104", "Cdp105", "Cdp106", "Cdp107", "Cdp108", "Cdp109",
    "Cdp201", "Cdp202", "Cdp203", "Cdp204", "Cdp205", "Cdp206", "Cdp207", "Cdp208",
    "Rdp101", "Rdp102", "Rdp103", "Rdp104", "Rdp105", "Rdp106", "Rdp107", "Rdp108", "Rdp109", "Rdp110", "Rdp111", "Rdp112",
    "Rdp201", "Rdp202", "Rdp203", "Rdp204", "Rdp205", "Rdp206", "Rdp207", "Rdp208", "Rdp209", "Rdp210", "Rdp211"
]


def build_allocations() -> List[Dict]:
    """Partitions the 65 instances evenly into 13 accounts (5 instances each)."""
    allocations = []
    chunk_size = 5
    for acc_idx, acc in enumerate(ACCOUNTS):
        start = acc_idx * chunk_size
        end = start + chunk_size
        inst_subset = SHEET_INSTANCES[start:end]
        for inst in inst_subset:
            slug = f"ph-literal-{inst.lower()}-s42-n30"
            allocations.append({
                "account": acc["account"],
                "owner": acc["owner"],
                "instance": inst,
                "slug": slug,
                "seed_start": 42,
                "repeats": 30,
            })
    return allocations


def package_src_paper_literal_b64() -> str:
    """Creates a base64 encoded zip of src_paper_literal, runner script, and benchmark data."""
    import io
    import zipfile

    buf = io.BytesIO()
    src_dir = PROJECT_ROOT / "src_paper_literal"
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in src_dir.rglob("*.py"):
            rel = p.relative_to(PROJECT_ROOT)
            zf.write(p, arcname=str(rel).replace("\\", "/"))

        # Also pack the runner script
        runner_p = PROJECT_ROOT / "scripts" / "paper_literal" / "kaggle_run_paper_literal.py"
        if runner_p.is_file():
            zf.write(runner_p, arcname="scripts/paper_literal/kaggle_run_paper_literal.py")

        # Also pack the 65 benchmark instance files so notebooks are self-contained
        for inst in SHEET_INSTANCES:
            for fname in [f"{inst}.txt", f"{inst.lower()}.txt"]:
                inst_p = PROJECT_ROOT / "data" / "Wang_Chen" / fname
                if inst_p.is_file():
                    zf.write(inst_p, arcname=f"data/Wang_Chen/{fname}")
                    break

    return base64.b64encode(buf.getvalue()).decode("utf-8")


def generate_notebook_code(instance: str, seed_start: int, repeats: int, b64_payload: str) -> str:
    return f"""import base64
import io
import os
import sys
import zipfile
from pathlib import Path
import subprocess

print("=== SETTING UP PAPER-LITERAL SOURCE ON KAGGLE ===")
payload = \"\"\"{b64_payload}\"\"\"

zip_bytes = base64.b64decode(payload)
with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
    zf.extractall("/kaggle/working")

print("Extracted source code to /kaggle/working.")
print("Directory listing of /kaggle/working:", os.listdir("/kaggle/working"))

# Locate benchmark dataset
data_candidates = [
    Path("/kaggle/input/ph-showoa"),
    Path("/kaggle/input/datasets/keith1101/ph-showoa"),
    Path("/kaggle/input/ph-showoa/data/Wang_Chen"),
    Path("/kaggle/input/datasets/keith1101/ph-showoa/data/Wang_Chen"),
    Path("/kaggle/working/data/Wang_Chen"),
]
data_root = None
for p in data_candidates:
    if p.exists():
        data_root = p
        break

runner_script = Path("/kaggle/working/scripts/paper_literal/kaggle_run_paper_literal.py")
if not runner_script.exists():
    raise FileNotFoundError(f"Could not find runner script at {{runner_script}}")

cmd = [
    sys.executable,
    str(runner_script),
    "--instance", "{instance}",
    "--repeats", "{repeats}",
    "--seed_start", "{seed_start}",
    "--pop_size", "30",
    "--max_iter", "1000",
    "--workers", "1",
    "--output_dir", "/kaggle/working/outputs",
]
if data_root is not None:
    cmd.extend(["--data_root", str(data_root)])

print("Executing runner command:", " ".join(cmd), flush=True)
res = subprocess.run(cmd)
print(f"Runner completed with exit code: {{res.returncode}}", flush=True)
sys.exit(res.returncode)
"""


def create_job(job_dir: Path, owner: str, slug: str, instance: str, seed_start: int, repeats: int, b64_payload: str) -> None:
    job_dir.mkdir(parents=True, exist_ok=True)
    code_content = generate_notebook_code(instance, seed_start, repeats, b64_payload)

    nb = {
        "cells": [
            {
                "cell_type": "code",
                "execution_count": None,
                "metadata": {},
                "outputs": [],
                "source": [line + "\n" for line in code_content.splitlines()]
            }
        ],
        "metadata": {
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3"
            },
            "language_info": {
                "name": "python",
                "version": "3.10"
            },
            "kaggle": {
                "accelerator": "none",
                "dataSources": [],
                "isGpuEnabled": False,
                "isInternetEnabled": False,
                "language": "python",
                "sourceType": "notebook"
            }
        },
        "nbformat": 4,
        "nbformat_minor": 4
    }

    nb_file = job_dir / f"{slug}.ipynb"
    with open(nb_file, "w", encoding="utf-8") as f:
        json.dump(nb, f, indent=2)

    meta = {
        "id": f"{owner}/{slug}",
        "title": slug,
        "code_file": f"{slug}.ipynb",
        "language": "python",
        "kernel_type": "notebook",
        "is_private": True,
        "enable_gpu": False,
        "enable_tpu": False,
        "enable_internet": False,
        "keywords": [],
        "dataset_sources": [
            "keith1101/ph-showoa"
        ],
        "kernel_sources": [],
        "competition_sources": [],
        "model_sources": []
    }
    meta_file = job_dir / "kernel-metadata.json"
    with open(meta_file, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)


def get_kaggle_env(account: str) -> Dict[str, str]:
    env = os.environ.copy()
    if account == "default":
        env["KAGGLE_CONFIG_DIR"] = str(CREDS_ROOT / "tafuhihi")
    else:
        env["KAGGLE_CONFIG_DIR"] = str(CREDS_ROOT / account)
    return env


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare and dispatch Paper-Literal PH-SHOWOA 65 slots on Kaggle")
    parser.add_argument("--push", action="store_true", help="Actually push kernels to Kaggle (default: prepare only)")
    parser.add_argument("--accounts", nargs="*", default=None, help="Specific accounts to target (e.g. account-b)")
    args = parser.parse_args()

    allocations = build_allocations()
    if args.accounts:
        target_accs = set(args.accounts)
        allocations = [a for a in allocations if a["account"] in target_accs]

    print("=" * 75)
    print(f"PREPARING PAPER-LITERAL 65-SLOT KAGGLE JOBS (Total allocations: {len(allocations)})")
    print(f"Mode: {'PUSH TO KAGGLE' if args.push else 'PREPARE ONLY (DRY-RUN)'}")
    print("=" * 75)

    print("Packing src_paper_literal into base64 payload...")
    b64_payload = package_src_paper_literal_b64()
    print(f"Payload packed: {len(b64_payload)} characters.")

    JOBS_ROOT.mkdir(parents=True, exist_ok=True)

    success = 0
    failed = 0

    for idx, item in enumerate(allocations, 1):
        account = item["account"]
        owner = item["owner"]
        slug = item["slug"]
        inst = item["instance"]
        seed = item["seed_start"]
        reps = item["repeats"]

        job_dir = JOBS_ROOT / slug
        create_job(job_dir, owner, slug, inst, seed, reps, b64_payload)

        if not args.push:
            print(f"[{idx:2d}/{len(allocations)}] Prepared {owner}/{slug} ({inst} s={seed} n={reps}) in {job_dir.name}")
            success += 1
        else:
            print(f"[{idx:2d}/{len(allocations)}] Pushing {owner}/{slug} ({inst} s={seed} n={reps}) via {account}...", flush=True)
            env = get_kaggle_env(account)
            res = subprocess.run([KAGGLE_EXE, "kernels", "push", "-p", str(job_dir)], env=env, capture_output=True, text=True)
            out_msg = (res.stdout + " " + res.stderr).lower()
            if res.returncode == 0 and ("successful" in out_msg or "kernel version" in out_msg):
                print(f"   --> SUCCESS: {res.stdout.strip()}", flush=True)
                success += 1
            else:
                print(f"   --> FAILED / MSG: {res.stdout.strip()} | {res.stderr.strip()}", flush=True)
                failed += 1

    print("\n" + "=" * 75)
    print(f"Finished: {success} succeeded, {failed} failed out of {len(allocations)} jobs.")
    print("=" * 75)


if __name__ == "__main__":
    main()
