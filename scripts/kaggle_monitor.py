#!/usr/bin/env python3
"""
Kaggle Distributed Multi-Account Kernel Monitor.

Monitors all 25 active Kaggle kernels across the 5 authenticated accounts:
1. tafuhihi (5 kernels, Cdp202 new solution with seeds 42..71)
2. kanhan162 / account-b (5 kernels, Cdp202 pop30 seeds 42..71)
3. dautromduoicuop / account-c (5 kernels, Cdp203 pop30 seeds 42..71)
4. keith1101 / account-d (5 kernels, Cdp205 pop30 seeds 42..71)
5. giahaohuynh / account-e (5 kernels, Cdp208 pop30 seeds 42..71)

Features:
- Handles per-account KAGGLE_CONFIG_DIR authentication.
- Detects transitions from RUNNING to COMPLETE or ERROR.
- Thread-pooled concurrent queries for rapid updates (~5s for 25 kernels).
- State persistence to track status changes over time.
- Verifies remote parameters match:
  --backends cpu --pop_size 30 --max_iter 1000 --paper_flags --timeout 43200.
- Zero heavy CPU usage on local machine.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import datetime
import json
import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Default paths
DEFAULT_KAGGLE_EXE = r"C:\Users\LENOVO\miniconda3\envs\phshowoa\Scripts\kaggle.exe"
DEFAULT_CREDS_ROOT = Path(r"D:\Project\Kaggle\credentials")
DEFAULT_ROOT_CREDS = Path(r"C:\Users\LENOVO\.kaggle")
DEFAULT_STATE_FILE = Path(r"D:\Project\PH-SHOWOA\tmp\kaggle_monitor_state.json")
DEFAULT_JOBS_ROOT = Path(r"D:\Project\Kaggle\jobs_pop30")
DEFAULT_TAFUHIHI_JOBS_ROOT = Path(r"D:\Project\PH-SHOWOA\build_jobs_tafuhihi")


@dataclass
class KernelSpec:
    account: str
    owner: str
    creds_dir: Path
    instance: str
    slug: str
    seed_start: int
    repeats: int
    is_new_solution: bool
    solution_label: str
    notebook_path: Path | None = None

    @property
    def ref(self) -> str:
        return f"{self.owner}/{self.slug}"

    @property
    def seeds_range(self) -> str:
        return f"{self.seed_start}..{self.seed_start + self.repeats - 1}"


def get_all_kernel_specs() -> list[KernelSpec]:
    """Define all 25 active kernels across the 5 authenticated accounts."""
    specs: list[KernelSpec] = []
    seeds = [42, 48, 54, 60, 66]
    repeats = 6

    # 1. Account tafuhihi (5 kernels, Cdp202 new solution)
    for s in seeds:
        slug = f"ph-showoa-new-cdp202-s{s}-n{repeats}"
        nb_path = DEFAULT_TAFUHIHI_JOBS_ROOT / slug / "ph-showoa.ipynb"
        if not nb_path.exists():
            nb_path = Path("D:/Project/PH-SHOWOA/build_kernel_tafuhihi/ph-showoa.ipynb")
        specs.append(
            KernelSpec(
                account="tafuhihi",
                owner="tafuhihi",
                creds_dir=DEFAULT_ROOT_CREDS,
                instance="Cdp202",
                slug=slug,
                seed_start=s,
                repeats=repeats,
                is_new_solution=True,
                solution_label="New Solution (Pruning + Active Elim + SA)",
                notebook_path=nb_path if nb_path.exists() else None,
            )
        )

    # 2. Account-b: kanhan162 (5 kernels, Cdp202 pop30)
    for s in seeds:
        slug = f"ph-showoa-pop30-cdp202-s{s}-n{repeats}"
        nb_path = DEFAULT_JOBS_ROOT / "account-b" / slug / "ph-showoa.ipynb"
        specs.append(
            KernelSpec(
                account="account-b",
                owner="kanhan162",
                creds_dir=DEFAULT_CREDS_ROOT / "account-b",
                instance="Cdp202",
                slug=slug,
                seed_start=s,
                repeats=repeats,
                is_new_solution=False,
                solution_label="Baseline pop30",
                notebook_path=nb_path if nb_path.exists() else None,
            )
        )

    # 3. Account-c: dautromduoicuop (5 kernels, Cdp203 pop30)
    for s in seeds:
        slug = f"ph-showoa-pop30-cdp203-s{s}-n{repeats}"
        nb_path = DEFAULT_JOBS_ROOT / "account-c" / slug / "ph-showoa.ipynb"
        specs.append(
            KernelSpec(
                account="account-c",
                owner="dautromduoicuop",
                creds_dir=DEFAULT_CREDS_ROOT / "account-c",
                instance="Cdp203",
                slug=slug,
                seed_start=s,
                repeats=repeats,
                is_new_solution=False,
                solution_label="Baseline pop30",
                notebook_path=nb_path if nb_path.exists() else None,
            )
        )

    # 4. Account-d: keith1101 (5 kernels, Cdp205 pop30)
    for s in seeds:
        slug = f"ph-showoa-pop30-cdp205-s{s}-n{repeats}"
        nb_path = DEFAULT_JOBS_ROOT / "account-d" / slug / "ph-showoa.ipynb"
        specs.append(
            KernelSpec(
                account="account-d",
                owner="keith1101",
                creds_dir=DEFAULT_CREDS_ROOT / "account-d",
                instance="Cdp205",
                slug=slug,
                seed_start=s,
                repeats=repeats,
                is_new_solution=False,
                solution_label="Baseline pop30",
                notebook_path=nb_path if nb_path.exists() else None,
            )
        )

    # 5. Account-e: giahaohuynh (5 kernels, Cdp208 pop30)
    for s in seeds:
        slug = f"ph-showoa-pop30-cdp208-s{s}-n{repeats}"
        nb_path = DEFAULT_JOBS_ROOT / "account-e" / slug / "ph-showoa.ipynb"
        specs.append(
            KernelSpec(
                account="account-e",
                owner="giahaohuynh",
                creds_dir=DEFAULT_CREDS_ROOT / "account-e",
                instance="Cdp208",
                slug=slug,
                seed_start=s,
                repeats=repeats,
                is_new_solution=False,
                solution_label="Baseline pop30",
                notebook_path=nb_path if nb_path.exists() else None,
            )
        )

    return specs


def resolve_kaggle_exe(custom_path: str | None = None) -> str:
    """Locate the kaggle CLI executable."""
    if custom_path and Path(custom_path).exists():
        return custom_path
    if Path(DEFAULT_KAGGLE_EXE).exists():
        return DEFAULT_KAGGLE_EXE
    found = shutil.which("kaggle")
    if found:
        return found
    return "kaggle"


def query_kernel_status(spec: KernelSpec, kaggle_exe: str, timeout: int = 30) -> dict[str, Any]:
    """
    Query the status of a single Kaggle kernel using its account credentials.
    Returns structured result dict.
    """
    env = os.environ.copy()
    env["KAGGLE_CONFIG_DIR"] = str(spec.creds_dir)

    cmd = [kaggle_exe, "kernels", "status", spec.ref]
    query_time = datetime.datetime.now(datetime.timezone.utc).isoformat()

    try:
        proc = subprocess.run(
            cmd,
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        raw_stdout = proc.stdout.strip()
        raw_stderr = proc.stderr.strip()
        error_msg = (raw_stderr or raw_stdout) if proc.returncode != 0 else ""

        # Parse status from output with robust precedence:
        # Check explicit error codes and failure tokens before matching RUNNING
        status = "UNKNOWN"
        if "404 - Not Found" in raw_stdout or "404 - Not Found" in raw_stderr:
            status = "NOT_FOUND"
        elif proc.returncode != 0:
            if "getaddrinfo failed" in raw_stderr or "connection" in raw_stderr.lower() or "connection" in raw_stdout.lower():
                status = "NETWORK_ERROR"
            elif "KernelWorkerStatus.ERROR" in raw_stdout or '"ERROR"' in raw_stdout:
                status = "ERROR"
            else:
                status = f"ERROR_CODE_{proc.returncode}"
        else:
            # proc.returncode == 0
            # Prioritize ERROR over RUNNING to prevent ambiguous crashes being misclassified
            if "KernelWorkerStatus.ERROR" in raw_stdout or '"ERROR"' in raw_stdout:
                status = "ERROR"
                if not error_msg:
                    error_msg = raw_stderr or raw_stdout
            elif "KernelWorkerStatus.COMPLETE" in raw_stdout or '"COMPLETE"' in raw_stdout:
                status = "COMPLETE"
            elif "KernelWorkerStatus.RUNNING" in raw_stdout or '"RUNNING"' in raw_stdout:
                status = "RUNNING"
            elif "KernelWorkerStatus.QUEUED" in raw_stdout or '"QUEUED"' in raw_stdout:
                status = "QUEUED"
            elif "KernelWorkerStatus.CANCELING" in raw_stdout or '"CANCELING"' in raw_stdout:
                status = "CANCELING"
            elif "KernelWorkerStatus.CANCELED" in raw_stdout or '"CANCELED"' in raw_stdout:
                status = "CANCELED"
            elif raw_stdout:
                # Fallback regex search for quoted word
                m = re.search(r'status ["\']?([A-Za-z0-9_.]+)["\']?', raw_stdout)
                if m:
                    status = m.group(1).replace("KernelWorkerStatus.", "")

        return {
            "ref": spec.ref,
            "account": spec.account,
            "owner": spec.owner,
            "instance": spec.instance,
            "slug": spec.slug,
            "seed_start": spec.seed_start,
            "repeats": spec.repeats,
            "seeds_range": spec.seeds_range,
            "is_new_solution": spec.is_new_solution,
            "solution_label": spec.solution_label,
            "status": status,
            "raw_output": raw_stdout or raw_stderr,
            "exit_code": proc.returncode,
            "checked_at": query_time,
            "error_msg": error_msg,
        }

    except subprocess.TimeoutExpired:
        return {
            "ref": spec.ref,
            "account": spec.account,
            "owner": spec.owner,
            "instance": spec.instance,
            "slug": spec.slug,
            "seed_start": spec.seed_start,
            "repeats": spec.repeats,
            "seeds_range": spec.seeds_range,
            "is_new_solution": spec.is_new_solution,
            "solution_label": spec.solution_label,
            "status": "TIMEOUT",
            "raw_output": "",
            "exit_code": -1,
            "checked_at": query_time,
            "error_msg": f"Command timed out after {timeout}s",
        }
    except Exception as exc:
        return {
            "ref": spec.ref,
            "account": spec.account,
            "owner": spec.owner,
            "instance": spec.instance,
            "slug": spec.slug,
            "seed_start": spec.seed_start,
            "repeats": spec.repeats,
            "seeds_range": spec.seeds_range,
            "is_new_solution": spec.is_new_solution,
            "solution_label": spec.solution_label,
            "status": "EXCEPTION",
            "raw_output": "",
            "exit_code": -1,
            "checked_at": query_time,
            "error_msg": str(exc),
        }


def query_all_kernels_concurrent(
    specs: list[KernelSpec],
    kaggle_exe: str,
    max_workers: int = 5,
    timeout: int = 30,
) -> list[dict[str, Any]]:
    """Query all kernels concurrently across accounts."""
    results: list[dict[str, Any]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_map = {
            executor.submit(query_kernel_status, spec, kaggle_exe, timeout): spec
            for spec in specs
        }
        for future in concurrent.futures.as_completed(future_map):
            try:
                res = future.result()
                results.append(res)
            except Exception as exc:
                spec = future_map[future]
                results.append({
                    "ref": spec.ref,
                    "account": spec.account,
                    "owner": spec.owner,
                    "instance": spec.instance,
                    "slug": spec.slug,
                    "seed_start": spec.seed_start,
                    "repeats": spec.repeats,
                    "seeds_range": spec.seeds_range,
                    "is_new_solution": spec.is_new_solution,
                    "solution_label": spec.solution_label,
                    "status": "THREAD_ERROR",
                    "raw_output": "",
                    "exit_code": -1,
                    "checked_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    "error_msg": str(exc),
                })

    # Sort results in predictable original order
    order_map = {spec.ref: idx for idx, spec in enumerate(specs)}
    results.sort(key=lambda item: order_map.get(item["ref"], 999))
    return results


def update_state_and_detect_transitions(
    current_results: list[dict[str, Any]],
    state_file: Path,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """
    Compare current statuses with persisted state to detect status transitions.
    Saves updated state to state_file.
    Returns (state_dict, transition_events).
    """
    state_file.parent.mkdir(parents=True, exist_ok=True)
    previous_state: dict[str, Any] = {}
    if state_file.exists():
        try:
            previous_state = json.loads(state_file.read_text(encoding="utf-8"))
        except Exception:
            previous_state = {}

    prev_kernels = previous_state.get("kernels", {})
    transitions: list[dict[str, Any]] = []
    # Merge rather than clobber: preserve existing kernel records across filtered queries
    updated_kernels: dict[str, Any] = dict(prev_kernels)
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

    for item in current_results:
        ref = item["ref"]
        current_status = item["status"]
        prev_data = prev_kernels.get(ref, {})
        prev_status = prev_data.get("status")

        # Detect transition
        if prev_status and prev_status != current_status:
            event = {
                "ref": ref,
                "account": item["account"],
                "owner": item["owner"],
                "instance": item["instance"],
                "seeds_range": item["seeds_range"],
                "from_status": prev_status,
                "to_status": current_status,
                "timestamp": now_iso,
            }
            transitions.append(event)

        # Merge history
        history = list(prev_data.get("history", []))
        if prev_status != current_status:
            history.append({
                "from": prev_status,
                "to": current_status,
                "at": now_iso,
            })

        updated_kernels[ref] = {
            "status": current_status,
            "last_checked": now_iso,
            "previous_status": prev_status,
            "history": history,
            "details": {
                "account": item["account"],
                "owner": item["owner"],
                "instance": item["instance"],
                "seeds_range": item["seeds_range"],
                "is_new_solution": item["is_new_solution"],
            },
        }

    new_state = {
        "last_updated": now_iso,
        "total_kernels": len(updated_kernels),
        "kernels": updated_kernels,
        "recent_transitions": transitions + previous_state.get("recent_transitions", [])[:20],
    }

    try:
        tmp_target = state_file.with_suffix(".tmp")
        tmp_target.write_text(json.dumps(new_state, indent=2), encoding="utf-8")
        os.replace(tmp_target, state_file)
    except Exception as exc:
        print(f"Warning: Failed to persist state to {state_file}: {exc}", file=sys.stderr)

    return new_state, transitions


def verify_remote_parameters() -> dict[str, Any]:
    """
    Verify that all 25 kernel configurations match the required execution parameters:
    --backends cpu --pop_size 30 --max_iter 1000 --paper_flags --timeout 43200
    """
    required_flags = {
        "backends": "cpu",
        "pop_size": "30",
        "max_iter": "1000",
        "paper_flags": True,
        "timeout": "43200",
    }

    specs = get_all_kernel_specs()
    audit_results: list[dict[str, Any]] = []
    all_match = True

    for spec in specs:
        # Check source notebook if available
        matched_flags = {}
        source_found = False
        nb_code = ""

        if spec.notebook_path and spec.notebook_path.exists():
            try:
                nb_content = json.loads(spec.notebook_path.read_text(encoding="utf-8"))
                for cell in nb_content.get("cells", []):
                    if cell.get("cell_type") == "code":
                        source_lines = "".join(cell.get("source", []))
                        nb_code += source_lines + "\n"
                source_found = True
            except Exception:
                pass

        if not source_found:
            # Fallback to generator scripts
            if spec.account == "tafuhihi":
                push_script = Path(r"D:\Project\PH-SHOWOA\scripts\push_tafuhihi_batches.py")
                if push_script.exists():
                    nb_code = push_script.read_text(encoding="utf-8")
                    source_found = True

        # Inspect flags in code with strict regex word boundaries
        # Supporting both CLI syntax (--backends cpu) and Python list elements ('--backends', 'cpu')
        arg_sep = r'(?:["\']?,\s*["\']?|\s+)'
        has_backends_cpu = bool(re.search(rf'--backends{arg_sep}cpu\b', nb_code))
        has_pop_size_30 = bool(re.search(rf'--pop_size{arg_sep}30\b', nb_code))
        has_max_iter_1000 = bool(re.search(rf'--max_iter{arg_sep}1000\b', nb_code))
        has_timeout_43200 = bool(re.search(rf'--timeout{arg_sep}43200\b', nb_code))

        # In kaggle_run.py line 84: parser.add_argument('--paper_flags', default=True)
        # Therefore, paper_flags is enabled if passed explicitly OR by default unless --no_paper_flags is given.
        has_no_paper_flags = bool(re.search(r'--no_paper_flags\b', nb_code))
        explicit_paper_flags = bool(re.search(r'--paper_flags\b', nb_code))

        if has_no_paper_flags:
            paper_flags_enabled = False
            paper_flags_mode = "DISABLED"
        elif explicit_paper_flags:
            paper_flags_enabled = True
            paper_flags_mode = "EXPLICIT"
        else:
            paper_flags_enabled = True
            paper_flags_mode = "DEFAULT (ON)"

        spec_pass = (
            has_backends_cpu
            and has_pop_size_30
            and has_max_iter_1000
            and has_timeout_43200
            and paper_flags_enabled
        )

        if not spec_pass:
            all_match = False

        audit_results.append({
            "ref": spec.ref,
            "account": spec.account,
            "instance": spec.instance,
            "seeds": spec.seeds_range,
            "source_verified": source_found,
            "backends_cpu": has_backends_cpu,
            "pop_size_30": has_pop_size_30,
            "max_iter_1000": has_max_iter_1000,
            "paper_flags": paper_flags_enabled,
            "paper_flags_mode": paper_flags_mode,
            "timeout_43200": has_timeout_43200,
            "all_passed": spec_pass,
        })

    return {
        "required_parameters": required_flags,
        "total_audited": len(audit_results),
        "all_match": all_match,
        "details": audit_results,
    }


def format_status_table(
    results: list[dict[str, Any]],
    transitions: list[dict[str, Any]] | None = None,
) -> str:
    """Format kernel statuses as an ASCII table."""
    lines: list[str] = []
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    lines.append("=" * 110)
    lines.append(f"  KAGGLE DISTRIBUTED KERNEL MONITOR -- 25 ACTIVE REMOTE WORKERS  ({now_str})")
    lines.append("=" * 110)

    # Column widths
    # No | Account | Owner | Inst | Seeds | Version | Status | Checked
    header = (
        f"{'#':<3} | {'Account':<11} | {'Owner':<16} | {'Inst':<7} | {'Seeds':<8} "
        f"| {'Algorithm Version':<30} | {'Status':<10} | {'Notes'}"
    )
    lines.append(header)
    lines.append("-" * 110)

    counts: dict[str, int] = {}
    for idx, r in enumerate(results, start=1):
        status = r["status"]
        counts[status] = counts.get(status, 0) + 1

        version_short = (
            "NEW (Pruning+RouteElim+SA)" if r["is_new_solution"] else "Baseline pop30"
        )
        err = (r.get("error_msg") or r.get("raw_output") or "").strip().replace("\n", " ")
        err_short = err[:28] if err else ""

        notes = ""
        if status == "COMPLETE":
            notes = "SUCCESS (Ready to Harvest)"
        elif status == "RUNNING":
            notes = "Active on Remote Worker"
        elif status == "QUEUED":
            notes = "Waiting in Queue"
        elif status == "CANCELING":
            notes = "Canceling..."
        elif status == "CANCELED":
            notes = "CANCELED by User"
        elif status == "ERROR":
            notes = f"FAIL: {err_short}" if err_short else "Execution Failed"
        elif status == "TIMEOUT":
            notes = f"TIMEOUT: {err_short}" if err_short else "Command Timed Out"
        elif status == "NETWORK_ERROR":
            notes = f"NET_ERR: {err_short}" if err_short else "Network Unreachable"
        elif status == "NOT_FOUND":
            notes = "Kernel Not Found (404)"
        elif r.get("exit_code", 0) != 0 or "ERROR" in status:
            notes = f"FAIL ({status}): {err_short}" if err_short else f"FAIL ({status})"
        else:
            notes = f"{status}: {err_short}" if err_short else status

        row = (
            f"{idx:<3} | {r['account']:<11} | {r['owner']:<16} | {r['instance']:<7} | {r['seeds_range']:<8} "
            f"| {version_short:<30} | {status:<10} | {notes}"
        )
        lines.append(row)

    lines.append("-" * 110)

    # Summary bar
    summary_parts = [f"{k}: {v}" for k, v in sorted(counts.items())]
    lines.append(f"  SUMMARY [Total: {len(results)}] -> " + " | ".join(summary_parts))
    lines.append("=" * 110)

    # Transition alerts
    if transitions:
        lines.append("\n" + "!" * 80)
        lines.append("  STATUS TRANSITIONS DETECTED THIS CYCLE:")
        for t in transitions:
            icon = "[COMPLETE]" if t["to_status"] == "COMPLETE" else ("[ERROR]" if t["to_status"] == "ERROR" else "[INFO]")
            lines.append(
                f"  {icon} [{t['timestamp']}] {t['ref']} ({t['instance']} {t['seeds_range']}): "
                f"{t['from_status']} -> {t['to_status']}"
            )
        lines.append("!" * 80)

    return "\n".join(lines)


def print_parameter_audit_report(audit: dict[str, Any]) -> None:
    """Print the verification report for remote execution parameters."""
    print("\n" + "=" * 90)
    print("  REMOTE EXECUTION PARAMETERS VERIFICATION AUDIT")
    print("=" * 90)
    print("  Required Parameters:")
    for k, v in audit["required_parameters"].items():
        print(f"    --{k:<15} : {v}")
    print("-" * 90)
    print(
        f"{'#':<3} | {'Account':<11} | {'Instance':<7} | {'Seeds':<8} | "
        f"{'cpu':<5} | {'pop30':<5} | {'iter1000':<8} | {'paper_flags':<11} | {'timeout':<7} | {'Result'}"
    )
    print("-" * 90)

    for idx, d in enumerate(audit["details"], start=1):
        cpu_ok = "PASS" if d["backends_cpu"] else "FAIL"
        pop_ok = "PASS" if d["pop_size_30"] else "FAIL"
        iter_ok = "PASS" if d["max_iter_1000"] else "FAIL"
        paper_ok = d.get("paper_flags_mode", "PASS" if d["paper_flags"] else "FAIL")
        to_ok = "PASS" if d["timeout_43200"] else "FAIL"
        res = "MATCHED" if d["all_passed"] else "MISMATCH"

        print(
            f"{idx:<3} | {d['account']:<11} | {d['instance']:<7} | {d['seeds']:<8} | "
            f"{cpu_ok:<5} | {pop_ok:<5} | {iter_ok:<8} | {paper_ok:<12} | {to_ok:<7} | {res}"
        )

    print("-" * 90)
    overall = "100% VERIFIED - ALL 25 KERNELS MATCH" if audit["all_match"] else "VERIFICATION FAILED"
    print(f"  OVERALL AUDIT: {overall}")
    print("=" * 90 + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Monitor all 25 active Kaggle kernels across 5 accounts."
    )
    parser.add_argument(
        "--kaggle_exe",
        default=DEFAULT_KAGGLE_EXE,
        help="Path to kaggle.exe CLI binary.",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=5,
        help="Number of concurrent query worker threads (default: 5).",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=30,
        help="Timeout in seconds per query (default: 30).",
    )
    parser.add_argument(
        "--watch",
        action="store_true",
        help="Run continuously in watch/polling mode without consuming local CPU.",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=60,
        help="Polling interval in seconds when --watch is active (default: 60).",
    )
    parser.add_argument(
        "--state-file",
        type=Path,
        default=DEFAULT_STATE_FILE,
        help="Path to JSON state file for tracking transitions.",
    )
    parser.add_argument(
        "--account",
        type=str,
        default=None,
        help="Filter kernels by specific account (e.g., 'tafuhihi', 'account-b').",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON to stdout.",
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        default=None,
        help="Save status snapshot to specified JSON file.",
    )
    parser.add_argument(
        "--verify-params",
        action="store_true",
        help="Audit and verify remote execution parameters across all 25 jobs.",
    )

    args = parser.parse_args()

    # Step 1: Verify parameters if requested
    if args.verify_params:
        audit = verify_remote_parameters()
        print_parameter_audit_report(audit)
        if not args.watch and not args.json:
            return 0 if audit["all_match"] else 1

    # Step 2: Resolve specs
    all_specs = get_all_kernel_specs()
    if args.account:
        all_specs = [s for s in all_specs if s.account.lower() == args.account.lower()]
        if not all_specs:
            print(f"Error: No kernels configured for account '{args.account}'", file=sys.stderr)
            return 1

    kaggle_bin = resolve_kaggle_exe(args.kaggle_exe)

    # Step 3: Run monitoring loop or single snapshot
    iteration = 0
    try:
        while True:
            iteration += 1
            results = query_all_kernels_concurrent(
                specs=all_specs,
                kaggle_exe=kaggle_bin,
                max_workers=args.workers,
                timeout=args.timeout,
            )

            state, transitions = update_state_and_detect_transitions(
                current_results=results,
                state_file=args.state_file,
            )

            if args.output_json:
                args.output_json.parent.mkdir(parents=True, exist_ok=True)
                args.output_json.write_text(
                    json.dumps(results, indent=2), encoding="utf-8"
                )

            if args.json:
                print(json.dumps(results, indent=2))
            else:
                table = format_status_table(results, transitions)
                print(table)

            if not args.watch:
                break

            time.sleep(args.interval)

    except KeyboardInterrupt:
        print("\nMonitoring stopped by user.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
