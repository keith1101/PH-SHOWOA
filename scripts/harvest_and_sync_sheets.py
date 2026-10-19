#!/usr/bin/env python3
"""
scripts/harvest_and_sync_sheets.py
==================================
Milestone 2 - Automated Output Harvesting & Google Sheet Synchronization.

Features:
1. Multi-account Kaggle kernel monitoring and output harvesting for:
   - account-c (dautromduoicuop): Cdp203 (5 kernels, seeds 42..71)
   - account-d (keith1101): Cdp205 (5 kernels, seeds 42..71)
   - account-e (giahaohuynh): Cdp208 (5 kernels, seeds 42..71)
   - tafuhihi (tafuhihi): Cdp202 (5 kernels, seeds 42..71, NEW SOLUTION)
2. Comprehensive multi-format log parser across 65 instances:
   - Parses runs.csv, runs.json, summary.json, solution.txt, and raw solver logs.
   - Enforces user directive: Cdp202 only accepts runs from the new solution (tafuhihi).
     Baseline Cdp202 runs are excluded to prevent overwriting with old solutions.
3. Statistical aggregation & formatting:
   - NV: integer string if integer, or 2 decimal places if fractional. Empty if 0 runs.
   - TD: 2 decimal places. Empty if 0 runs.
   - Avg/Run: formatted "{m}m{s:02d}s" or "{h}h{m:02d}m{s:02d}s". Empty if 0 runs.
   - Mapped to Rows 3 to 67 (Row = STT + 2) in tab 'Python_rerun_popsize30'.
4. Google Sheets synchronization:
   - Generates tmp/gsheets_update_request.json for range 'Python_rerun_popsize30'!G3:I67.
   - Executes batch mutation via Google Sheets CLI (BypassSandbox: true).
   - Verifies update by reading back from the sheet.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import shutil
import subprocess
import sys
import datetime
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

SPREADSHEET_ID = "1q498GxIhgMLg38hN44w-hWStl89EsSNDBHOp5Ksd2rA"
SHEET_NAME = "Python_rerun_popsize30"
SHEET_RANGE = f"'{SHEET_NAME}'!G3:I67"

# CUTOFF_DATE per user directive to exclude legacy pre-12/10 runs
DEFAULT_CUTOFF_DATE = datetime.datetime(2026, 10, 12, 0, 0, 0)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_ROOT = Path(r"D:\Project\Kaggle\output")
CREDS_ROOT = Path(r"D:\Project\Kaggle\credentials")
TMP_DIR = PROJECT_ROOT / "tmp"

KAGGLE_EXE = Path(r"C:\Users\LENOVO\miniconda3\envs\phshowoa\Scripts\kaggle.exe")
GSHEETS_CMD = Path(
    r"C:\Users\LENOVO\.gemini\config\plugins\gsheets\skills\gsheets\scripts\gsheets.cmd"
)

# Canonical ordering of the 65 instances in Google Sheet (Rows 3 to 67)
SHEET_INSTANCES: List[str] = [
    # Table 3: Small WC (9 instances, rows 3..11, STT 1..9)
    "RCdp1001", "RCdp1004", "RCdp1007",
    "RCdp2501", "RCdp2504", "RCdp2507",
    "RCdp5001", "RCdp5004", "RCdp5007",
    # Table 4: RCdp 100-customer (8 instances, rows 12..19, STT 10..17)
    "RCdp101", "RCdp102", "RCdp103", "RCdp104", "RCdp105", "RCdp106", "RCdp107", "RCdp108",
    # Table 5: RCdp 100-customer (8 instances, rows 20..27, STT 18..25)
    "RCdp201", "RCdp202", "RCdp203", "RCdp204", "RCdp205", "RCdp206", "RCdp207", "RCdp208",
    # Table 4: Cdp 100-customer (9 instances, rows 28..36, STT 26..34)
    "Cdp101", "Cdp102", "Cdp103", "Cdp104", "Cdp105", "Cdp106", "Cdp107", "Cdp108", "Cdp109",
    # Table 5: Cdp 100-customer (8 instances, rows 37..44, STT 35..42)
    "Cdp201", "Cdp202", "Cdp203", "Cdp204", "Cdp205", "Cdp206", "Cdp207", "Cdp208",
    # Table 4: Rdp 100-customer (12 instances, rows 45..56, STT 43..54)
    "Rdp101", "Rdp102", "Rdp103", "Rdp104", "Rdp105", "Rdp106", "Rdp107", "Rdp108", "Rdp109", "Rdp110", "Rdp111", "Rdp112",
    # Table 5: Rdp 100-customer (11 instances, rows 57..67, STT 55..65)
    "Rdp201", "Rdp202", "Rdp203", "Rdp204", "Rdp205", "Rdp206", "Rdp207", "Rdp208", "Rdp209", "Rdp210", "Rdp211",
]

# Kaggle remote targets configuration (Wave 1 Completed + Wave 2 Running)
HARVEST_TARGETS = [
    # Wave 1 Targets (Completed on 2026-10-12)
    {
        "account": "account-c",
        "owner": "dautromduoicuop",
        "creds_dir": str(CREDS_ROOT / "account-c"),
        "instance": "Cdp203",
        "slug_pattern": "ph-showoa-pop30-cdp203-s{seed}-n6",
        "seeds": [42, 48, 54, 60, 66],
        "is_new_solution": False,
        "wave": 1,
        "dest_subdir": "Cdp203",
    },
    {
        "account": "account-d",
        "owner": "keith1101",
        "creds_dir": str(CREDS_ROOT / "account-d"),
        "instance": "Cdp205",
        "slug_pattern": "ph-showoa-pop30-cdp205-s{seed}-n6",
        "seeds": [42, 48, 54, 60, 66],
        "is_new_solution": False,
        "wave": 1,
        "dest_subdir": "cdp205",
    },
    {
        "account": "account-e",
        "owner": "giahaohuynh",
        "creds_dir": str(CREDS_ROOT / "account-e"),
        "instance": "Cdp208",
        "slug_pattern": "ph-showoa-pop30-cdp208-s{seed}-n6",
        "seeds": [42, 48, 54, 60, 66],
        "is_new_solution": False,
        "wave": 1,
        "dest_subdir": "cdp208",
    },
    # Wave 2 Targets (Running with new solution: keith1101/phshowoa-code dataset v2)
    {
        "account": "tafuhihi",
        "owner": "tafuhihi",
        "creds_dir": r"C:\Users\LENOVO\.kaggle",
        "instance": "Cdp202",
        "slug_pattern": "ph-showoa-new-cdp202-s{seed}-n6",
        "seeds": [42, 48, 54, 60, 66],
        "is_new_solution": True,
        "wave": 2,
        "dest_subdir": "Cdp202_tafuhihi",
    },
    {
        "account": "account-b",
        "owner": "kanhan162",
        "creds_dir": str(CREDS_ROOT / "account-b"),
        "instance": "Cdp201",
        "slug_pattern": "ph-showoa-new-cdp201-s{seed}-n6",
        "seeds": [42, 48, 54, 60, 66],
        "is_new_solution": True,
        "wave": 2,
        "dest_subdir": "Cdp201_new",
    },
    {
        "account": "account-c",
        "owner": "dautromduoicuop",
        "creds_dir": str(CREDS_ROOT / "account-c"),
        "instance": "Cdp204",
        "slug_pattern": "ph-showoa-new-cdp204-s{seed}-n6",
        "seeds": [42, 48, 54, 60, 66],
        "is_new_solution": True,
        "wave": 2,
        "dest_subdir": "Cdp204_new",
    },
    {
        "account": "account-d",
        "owner": "keith1101",
        "creds_dir": str(CREDS_ROOT / "account-d"),
        "instance": "Cdp206",
        "slug_pattern": "ph-showoa-new-cdp206-s{seed}-n6",
        "seeds": [42, 48, 54, 60, 66],
        "is_new_solution": True,
        "wave": 2,
        "dest_subdir": "Cdp206_new",
    },
    {
        "account": "account-e",
        "owner": "giahaohuynh",
        "creds_dir": str(CREDS_ROOT / "account-e"),
        "instance": "Cdp207",
        "slug_pattern": "ph-showoa-new-cdp207-s{seed}-n6",
        "seeds": [42, 48, 54, 60, 66],
        "is_new_solution": True,
        "wave": 2,
        "dest_subdir": "Cdp207_new",
    },
]


def resolve_kaggle_exe() -> str:
    """Return path to kaggle CLI executable."""
    if KAGGLE_EXE.exists():
        return str(KAGGLE_EXE)
    which_path = shutil.which("kaggle")
    if which_path:
        return which_path
    return "kaggle"


def resolve_gsheets_cmd() -> str:
    """Return path to gsheets CLI tool."""
    if GSHEETS_CMD.exists():
        return str(GSHEETS_CMD)
    which_path = shutil.which("gsheets")
    if which_path:
        return which_path
    return "gsheets"


def format_time(sec: Optional[float]) -> str:
    """
    Format runtime in seconds to human-readable string:
    - Under 1 minute: '{s}s'
    - Under 1 hour: '{m}m{s:02d}s'
    - 1 hour or more: '{h}h{m:02d}m{s:02d}s'
    - None/0: ''
    """
    if sec is None or sec <= 0:
        return ""
    total_seconds = int(round(sec))
    m, s = divmod(total_seconds, 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h}h{m:02d}m{s:02d}s"
    elif m > 0:
        return f"{m}m{s:02d}s"
    else:
        return f"{s}s"


def format_nv(nv: Optional[float]) -> str:
    """
    Format average vehicle count:
    - Exact integer: integer string (e.g. '3', '10')
    - Fractional: 2 decimal places (e.g. '15.14', '3.18')
    - None: ''
    """
    if nv is None:
        return ""
    if abs(nv - round(nv)) < 1e-4:
        return str(int(round(nv)))
    return f"{nv:.2f}"


def format_td(td: Optional[float]) -> str:
    """
    Format average travel distance:
    - Float with 2 decimal places (e.g. '348.98')
    - None: ''
    """
    if td is None:
        return ""
    return f"{td:.2f}"


def check_kernel_status(owner: str, slug: str, creds_dir: str) -> str:
    """Query kernel status via Kaggle CLI."""
    env = os.environ.copy()
    env["KAGGLE_CONFIG_DIR"] = str(creds_dir)
    cmd = [resolve_kaggle_exe(), "kernels", "status", f"{owner}/{slug}"]
    try:
        res = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=30)
        out = (res.stdout or "") + " " + (res.stderr or "")
        if "404 - Not Found" in out:
            return "NOT_FOUND"
        if "KernelWorkerStatus.COMPLETE" in out or '"COMPLETE"' in out:
            return "COMPLETE"
        if "KernelWorkerStatus.RUNNING" in out or '"RUNNING"' in out:
            return "RUNNING"
        if "KernelWorkerStatus.ERROR" in out or '"ERROR"' in out:
            return "ERROR"
        if "KernelWorkerStatus.QUEUED" in out or '"QUEUED"' in out:
            return "QUEUED"
        return out.strip() or "UNKNOWN"
    except subprocess.TimeoutExpired:
        return "TIMEOUT"
    except Exception as exc:
        return f"ERROR: {exc}"


def download_kernel_output(
    owner: str, slug: str, creds_dir: str, target_dir: Path, force: bool = False
) -> Tuple[bool, str]:
    """Download kernel output bundle via Kaggle CLI."""
    target_dir.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["KAGGLE_CONFIG_DIR"] = str(creds_dir)
    cmd = [
        resolve_kaggle_exe(),
        "kernels",
        "output",
        f"{owner}/{slug}",
        "-p",
        str(target_dir),
    ]
    if force:
        cmd.append("--force")
    try:
        res = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=120)
        output_msg = (res.stdout or "") + (res.stderr or "")
        return res.returncode == 0, output_msg.strip()
    except Exception as exc:
        return False, str(exc)


def harvest_remote_kernels(
    force_download: bool = False,
) -> Dict[str, Any]:
    """
    Harvest completed remote kernel outputs from Kaggle.
    Adheres strictly to user directive regarding Cdp202:
    - tafuhihi (new solution) is queried for Cdp202.
    - If running, do not harvest baseline or overwrite Cdp202.
    """
    results: Dict[str, Any] = {
        "harvested": [],
        "running": [],
        "skipped": [],
        "errors": [],
    }

    print("\n" + "=" * 80)
    print("HARVESTING COMPLETED KERNELS ACROSS KAGGLE ACCOUNTS")
    print("=" * 80)

    for target in HARVEST_TARGETS:
        account = target["account"]
        owner = target["owner"]
        creds_dir = target["creds_dir"]
        inst = target["instance"]
        slug_pat = target["slug_pattern"]
        seeds = target["seeds"]
        dest_subdir = target["dest_subdir"]
        is_new = target["is_new_solution"]

        tag = "[NEW SOLUTION]" if is_new else "[BASELINE]"
        print(f"\n--- Checking Account: {account} ({owner}) | Target: {inst} {tag} ---")

        for s in seeds:
            slug = slug_pat.format(seed=s)
            status = check_kernel_status(owner, slug, creds_dir)
            target_dir = OUTPUT_ROOT / dest_subdir / slug

            print(f"  [{inst}] {owner}/{slug} -> {status}")

            if status == "COMPLETE":
                # Check if already downloaded locally
                has_runs_csv = any(target_dir.rglob("runs.csv"))
                if has_runs_csv and not force_download:
                    print(f"    -> Local output exists at {target_dir}. Skipping re-download.")
                    results["harvested"].append(
                        {"instance": inst, "slug": slug, "status": "ALREADY_DOWNLOADED"}
                    )
                else:
                    print(f"    -> Downloading output bundle to {target_dir}...")
                    ok, msg = download_kernel_output(
                        owner, slug, creds_dir, target_dir, force=force_download
                    )
                    if ok:
                        print(f"    -> Successfully downloaded: {msg[:60]}")
                        results["harvested"].append(
                            {"instance": inst, "slug": slug, "status": "DOWNLOADED"}
                        )
                    else:
                        print(f"    -> Download failed: {msg}")
                        results["errors"].append(
                            {"instance": inst, "slug": slug, "error": msg}
                        )
            elif status == "RUNNING":
                results["running"].append({"instance": inst, "slug": slug})
                if inst == "Cdp202":
                    print(
                        f"    -> NOTE: Cdp202 (tafuhihi) is still RUNNING. "
                        f"Per user directive, do not overwrite Cdp202 with baseline."
                    )
            else:
                results["skipped"].append(
                    {"instance": inst, "slug": slug, "status": status}
                )

    print("\nHarvest Summary:")
    print(f"  Harvested/Available: {len(results['harvested'])}")
    print(f"  Still Running:       {len(results['running'])}")
    print(f"  Errors:              {len(results['errors'])}")
    print("=" * 80 + "\n")
    return results


def parse_solution_text(content: str) -> Optional[Tuple[int, float]]:
    """Parse vehicle number and total distance from solution.txt content."""
    nv_m = re.search(r"vehicle\s*\(route\)\s*number:\s*(\d+)", content, re.IGNORECASE)
    tc_m = re.search(r"Total\s*cost:\s*([\d.]+)", content, re.IGNORECASE)
    if nv_m and tc_m:
        nv = int(nv_m.group(1))
        tc = float(tc_m.group(1))
        # Total cost = 2000.0 * NV + TD
        td = tc - 2000.0 * nv
        return nv, td
    return None


def parse_all_runs(
    scan_dirs: Optional[List[Path]] = None,
    include_baseline_cdp202: bool = False,
    cutoff_date: Optional[datetime.datetime] = DEFAULT_CUTOFF_DATE,
) -> Dict[str, Dict[int, Tuple[float, float, float]]]:
    """
    Scan all harvested and completed log repositories across 65 instances.
    Extracts (vehicles, distance, duration_sec) per seed per instance.

    Guarantees:
    - Deduplicates runs by seed.
    - Excludes old baseline Cdp202 runs unless explicitly requested.
    - Filters files by cutoff_date (defaulting to 2026-10-12) to exclude legacy runs.
    """
    if scan_dirs is None:
        if cutoff_date is not None:
            scan_dirs = [OUTPUT_ROOT]
        else:
            scan_dirs = [
                PROJECT_ROOT / "tmp" / "pop32-completed",
                PROJECT_ROOT / "tmp" / "pop30_completed",
                PROJECT_ROOT / "tmp" / "pop32-logs",
                PROJECT_ROOT / "outputs",
                OUTPUT_ROOT,
            ]

    target_map = {t.lower(): t for t in SHEET_INSTANCES}

    # Regex patterns
    job_re = re.compile(r"ph-showoa-(?:pop\d+|new)-([^-]+)-s(\d+)-n(\d+)", re.IGNORECASE)
    inst_start_re = re.compile(r"\[\d+/\d+\]\s+([A-Za-z0-9_]+):\s+start", re.IGNORECASE)
    inst_cmd_re = re.compile(r"--instances\s+([A-Za-z0-9_]+)", re.IGNORECASE)
    inst_log_name_re = re.compile(r"^([A-Za-z0-9_]+)_seed_(\d+)\.log", re.IGNORECASE)
    seed_re = re.compile(r"seed=(\d+)")
    done_re = re.compile(r"done in\s+([0-9:]+)\s+\|\s+NV=([\d.]+)\s+TD=([\d.]+)")
    done_sec_re = re.compile(r"done in\s+([\d.]+)s\s+\|\s+NV=([\d.]+)\s+TD=([\d.]+)")

    records: Dict[str, Dict[int, Tuple[float, float, float]]] = defaultdict(dict)

    # Step 1: Scan structured runs.csv files first for maximum fidelity
    csv_files: List[Path] = []
    for d in scan_dirs:
        if d.exists():
            for f in d.rglob("runs.csv"):
                if f.is_file():
                    if cutoff_date is not None:
                        try:
                            mtime = datetime.datetime.fromtimestamp(f.stat().st_mtime)
                            if mtime < cutoff_date:
                                continue
                        except Exception:
                            pass
                    csv_files.append(f)

    for csv_file in csv_files:
        path_str = str(csv_file).replace("\\", "/")
        # Determine instance from path
        inst = None
        for t in SHEET_INSTANCES:
            # Match boundary segments: /cdp203/ or /01_cdp203/
            if f"/{t.lower()}/" in path_str.lower() or f"/01_{t.lower()}/" in path_str.lower():
                inst = t
                break

        if not inst and "cdp202" in path_str.lower():
            inst = "Cdp202"

        if not inst:
            continue

        canonical = target_map.get(inst.lower())
        if not canonical:
            continue

        # Enforce Cdp202 directive
        if canonical == "Cdp202" and not include_baseline_cdp202:
            if "ph-showoa-new" not in path_str and "tafuhihi" not in path_str:
                continue

        try:
            with open(csv_file, "r", encoding="utf-8", errors="ignore") as fp:
                reader = csv.DictReader(fp)
                for row in reader:
                    if row.get("status") == "ok" or row.get("returncode") in ("0", 0):
                        seed = int(row["seed"])
                        nv = float(row["vehicles"])
                        td = float(row["distance"])
                        dur = float(row["duration_sec"])
                        records[canonical][seed] = (nv, td, dur)
        except Exception:
            continue

    # Step 2: Scan log files (.log, .txt, .out)
    log_files: List[Path] = []
    for d in scan_dirs:
        if d.exists():
            for f in d.rglob("*"):
                if f.is_file() and f.suffix in [".log", ".txt", ".out"]:
                    if cutoff_date is not None:
                        try:
                            mtime = datetime.datetime.fromtimestamp(f.stat().st_mtime)
                            if mtime < cutoff_date:
                                continue
                        except Exception:
                            pass
                    log_files.append(f)

    for f in log_files:
        try:
            content = f.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue

        if "done in" not in content and "vehicle (route) number" not in content:
            continue

        inst = None
        nm = inst_log_name_re.match(f.name)
        if nm:
            inst = nm.group(1)
        else:
            jm = job_re.search(str(f)) or job_re.search(content)
            if jm:
                inst = jm.group(1)
            else:
                sm = inst_start_re.search(content) or inst_cmd_re.search(content)
                if sm:
                    inst = sm.group(1)
                else:
                    for t in SHEET_INSTANCES:
                        f_path = str(f).replace("\\", "/")
                        if f"/{t}/" in f_path or f"/{t.lower()}/" in f_path:
                            inst = t
                            break

        if not inst or inst.lower() not in target_map:
            continue

        canonical = target_map[inst.lower()]

        # Enforce Cdp202 directive
        if canonical == "Cdp202" and not include_baseline_cdp202:
            if "ph-showoa-new" not in str(f) and "tafuhihi" not in str(f):
                continue

        curr_seed: Optional[int] = int(nm.group(2)) if nm else None

        for line in content.splitlines():
            sm = seed_re.search(line)
            if sm and ("run " in line or "seed=" in line):
                curr_seed = int(sm.group(1))

            dm = done_re.search(line)
            if dm and curr_seed is not None:
                d_str, nv_str, td_str = dm.groups()
                parts = d_str.split(":")
                if len(parts) == 3:
                    sec = int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
                elif len(parts) == 2:
                    sec = int(parts[0]) * 60 + int(parts[1])
                else:
                    sec = float(parts[0])
                if curr_seed not in records[canonical]:
                    records[canonical][curr_seed] = (float(nv_str), float(td_str), float(sec))
                if not nm:
                    curr_seed = None
                continue

            dm2 = done_sec_re.search(line)
            if dm2 and curr_seed is not None:
                sec_str, nv_str, td_str = dm2.groups()
                if curr_seed not in records[canonical]:
                    records[canonical][curr_seed] = (
                        float(nv_str),
                        float(td_str),
                        float(sec_str),
                    )
                if not nm:
                    curr_seed = None

    return records


def compute_instance_statistics(
    records: Dict[str, Dict[int, Tuple[float, float, float]]],
) -> Dict[str, Dict[str, Any]]:
    """
    Calculate statistical averages across 65 instances:
    - NV: average vehicle count (integer string or 2 decimal places)
    - TD: average distance (2 decimal places)
    - Avg/Run: average wall-clock duration formatted string
    """
    stats: Dict[str, Dict[str, Any]] = {}

    for idx, inst in enumerate(SHEET_INSTANCES, 1):
        row_num = idx + 2  # Row = STT + 2 (3 to 67)
        runs = records.get(inst, {})
        num_runs = len(runs)

        if num_runs > 0:
            nv_avg = sum(r[0] for r in runs.values()) / num_runs
            td_avg = sum(r[1] for r in runs.values()) / num_runs
            sec_avg = sum(r[2] for r in runs.values()) / num_runs

            nv_str = format_nv(nv_avg)
            td_str = format_td(td_avg)
            time_str = format_time(sec_avg)

            stats[inst] = {
                "stt": idx,
                "row": row_num,
                "runs_count": num_runs,
                "nv_avg": nv_avg,
                "td_avg": td_avg,
                "sec_avg": sec_avg,
                "nv_str": nv_str,
                "td_str": td_str,
                "time_str": time_str,
            }
        else:
            stats[inst] = {
                "stt": idx,
                "row": row_num,
                "runs_count": 0,
                "nv_avg": None,
                "td_avg": None,
                "sec_avg": None,
                "nv_str": "",
                "td_str": "",
                "time_str": "",
            }

    return stats


def generate_gsheets_payload(
    stats: Dict[str, Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Generate the batch mutation payload JSON structure."""
    data_matrix: List[List[str]] = []

    for inst in SHEET_INSTANCES:
        s = stats.get(inst, {})
        nv_str = s.get("nv_str", "")
        td_str = s.get("td_str", "")
        time_str = s.get("time_str", "")
        data_matrix.append([nv_str, td_str, time_str])

    return [
        {
            "op": "write",
            "range": SHEET_RANGE,
            "data": data_matrix,
        }
    ]


def save_gsheets_request(
    payload: List[Dict[str, Any]],
    output_path: Optional[Path] = None,
) -> Path:
    """Save update request payload to file."""
    if output_path is None:
        output_path = TMP_DIR / "gsheets_update_request.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as fp:
        json.dump(payload, fp, indent=2)
    return output_path


def execute_gsheets_mutation(
    payload_file: Path,
) -> Tuple[bool, str]:
    """Execute batch mutation on Google Sheet via CLI."""
    gsheets_exe = resolve_gsheets_cmd()
    cmd = [
        gsheets_exe,
        "mutate",
        "batch",
        SPREADSHEET_ID,
        "-f",
        str(payload_file),
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=60, shell=True)
        out = (res.stdout or "") + (res.stderr or "")
        return res.returncode == 0, out.strip()
    except Exception as exc:
        return False, str(exc)


def readback_gsheets_data() -> Tuple[bool, List[List[str]], str]:
    """Read back Columns G, H, I from Google Sheet tab Python_rerun_popsize30."""
    gsheets_exe = resolve_gsheets_cmd()
    cmd = [
        gsheets_exe,
        "readonly",
        "read",
        SPREADSHEET_ID,
        SHEET_RANGE,
        "--json",
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=60, shell=True)
        if res.returncode != 0:
            return False, [], (res.stderr or res.stdout).strip()
        data = json.loads(res.stdout)
        return True, data, ""
    except Exception as exc:
        return False, [], str(exc)


def are_cells_equal(exp: str, act: str) -> bool:
    """Compare expected and actual cell values, tolerating float trailing zeros."""
    if exp == act:
        return True
    if not exp and not act:
        return True
    try:
        f_exp = float(exp)
        f_act = float(act)
        return abs(f_exp - f_act) < 1e-3
    except ValueError:
        return False


def verify_readback(
    expected_matrix: List[List[str]],
    actual_matrix: List[List[str]],
) -> Tuple[bool, List[str]]:
    """Verify that sheet readback matches expected values for all 65 rows."""
    mismatches: List[str] = []
    for idx, inst in enumerate(SHEET_INSTANCES):
        row_num = idx + 3  # Row 3 to 67
        exp = expected_matrix[idx]
        act = actual_matrix[idx] if idx < len(actual_matrix) else ["", "", ""]

        # Pad actual row if trailing empty cells omitted by API
        act_padded = [act[c] if c < len(act) else "" for c in range(3)]

        cells_match = all(
            are_cells_equal(exp[c], act_padded[c]) for c in range(3)
        )
        if not cells_match:
            mismatches.append(
                f"Row {row_num} ({inst}): Expected {exp} but got {act_padded}"
            )

    return len(mismatches) == 0, mismatches


def run_pipeline(
    skip_harvest: bool = False,
    dry_run: bool = False,
    include_baseline_cdp202: bool = False,
    force_download: bool = False,
    cutoff_date: Optional[datetime.datetime] = DEFAULT_CUTOFF_DATE,
) -> int:
    """Run full harvest, parse, aggregate, and Google Sheet sync pipeline."""
    print("=" * 80)
    print("PH-SHOWOA KAGGLE HARVEST & GOOGLE SHEET SYNC PIPELINE")
    print("=" * 80)

    # Step 1: Harvest completed remote kernels
    if not skip_harvest:
        harvest_results = harvest_remote_kernels(force_download=force_download)
    else:
        print("\nSkipping Kaggle harvest step (--skip-harvest specified).")

    # Step 2: Parse all runs across 65 instances
    cutoff_desc = cutoff_date.strftime("%Y-%m-%d %H:%M:%S") if cutoff_date else "None (all historical)"
    print(f"\nScanning and parsing run outputs across 65 instances (Cutoff: {cutoff_desc})...")
    records = parse_all_runs(
        include_baseline_cdp202=include_baseline_cdp202,
        cutoff_date=cutoff_date,
    )
    print(f"Total instances with parsed records: {len(records)} / 65")

    # Step 3: Compute instance statistics
    stats = compute_instance_statistics(records)

    print("\n" + "-" * 80)
    print(f"{'Row':<5} | {'STT':<4} | {'Instance':<10} | {'Runs':<5} | {'NV':<6} | {'TD':<8} | {'Avg/Run':<10}")
    print("-" * 80)
    for inst in SHEET_INSTANCES:
        s = stats[inst]
        r_num = s["row"]
        stt = s["stt"]
        runs = s["runs_count"]
        nv = s["nv_str"] or "-"
        td = s["td_str"] or "-"
        tm = s["time_str"] or "-"
        print(f"{r_num:<5} | {stt:<4} | {inst:<10} | {runs:<5} | {nv:<6} | {td:<8} | {tm:<10}")
    print("-" * 80)

    # Step 4: Generate payload
    payload = generate_gsheets_payload(stats)
    req_file = save_gsheets_request(payload)
    print(f"\nGenerated Google Sheets update payload at: {req_file}")

    if dry_run:
        print("\n[DRY RUN] Mutation skipped. Pipeline complete.")
        return 0

    # Step 5: Synchronize Google Sheet
    print(f"\nMutating Google Sheet {SPREADSHEET_ID} for range {SHEET_RANGE}...")
    ok, msg = execute_gsheets_mutation(req_file)
    if not ok:
        print(f"ERROR: Google Sheet mutation failed: {msg}", file=sys.stderr)
        return 1
    print(f"Mutation successful: {msg[:100]}")

    # Step 6: Verify readback
    print("\nVerifying Google Sheet updated values via readback...")
    read_ok, actual_data, read_err = readback_gsheets_data()
    if not read_ok:
        print(f"ERROR: Google Sheet readback failed: {read_err}", file=sys.stderr)
        return 1

    expected_data = payload[0]["data"]
    match, mismatches = verify_readback(expected_data, actual_data)

    if match:
        print("\n" + "=" * 80)
        print("VERIFICATION SUCCESS: All 65 rows in Google Sheet match local aggregates 100%!")
        print("=" * 80 + "\n")
        return 0
    else:
        print("\nERROR: Verification failed with mismatches:", file=sys.stderr)
        for m in mismatches[:10]:
            print(f"  {m}", file=sys.stderr)
        return 1


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Harvest Kaggle kernel outputs and synchronize Google Sheet Python_rerun_popsize30."
    )
    parser.add_argument(
        "--skip-harvest",
        action="store_true",
        help="Skip remote Kaggle kernel harvesting and only perform local parsing & sync.",
    )
    parser.add_argument(
        "--harvest-only",
        action="store_true",
        help="Only harvest remote Kaggle kernel outputs without modifying Google Sheet.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse logs and generate payload without executing Google Sheet mutation.",
    )
    parser.add_argument(
        "--force-download",
        action="store_true",
        help="Force re-download of existing local Kaggle output bundles.",
    )
    parser.add_argument(
        "--include-baseline-cdp202",
        action="store_true",
        help="Include baseline Cdp202 runs (default: False, requires new solution from tafuhihi).",
    )
    parser.add_argument(
        "--no-cutoff",
        action="store_true",
        help="Include all historical runs without 2026-10-12 date cutoff.",
    )
    parser.add_argument(
        "--cutoff-date",
        type=str,
        default="2026-10-12",
        help="Cutoff date string in YYYY-MM-DD format (default: 2026-10-12).",
    )
    args = parser.parse_args()

    if args.harvest_only:
        harvest_remote_kernels(force_download=args.force_download)
        return 0

    if args.no_cutoff:
        cutoff_dt = None
    else:
        try:
            parts = [int(p) for p in args.cutoff_date.split("-")]
            cutoff_dt = datetime.datetime(parts[0], parts[1], parts[2], 0, 0, 0)
        except Exception:
            cutoff_dt = DEFAULT_CUTOFF_DATE

    return run_pipeline(
        skip_harvest=args.skip_harvest,
        dry_run=args.dry_run,
        include_baseline_cdp202=args.include_baseline_cdp202,
        force_download=args.force_download,
        cutoff_date=cutoff_dt,
    )


if __name__ == "__main__":
    sys.exit(main())
