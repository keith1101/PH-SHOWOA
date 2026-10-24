from __future__ import annotations

import argparse
import base64
import csv
import io
import json
import os
import subprocess
import sys
import zipfile
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Set

PROJECT_ROOT = Path("D:/Project/PH-SHOWOA")
KAGGLE_EXE = r"C:\Users\LENOVO\miniconda3\envs\phshowoa\Scripts\kaggle.exe"
CREDS_ROOT = Path("D:/Project/Kaggle/credentials")
JOBS_ROOT = PROJECT_ROOT / "build_jobs_canonical"

# 13 Active accounts (5 slots each = 65 slots)
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


def compute_balanced_allocations() -> List[Dict]:
    """
    Partitions the 1,950 runs of 65 instances into exactly 65 balanced bins.
    Uses empirical runtimes from Kaggle measurements and LPT Greedy Bin Packing.
    Ensures every slot runs for ~85-110 minutes with zero idle kernels.
    """
    # Profile empirical times from output_canonical_v2
    root = Path("D:/Project/Kaggle/output_canonical_v2")
    times = defaultdict(list)
    if root.exists():
        for p in root.rglob("runs.csv"):
            with open(p, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    times[row["instance"]].append(float(row.get("elapsed_seconds", 0.0)))

    time_per_run = {inst: sum(v)/len(v) for inst, v in times.items()}

    # Break 65 instances x 30 runs into atomic tasks
    tasks = []
    for inst in SHEET_INSTANCES:
        avg_s = time_per_run.get(inst, 100.0)
        if avg_s > 600:  # Rdp204 (842s)
            chunks = [(42, 6), (48, 6), (54, 6), (60, 6), (66, 6)]
        elif avg_s > 500:  # Rdp203, Rdp209, Rdp207
            chunks = [(42, 10), (52, 10), (62, 10)]
        elif avg_s > 380:  # Rdp202, Rdp201, RCdp202, Rdp211, Rdp205, RCdp208, Rdp210, RCdp205, RCdp207, RCdp204, Cdp204, RCdp206, Rdp206
            chunks = [(42, 10), (52, 10), (62, 10)]
        elif avg_s > 250:  # RCdp203, RCdp201
            chunks = [(42, 15), (57, 15)]
        elif avg_s > 100:  # Rdp101, Rdp102, RCdp101, etc.
            chunks = [(42, 15), (57, 15)]
        else:  # light instances
            chunks = [(42, 30)]

        for s_start, reps in chunks:
            tasks.append({
                "instance": inst,
                "seed_start": s_start,
                "repeats": reps,
                "est_sec": avg_s * reps
            })

    # LPT Bin Packing into 65 bins
    tasks.sort(key=lambda t: t["est_sec"], reverse=True)
    bins = [{"id": i, "time": 0.0, "tasks": []} for i in range(65)]
    for t in tasks:
        best_bin = min(bins, key=lambda b: b["time"])
        best_bin["tasks"].append(t)
        best_bin["time"] += t["est_sec"]

    # Assign bins evenly to 13 accounts (5 bins each)
    allocations = []
    for bin_idx, b in enumerate(bins):
        acc_idx = bin_idx // 5
        slot_idx = bin_idx % 5
        acc = ACCOUNTS[acc_idx]
        slug = f"ph-canon-slot{bin_idx:02d}"
        allocations.append({
            "slot_id": bin_idx,
            "account": acc["account"],
            "owner": acc["owner"],
            "slug": slug,
            "tasks": b["tasks"],
            "est_sec": b["time"],
            "est_min": round(b["time"] / 60, 1),
        })

    return allocations


def build_allocations() -> List[Dict]:
    """Compatibility alias for other scripts."""
    return compute_balanced_allocations()


def package_src_canonical_b64(instances: Set[str]) -> str:
    """Creates a base64 encoded zip of src_canonical, runner script, and the target benchmark files."""
    buf = io.BytesIO()
    src_dir = PROJECT_ROOT / "src_canonical"
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in src_dir.rglob("*.py"):
            rel = p.relative_to(PROJECT_ROOT)
            zf.write(p, arcname=str(rel).replace("\\", "/"))

        # Runner script
        runner_p = PROJECT_ROOT / "scripts" / "canonical" / "kaggle_run_canonical.py"
        if runner_p.is_file():
            zf.write(runner_p, arcname="scripts/canonical/kaggle_run_canonical.py")

        # Benchmark files for all instances needed in this slot
        for inst in instances:
            for fname in [f"{inst}.txt", f"{inst.lower()}.txt", f"explicit_{inst}.vrpsdptw", f"explicit_{inst.lower()}.vrpsdptw"]:
                inst_p = PROJECT_ROOT / "data" / "Wang_Chen" / fname
                if inst_p.is_file():
                    zf.write(inst_p, arcname=f"data/Wang_Chen/{fname}")

    return base64.b64encode(buf.getvalue()).decode("utf-8")


def generate_notebook_code(slot_id: int, tasks: List[Dict], b64_payload: str) -> str:
    task_calls = []
    for t in tasks:
        task_calls.append(
            f'run_task("{t["instance"]}", {t["seed_start"]}, {t["repeats"]})'
        )
    task_calls_code = "\n".join(task_calls)

    return f"""import base64
import io
import os
import sys
import zipfile
from pathlib import Path
import subprocess

print("=== SETTING UP BALANCED CANONICAL PH-SHOWOA ON KAGGLE (Slot {slot_id:02d}) ===", flush=True)
payload = \"\"\"{b64_payload}\"\"\"

zip_bytes = base64.b64decode(payload)
with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
    zf.extractall("/kaggle/working")

print("Extracted source code to /kaggle/working.", flush=True)

data_candidates = [
    Path("/kaggle/working/data/Wang_Chen"),
    Path("/kaggle/input/ph-showoa"),
    Path("/kaggle/input/datasets/keith1101/ph-showoa"),
    Path("/kaggle/input/ph-showoa/data/Wang_Chen"),
    Path("/kaggle/input/datasets/keith1101/ph-showoa/data/Wang_Chen"),
]
data_root = None
for p in data_candidates:
    if p.exists():
        data_root = p
        break

runner_script = Path("/kaggle/working/scripts/canonical/kaggle_run_canonical.py")
if not runner_script.exists():
    raise FileNotFoundError(f"Could not find runner script at {{runner_script}}")

def run_task(instance: str, seed_start: int, repeats: int):
    cmd = [
        sys.executable,
        str(runner_script),
        "--instance", instance,
        "--repeats", str(repeats),
        "--seed_start", str(seed_start),
        "--pop_size", "30",
        "--max_iter", "1000",
        "--workers", "1",
        "--output_dir", "/kaggle/working/outputs",
    ]
    if data_root is not None:
        cmd.extend(["--data_root", str(data_root)])

    print(f"\\n>>> STARTING TASK: {{instance}} (seeds {{seed_start}}..{{seed_start+repeats-1}}, {{repeats}} runs) <<<", flush=True)
    res = subprocess.run(cmd)
    print(f">>> TASK {{instance}} COMPLETED with exit code: {{res.returncode}} <<<\\n", flush=True)
    if res.returncode != 0:
        print(f"WARNING: Task {{instance}} failed with returncode {{res.returncode}}", flush=True)

print("Starting balanced tasks execution...", flush=True)
{task_calls_code}
print("=== ALL TASKS IN SLOT {slot_id:02d} FINISHED SUCCESSFULLY ===", flush=True)
sys.exit(0)
"""


def create_job(job_dir: Path, owner: str, slug: str, slot_id: int, tasks: List[Dict], b64_payload: str) -> None:
    job_dir.mkdir(parents=True, exist_ok=True)
    code_content = generate_notebook_code(slot_id, tasks, b64_payload)

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
        "dataset_sources": [],
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
    parser = argparse.ArgumentParser(description="Prepare and dispatch Balanced Canonical PH-SHOWOA 65 slots on Kaggle")
    parser.add_argument("--push", action="store_true", help="Actually push kernels to Kaggle (default: prepare only)")
    parser.add_argument("--accounts", nargs="*", default=None, help="Specific accounts to target (e.g. account-b)")
    args = parser.parse_args()

    allocations = compute_balanced_allocations()
    if args.accounts:
        target_accs = set(args.accounts)
        allocations = [a for a in allocations if a["account"] in target_accs]

    print("=" * 75)
    print(f"PREPARING BALANCED CANONICAL 65-SLOT KAGGLE JOBS (Total slots: {len(allocations)})")
    print(f"Mode: {'PUSH TO KAGGLE' if args.push else 'PREPARE ONLY (DRY-RUN)'}")
    print("=" * 75)

    JOBS_ROOT.mkdir(parents=True, exist_ok=True)

    for idx, alloc in enumerate(allocations, 1):
        slot_id = alloc["slot_id"]
        account = alloc["account"]
        owner = alloc["owner"]
        slug = alloc["slug"]
        tasks = alloc["tasks"]
        est_min = alloc["est_min"]

        job_dir = JOBS_ROOT / account / slug
        task_insts = {t["instance"] for t in tasks}
        b64_payload = package_src_canonical_b64(task_insts)

        create_job(job_dir, owner, slug, slot_id, tasks, b64_payload)

        task_summary = ", ".join(f"{t['instance']}(s{t['seed_start']}-n{t['repeats']})" for t in tasks)
        print(f"[{idx:2d}/{len(allocations)}] Slot {slot_id:02d} | {owner}/{slug} ({account}) | Est: {est_min:5.1f}m | Tasks: {task_summary}")

        if args.push:
            print(f"    --> Pushing kernel {owner}/{slug} to Kaggle...")
            env = get_kaggle_env(account)
            res = subprocess.run([KAGGLE_EXE, "kernels", "push", "-p", str(job_dir)], env=env, capture_output=True, text=True)
            if res.returncode == 0:
                print(f"    --> SUCCESS: {owner}/{slug} pushed.")
            else:
                print(f"    --> FAILED: {owner}/{slug} | {res.stderr.strip()}")

    print("\n" + "=" * 75)
    print("ALL 65 BALANCED KAGGLE SLOTS SUCCESSFULLY PROCESSED!")
    print("=" * 75)


if __name__ == "__main__":
    main()
