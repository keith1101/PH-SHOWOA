"""
CLEANUP OLD RESULTS SCRIPT
Deletes outdated benchmark runs, keeping ONLY the latest verified canonical results from 2026-10-22.
"""

from __future__ import annotations

import os
import shutil
import stat
from pathlib import Path

WORKSPACE = Path("D:/Project/PH-SHOWOA")
KAGGLE_DIR = Path("D:/Project/Kaggle")

# Files in outputs/ to explicitly delete (old results)
OLD_OUTPUT_FILES = [
    "all_collected_runs_summary.csv",
    "best_solutions_65instances.csv",
    "final_benchmark_summary_65instances.csv",
    "ph_showoa_all_1950_runs.csv",
    "ph_showoa_benchmark_summary.csv",
    "ph_showoa_comprehensive_runs_and_summary.csv",
    "ph_showoa_paper_literal_results.csv",
    "smoke_test_paper_literal.csv",
    "smoke_test_results.csv",
    "test_cli.csv",
]

# Subdirectories in outputs/ to explicitly delete
OLD_OUTPUT_DIRS = [
    "format_65_instances",
    "kaggle_literal_test",
    "pop32_log_summary",
]

# Top-level directories in workspace to delete
OLD_WORKSPACE_DIRS = [
    "batch_results",
    "build_jobs_canonical",
]

# Outdated output directories in D:/Project/Kaggle to delete
OLD_KAGGLE_DIRS = [
    "output_canonical",       # Old unpatched run from 2026-10-21
    "output_paper_literal",   # Old run from 2026-10-19
    "output",                 # Old run from 2026-10-16
    "temp_rdp204_check",      # Temporary probe folder
]

# MUST PRESERVE (SANITY CHECK)
KEEP_CANONICAL = [
    "ph_showoa_canonical_results.csv",
    "canonical_best_solutions_summary.csv",
    "canonical_best_solutions_verified.json",
]


def remove_readonly(func, path, exc_info):
    """Clear the read-only bit and retry removal."""
    try:
        os.chmod(path, stat.S_IWRITE)
        func(path)
    except Exception as e:
        print(f"Failed to remove {path}: {e}")


def main():
    print("=" * 70)
    print("CLEANING UP OLD RESULTS (KEEPING LATEST CANONICAL RESULTS)")
    print("=" * 70)

    # 1. Clean old files in outputs/
    outputs_dir = WORKSPACE / "outputs"
    for fname in OLD_OUTPUT_FILES:
        fpath = outputs_dir / fname
        if fpath.is_file():
            try:
                os.chmod(fpath, stat.S_IWRITE)
                os.remove(fpath)
                print(f"[REMOVED FILE] outputs/{fname}")
            except Exception as e:
                print(f"[ERROR] Could not remove outputs/{fname}: {e}")

    # 2. Clean old directories in outputs/
    for dname in OLD_OUTPUT_DIRS:
        dpath = outputs_dir / dname
        if dpath.is_dir():
            try:
                shutil.rmtree(dpath, onerror=remove_readonly)
                print(f"[REMOVED DIR]  outputs/{dname}")
            except Exception as e:
                print(f"[ERROR] Could not remove outputs/{dname}: {e}")

    # 3. Clean old directories in WORKSPACE
    for dname in OLD_WORKSPACE_DIRS:
        dpath = WORKSPACE / dname
        if dpath.is_dir():
            try:
                shutil.rmtree(dpath, onerror=remove_readonly)
                print(f"[REMOVED DIR]  {dname}")
            except Exception as e:
                print(f"[ERROR] Could not remove {dname}: {e}")

    # 4. Clean old directories in D:/Project/Kaggle
    for dname in OLD_KAGGLE_DIRS:
        dpath = KAGGLE_DIR / dname
        if dpath.is_dir():
            try:
                shutil.rmtree(dpath, onerror=remove_readonly)
                print(f"[REMOVED DIR]  Kaggle/{dname}")
            except Exception as e:
                print(f"[ERROR] Could not remove Kaggle/{dname}: {e}")

    # 5. Verify preserved files
    print("\n" + "=" * 70)
    print("VERIFYING PRESERVED LATEST RESULTS:")
    for fname in KEEP_CANONICAL:
        fpath = outputs_dir / fname
        if fpath.exists():
            sz = fpath.stat().st_size
            print(f"  [PRESERVED] outputs/{fname} ({sz / 1024:.1f} KB)")
        else:
            print(f"  [WARNING] Expected outputs/{fname} not found!")

    k_v2 = KAGGLE_DIR / "output_canonical_v2"
    if k_v2.is_dir():
        count = len(list(k_v2.rglob("runs.csv")))
        print(f"  [PRESERVED] Kaggle/output_canonical_v2 ({count} instances)")

    print("=" * 70)
    print("CLEANUP COMPLETED SUCCESSFULLY!")
    print("=" * 70)


if __name__ == "__main__":
    main()
