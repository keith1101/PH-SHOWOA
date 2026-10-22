from __future__ import annotations

import argparse
import csv
import os
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List

PROJECT_ROOT = Path("D:/Project/PH-SHOWOA")
KAGGLE_EXE = r"C:\Users\LENOVO\miniconda3\envs\phshowoa\Scripts\kaggle.exe"
CREDS_ROOT = Path("D:/Project/Kaggle/credentials")
HARVEST_DOWNLOAD_ROOT = Path("D:/Project/Kaggle/output_canonical_v2")
DEFAULT_OUTPUT_CSV = PROJECT_ROOT / "outputs" / "ph_showoa_canonical_results.csv"

# Import allocations from dispatch script
sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "canonical"))
from prepare_and_dispatch_canonical_65slots import build_allocations, get_kaggle_env, SHEET_INSTANCES

CANONICAL_MAP = {s.lower(): s for s in SHEET_INSTANCES}

CSV_COLUMNS = [
    "instance",
    "algo",
    "run",
    "seed",
    "NV",
    "TD",
    "cost",
    "feasible",
    "violation_note",
    "elapsed_seconds",
]


def check_and_download_kernels(allocations: List[Dict]) -> bool:
    print("=" * 75)
    print(f"CHECKING AND HARVESTING CANONICAL KAGGLE KERNELS ({len(allocations)} jobs)")
    print("=" * 75)

    status_counts = Counter()
    completed_jobs = []

    for idx, job in enumerate(allocations, 1):
        ref = f"{job['owner']}/{job['slug']}"
        account = job["account"]
        env = get_kaggle_env(account)

        res = subprocess.run([KAGGLE_EXE, "kernels", "status", ref], env=env, capture_output=True, text=True)
        out = (res.stdout + res.stderr).strip()

        status = "UNKNOWN"
        out_upper = out.upper()
        if "COMPLETE" in out_upper:
            status = "COMPLETE"
            completed_jobs.append(job)
        elif "RUNNING" in out_upper:
            status = "RUNNING"
        elif "ERROR" in out_upper:
            status = "ERROR"
        elif "QUEUED" in out_upper:
            status = "QUEUED"
        else:
            status = out if out else "NOT FOUND / PENDING"

        status_counts[status] += 1
        print(f"[{idx:2d}/{len(allocations)}] {ref} -> {status}", flush=True)

    print("\n" + "=" * 75)
    print("STATUS SUMMARY:")
    for st, count in status_counts.items():
        print(f"  {st:25s}: {count}")
    print("=" * 75)

    # Download outputs of completed kernels
    if completed_jobs:
        print(f"\nDownloading outputs for {len(completed_jobs)} completed kernels...")
        for idx, job in enumerate(completed_jobs, 1):
            ref = f"{job['owner']}/{job['slug']}"
            out_dir = HARVEST_DOWNLOAD_ROOT / job["instance"] / job["slug"]
            out_dir.mkdir(parents=True, exist_ok=True)

            # Skip if runs.csv already exists
            has_runs = any(out_dir.rglob("runs.csv"))
            if has_runs:
                print(f"[{idx:2d}/{len(completed_jobs)}] [{job['instance']}] {ref} already downloaded. Skipping.")
                continue

            print(f"[{idx:2d}/{len(completed_jobs)}] [{job['instance']}] Downloading {ref} -> {out_dir}...")
            env = get_kaggle_env(job["account"])
            res = subprocess.run([KAGGLE_EXE, "kernels", "output", ref, "-p", str(out_dir)], env=env, capture_output=True, text=True)
            if res.returncode == 0:
                print(f"   --> SUCCESS: {ref}")
            else:
                print(f"   --> FAILED: {ref} | {res.stderr.strip()}")

    return len(completed_jobs) == len(allocations)


def aggregate_results(output_csv: Path) -> None:
    print("\n" + "=" * 75)
    print(f"AGGREGATING RUNS INTO LOCAL CSV: {output_csv}")
    print("=" * 75)

    all_rows = []
    seen_keys = set()
    instance_counts = Counter()
    instance_feas_counts = Counter()

    if not HARVEST_DOWNLOAD_ROOT.exists():
        print(f"Download root {HARVEST_DOWNLOAD_ROOT} does not exist yet. No runs to aggregate.")
        return

    csv_files = list(HARVEST_DOWNLOAD_ROOT.rglob("runs.csv"))
    print(f"Found {len(csv_files)} runs.csv files in {HARVEST_DOWNLOAD_ROOT}")

    for fpath in csv_files:
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    raw_inst = row.get("instance", "").strip()
                    inst = CANONICAL_MAP.get(raw_inst.lower(), raw_inst)
                    run_no = int(row.get("run", 0))
                    key = (inst, run_no)

                    if key in seen_keys:
                        continue
                    seen_keys.add(key)

                    nv = int(row.get("NV", 0))
                    td = float(row.get("TD", 0.0))
                    cost = float(row.get("cost", 0.0))
                    feas_str = row.get("feasible", "False").strip().lower()
                    feas = feas_str in ("true", "1")
                    note = row.get("violation_note", "")
                    seed = int(row.get("seed", 42 + run_no - 1))
                    elapsed = float(row.get("elapsed_seconds", 0.0))

                    clean_row = {
                        "instance": inst,
                        "algo": "PH-SHOWOA-Canonical",
                        "run": run_no,
                        "seed": seed,
                        "NV": nv,
                        "TD": f"{td:.2f}",
                        "cost": f"{cost:.2f}",
                        "feasible": str(feas),
                        "violation_note": note,
                        "elapsed_seconds": f"{elapsed:.2f}",
                    }
                    all_rows.append(clean_row)
                    instance_counts[inst] += 1
                    if feas:
                        instance_feas_counts[inst] += 1
        except Exception as e:
            print(f"Error reading {fpath}: {e}")

    # Sort rows by instance (according to SHEET_INSTANCES order) then run
    inst_order = {inst: i for i, inst in enumerate(SHEET_INSTANCES)}
    all_rows.sort(key=lambda r: (inst_order.get(r["instance"], 999), r["run"]))

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    tmp_csv = output_csv.with_suffix(".tmp")
    with open(tmp_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(all_rows)

    # Atomic rename / replace with retry for Windows file locks
    for attempt in range(5):
        try:
            tmp_csv.replace(output_csv)
            break
        except Exception:
            import time
            time.sleep(1)
    else:
        # Fallback if locked
        with open(output_csv, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
            writer.writeheader()
            writer.writerows(all_rows)

    total_runs = len(all_rows)
    total_feas = sum(instance_feas_counts.values())
    feas_rate = (total_feas / total_runs * 100) if total_runs > 0 else 0.0

    print(f"Successfully wrote {total_runs} runs across {len(instance_counts)} instances.")
    print(f"Overall Feasibility: {total_feas}/{total_runs} ({feas_rate:.2f}%)")
    print(f"Output saved to: {output_csv.resolve()}\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Harvest and aggregate Canonical PH-SHOWOA results from Kaggle")
    parser.add_argument("--output_csv", type=Path, default=DEFAULT_OUTPUT_CSV, help="Output CSV path")
    parser.add_argument("--download_only", action="store_true", help="Only check and download kernels")
    parser.add_argument("--aggregate_only", action="store_true", help="Only aggregate existing downloaded CSVs")
    args = parser.parse_args()

    allocations = build_allocations()

    if not args.aggregate_only:
        check_and_download_kernels(allocations)

    if not args.download_only:
        aggregate_results(args.output_csv)


if __name__ == "__main__":
    main()
