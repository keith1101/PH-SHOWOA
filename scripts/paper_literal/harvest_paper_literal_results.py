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
HARVEST_DOWNLOAD_ROOT = Path("D:/Project/Kaggle/output_paper_literal")
DEFAULT_OUTPUT_CSV = PROJECT_ROOT / "outputs" / "ph_showoa_paper_literal_results.csv"

# Import allocations from dispatch script
sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "paper_literal"))
from prepare_and_dispatch_paper_literal_65slots import build_allocations, get_kaggle_env, SHEET_INSTANCES

CANONICAL_MAP = {s.lower(): s for s in SHEET_INSTANCES}

CSV_COLUMNS = [
    "instance",
    "algo",
    "run",
    "NV",
    "TD",
    "cost",
    "feasible",
    "violation_note",
]


def check_and_download_kernels(allocations: List[Dict]) -> None:
    print("=" * 75)
    print(f"CHECKING AND HARVESTING KAGGLE KERNELS ({len(allocations)} jobs)")
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
    print("AGGREGATING RESULTS INTO CSV")
    print(f"Target CSV: {output_csv}")
    print("=" * 75)

    scan_dirs = [
        HARVEST_DOWNLOAD_ROOT,
        PROJECT_ROOT / "outputs",
    ]

    all_rows = []
    seen_keys = set()  # (instance, run)

    for base_dir in scan_dirs:
        if not base_dir.exists():
            continue
        for csv_path in base_dir.rglob("runs.csv"):
            try:
                with open(csv_path, "r", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        raw_inst = row.get("instance", "").strip()
                        inst = CANONICAL_MAP.get(raw_inst.lower(), raw_inst)
                        algo = row.get("algo", "PH-SHOWOA-PaperLiteral").strip()
                        run_str = row.get("run", "1").strip()
                        key = (inst.lower(), run_str)
                        if key not in seen_keys:
                            seen_keys.add(key)
                            all_rows.append({
                                "instance": inst,
                                "algo": algo,
                                "run": int(run_str) if run_str.isdigit() else 1,
                                "NV": row.get("NV", "").strip(),
                                "TD": row.get("TD", "").strip(),
                                "cost": row.get("cost", "").strip(),
                                "feasible": row.get("feasible", "").strip(),
                                "violation_note": row.get("violation_note", "").strip(),
                            })
            except Exception as e:
                print(f"Error reading {csv_path}: {e}")

    # Sort rows by instance name, then run index
    all_rows.sort(key=lambda r: (r["instance"].lower(), r["run"]))

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(CSV_COLUMNS)
        for r in all_rows:
            writer.writerow([
                r["instance"],
                r["algo"],
                r["run"],
                r["NV"],
                r["TD"],
                r["cost"],
                r["feasible"],
                r["violation_note"],
            ])

    print(f"Successfully aggregated {len(all_rows)} rows across {len(set(r['instance'] for r in all_rows))} instances.")
    print(f"Aggregated CSV written to: {output_csv}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Harvest and aggregate Paper-Literal PH-SHOWOA results")
    parser.add_argument("--output_csv", type=Path, default=DEFAULT_OUTPUT_CSV, help="Output aggregated CSV path")
    parser.add_argument("--skip_download", action="store_true", help="Skip checking/downloading from Kaggle")
    args = parser.parse_args()

    allocations = build_allocations()

    if not args.skip_download:
        check_and_download_kernels(allocations)

    aggregate_results(args.output_csv)


if __name__ == "__main__":
    main()
