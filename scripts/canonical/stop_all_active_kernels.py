from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, List

PROJECT_ROOT = Path("D:/Project/PH-SHOWOA")
KAGGLE_EXE = r"C:\Users\LENOVO\miniconda3\envs\phshowoa\Scripts\kaggle.exe"
CREDS_ROOT = Path("D:/Project/Kaggle/credentials")
STOP_JOBS_DIR = PROJECT_ROOT / "build_jobs_canonical" / "_stop_jobs"

sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "canonical"))
from prepare_and_dispatch_canonical_65slots import build_allocations, get_kaggle_env


def create_stop_kernel(job_dir: Path, owner: str, slug: str) -> None:
    job_dir.mkdir(parents=True, exist_ok=True)
    nb = {
        "cells": [
            {
                "cell_type": "code",
                "execution_count": None,
                "metadata": {},
                "outputs": [],
                "source": ["import sys\n", "print('Kernel stopped upon user request.')\n", "sys.exit(0)\n"]
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


def stop_active_kernels() -> None:
    allocations = build_allocations()
    print("=" * 75)
    print(f"STOPPING ACTIVE KERNELS VIA OVERRIDE PUSH ({len(allocations)} total jobs)")
    print("=" * 75)

    running_jobs = []
    for idx, job in enumerate(allocations, 1):
        ref = f"{job['owner']}/{job['slug']}"
        account = job["account"]
        env = get_kaggle_env(account)

        res = subprocess.run([KAGGLE_EXE, "kernels", "status", ref], env=env, capture_output=True, text=True)
        out = (res.stdout + res.stderr).strip().upper()

        if "RUNNING" in out or "QUEUED" in out:
            print(f"[{idx:2d}/{len(allocations)}] {ref} is {out} -> QUEUED FOR STOPPING")
            running_jobs.append(job)
        else:
            print(f"[{idx:2d}/{len(allocations)}] {ref} is {out} -> SKIP")

    print("\n" + "=" * 75)
    print(f"Found {len(running_jobs)} active kernels to stop.")
    print("=" * 75)

    if not running_jobs:
        print("No kernels currently running or queued. All clear!")
        return

    STOP_JOBS_DIR.mkdir(parents=True, exist_ok=True)
    for idx, job in enumerate(running_jobs, 1):
        slug = job["slug"]
        owner = job["owner"]
        ref = f"{owner}/{slug}"
        account = job["account"]
        env = get_kaggle_env(account)

        job_dir = STOP_JOBS_DIR / account / slug
        create_stop_kernel(job_dir, owner, slug)

        print(f"[{idx:2d}/{len(running_jobs)}] Overriding {ref} ({account}) to stop...")
        push_res = subprocess.run([KAGGLE_EXE, "kernels", "push", "-p", str(job_dir)], env=env, capture_output=True, text=True)
        if push_res.returncode == 0:
            print(f"   --> SUCCESS: {ref} stopped and overridden.")
        else:
            print(f"   --> FAILED: {ref} | {push_res.stderr.strip()}")

    print("\n" + "=" * 75)
    print("ALL ACTIVE KERNELS OVERRIDDEN AND STOPPED!")
    print("=" * 75)


if __name__ == "__main__":
    stop_active_kernels()
