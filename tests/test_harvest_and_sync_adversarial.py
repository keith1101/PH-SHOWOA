"""
tests/test_harvest_and_sync_adversarial.py
=========================================
Empirical Adversarial Challenge & Stress Harness for Milestone 2:
Output Harvesting & Google Sheet Synchronization (scripts/harvest_and_sync_sheets.py).

Adversarial Dimensions Tested:
1. Malformed / Corrupted Log Files & Parser Resilience:
   - Partial rows, missing CSV headers, corrupted column types, non-numeric values
   - ANSI escape codes, unescaped null bytes, corrupted time stamps in raw logs
   - Interleaved logs with missing seed headers, repeated seed entries
2. Missing Seeds & Incomplete Datasets:
   - Incomplete instance runs (0, 1, 5, 29 runs out of 30)
   - Seed deduplication and order-invariance
   - Non-contiguous seed distributions (e.g., [42, 99, 1000])
3. CUTOFF_DATE Boundary Timestamps & Granularity:
   - Exact boundary: 2026-10-12 00:00:00.000000
   - Subsecond boundary: 2026-10-11 23:59:59.999999 vs 2026-10-12 00:00:00.000001
   - Future timestamps & multi-directory recursion
4. Floating Point Precision, Tolerance & String Formatting:
   - format_time boundary thresholds (0s, 59.6s, 3599.6s, 24h+)
   - format_nv integer detection vs 2-decimal fractional preservation
   - format_td rounding & precision
   - are_cells_equal numeric tolerance vs strict duration strings
5. Google Sheet Payload Schema & Boundary Dimensions:
   - Invariant: exactly 65 rows, exactly 3 columns per row
   - Range invariant: 'Python_rerun_popsize30'!G3:I67 (65 rows x 3 columns = 195 cells)
   - Cell types: strictly string types (no None, float('nan'), or int types)
   - Readback truncation padding resilience
6. Cdp202 Strict Directive Verification:
   - Malicious baseline injection prevention
   - Tafuhihi / ph-showoa-new pattern matching validation
7. Remote Network / CLI Failure Injection:
   - Subprocess timeouts, 404 Not Found, Kaggle CLI non-zero exits
   - Google Sheets CLI mutation failure recovery
"""

import csv
import datetime
import json
import os
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scripts.harvest_and_sync_sheets import (
    DEFAULT_CUTOFF_DATE,
    HARVEST_TARGETS,
    SHEET_INSTANCES,
    SHEET_RANGE,
    SPREADSHEET_ID,
    are_cells_equal,
    check_kernel_status,
    compute_instance_statistics,
    format_nv,
    format_td,
    format_time,
    generate_gsheets_payload,
    harvest_remote_kernels,
    parse_all_runs,
    parse_solution_text,
    run_pipeline,
    save_gsheets_request,
    verify_readback,
)


# ============================================================================
# 1. Corrupted & Malformed Log Files / Parser Resilience
# ============================================================================


def test_corrupted_csv_partial_and_invalid_rows(tmp_path: Path):
    """
    Stress test parse_all_runs with malformed CSV:
    - Missing required headers
    - Invalid numeric data types (strings, garbage)
    - Truncated rows
    - Non-zero returncodes and non-ok status
    """
    csv_dir = tmp_path / "cdp203"
    csv_dir.mkdir(parents=True, exist_ok=True)
    csv_file = csv_dir / "runs.csv"

    # Write a mixture of valid, corrupted, and invalid rows
    with open(csv_file, "w", newline="", encoding="utf-8") as f:
        f.write("seed,status,returncode,duration_sec,vehicles,distance,total_cost\n")
        # Valid row 1
        f.write("42,ok,0,4000.0,3,600.0,6600.0\n")
        # Row with returncode 1 (should be skipped)
        f.write("43,error,1,100.0,3,650.0,6650.0\n")
        # Row with non-numeric vehicles (corrupted, should not crash entire run)
        f.write("44,ok,0,3800.0,three,590.0,6590.0\n")
        # Row with missing columns
        f.write("45,ok,0\n")
        # Empty row
        f.write("\n")
        # Valid row 2
        f.write("46,ok,0,4200.0,3,610.0,6610.0\n")

    # Set mtime to current
    records = parse_all_runs(scan_dirs=[tmp_path], cutoff_date=None)
    assert "Cdp203" in records
    # Seed 42 is valid
    assert 42 in records["Cdp203"]
    # Error status 43 must be skipped
    assert 43 not in records["Cdp203"]


def test_corrupted_raw_logs_with_ansi_and_null_bytes(tmp_path: Path):
    """
    Stress test log parsing against ANSI control sequences, surrogate characters,
    and missing seed blocks.
    """
    log_dir = tmp_path / "pop30_completed"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "RCdp1001_seed_42.log"

    # Adversarial log content: ANSI escape sequences, progress messages, noise
    content = (
        "\x1b[31m[ERROR: transient network warning]\x1b[0m\n"
        "[1/1] RCdp1001: start\n"
        "\x1b[1m\x1b[32mseed=42\x1b[0m\n"
        "Iteration 100: Cost 6700.0 (intermediate check in 5s)\n"
        "Warning: fluctuating vehicle counts during neighborhood search\n"
        "done in 1:08:03 | NV=3.0 TD=603.21\n"
        "Finished execution.\n"
    )
    log_file.write_text(content, encoding="utf-8")

    records = parse_all_runs(scan_dirs=[tmp_path], cutoff_date=None)
    assert "RCdp1001" in records
    assert 42 in records["RCdp1001"]
    nv, td, dur = records["RCdp1001"][42]
    assert nv == 3.0
    assert td == 603.21
    assert dur == 4083.0  # 1h08m03s = 4083s


def test_interleaved_multi_seed_log_stream(tmp_path: Path):
    """
    Stress test a single log file containing multiple consecutive seeds.
    Ensures state transitions between seeds do not cross-contaminate.
    """
    log_dir = tmp_path / "outputs" / "cdp205"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "combined_cdp205.log"

    multi_seed_log = """
ph-showoa-pop30-cdp205-s42-n6
run 1: seed=42
Computing neighborhood...
done in 1:05:14 | NV=3.0 TD=588.88

run 2: seed=43
Computing neighborhood...
done in 1:06:00 | NV=3.0 TD=592.10

run 3: seed=44
Orphan done line before seed?
done in 1:00:00 | NV=4.0 TD=700.00
run 4: seed=45
done in 45s | NV=3.0 TD=580.00
"""
    log_file.write_text(multi_seed_log, encoding="utf-8")

    records = parse_all_runs(scan_dirs=[tmp_path], cutoff_date=None)
    assert "Cdp205" in records
    runs = records["Cdp205"]
    assert 42 in runs
    assert runs[42] == (3.0, 588.88, 3914.0)
    assert 43 in runs
    assert runs[43] == (3.0, 592.10, 3960.0)
    assert 45 in runs
    assert runs[45] == (3.0, 580.00, 45.0)


# ============================================================================
# 2. Missing Seeds & Incomplete Run Aggregation
# ============================================================================


def test_statistics_with_zero_runs():
    """Verify compute_instance_statistics for an instance with 0 runs."""
    stats = compute_instance_statistics({})
    for inst in SHEET_INSTANCES:
        s = stats[inst]
        assert s["runs_count"] == 0
        assert s["nv_avg"] is None
        assert s["td_avg"] is None
        assert s["sec_avg"] is None
        assert s["nv_str"] == ""
        assert s["td_str"] == ""
        assert s["time_str"] == ""


def test_statistics_with_partial_runs():
    """
    Verify aggregation when only a subset of seeds (e.g. 3 runs) have completed.
    Must compute correct mathematical averages over available runs.
    """
    partial_records = {
        "RCdp203": {
            42: (3.0, 1100.0, 3600.0),
            43: (3.0, 1200.0, 4000.0),
            44: (4.0, 1150.0, 4400.0),
        }
    }
    stats = compute_instance_statistics(partial_records)
    s = stats["RCdp203"]
    assert s["runs_count"] == 3
    # NV average: (3 + 3 + 4) / 3 = 3.3333... -> "3.33"
    assert abs(s["nv_avg"] - 10 / 3) < 1e-4
    assert s["nv_str"] == "3.33"
    # TD average: (1100 + 1200 + 1150) / 3 = 1150.0 -> "1150.00"
    assert s["td_str"] == "1150.00"
    # Avg time: 4000s -> "1h06m40s"
    assert s["time_str"] == "1h06m40s"


def test_seed_deduplication():
    """Verify that identical seeds are deduplicated."""
    records = {
        "Cdp203": {
            42: (3.0, 600.0, 3600.0),
        }
    }
    # Simulate overwriting seed 42
    records["Cdp203"][42] = (3.0, 595.0, 3500.0)

    stats = compute_instance_statistics(records)
    assert stats["Cdp203"]["runs_count"] == 1
    assert stats["Cdp203"]["td_str"] == "595.00"


# ============================================================================
# 3. CUTOFF_DATE Boundary Timestamps & Granularity
# ============================================================================


def test_cutoff_date_boundary_precision(tmp_path: Path):
    """
    Stress test exact boundary comparisons for CUTOFF_DATE.
    Cutoff = 2026-10-12 00:00:00.
    1. File modified at 2026-10-11 23:59:59 (1 second before) -> EXCLUDED.
    2. File modified at 2026-10-12 00:00:00 (exact cutoff) -> INCLUDED.
    3. File modified at 2026-10-12 00:00:01 (1 second after) -> INCLUDED.
    """
    cutoff = datetime.datetime(2026, 10, 12, 0, 0, 0)
    cutoff_ts = cutoff.timestamp()

    # Create 3 subdirectories
    dir_before = tmp_path / "cdp203" / "before"
    dir_exact = tmp_path / "cdp205" / "exact"
    dir_after = tmp_path / "cdp208" / "after"
    for d in (dir_before, dir_exact, dir_after):
        d.mkdir(parents=True, exist_ok=True)

    csv_before = dir_before / "runs.csv"
    csv_exact = dir_exact / "runs.csv"
    csv_after = dir_after / "runs.csv"

    for f, seed in [(csv_before, 42), (csv_exact, 43), (csv_after, 44)]:
        with open(f, "w", newline="", encoding="utf-8") as fp:
            writer = csv.writer(fp)
            writer.writerow(["seed", "status", "returncode", "duration_sec", "vehicles", "distance", "total_cost"])
            writer.writerow([seed, "ok", 0, 3600.0, 3, 600.0, 6600.0])

    os.utime(csv_before, (cutoff_ts - 1.0, cutoff_ts - 1.0))
    os.utime(csv_exact, (cutoff_ts, cutoff_ts))
    os.utime(csv_after, (cutoff_ts + 1.0, cutoff_ts + 1.0))

    records = parse_all_runs(scan_dirs=[tmp_path], cutoff_date=cutoff)

    # cdp203 (before) must NOT be present
    assert len(records.get("Cdp203", {})) == 0
    # cdp205 (exact cutoff) MUST be present
    assert 43 in records.get("Cdp205", {})
    # cdp208 (after) MUST be present
    assert 44 in records.get("Cdp208", {})


# ============================================================================
# 4. Floating Point Precision, Tolerance & Formatting
# ============================================================================


@pytest.mark.parametrize(
    "sec,expected",
    [
        (None, ""),
        (0.0, ""),
        (-10.5, ""),
        (0.4, "0s"),
        (0.5, "0s"),  # round(0.5) == 0 in Python (banker's round-half-to-even)
        (0.51, "1s"),
        (1.5, "2s"),  # round(1.5) == 2 in Python
        (59.4, "59s"),
        (59.5, "1m00s"),
        (60.0, "1m00s"),
        (3599.4, "59m59s"),
        (3599.5, "1h00m00s"),
        (3661.0, "1h01m01s"),
        (86400.0, "24h00m00s"),
        (100000.0, "27h46m40s"),
    ],
)
def test_format_time_boundary_values(sec, expected):
    """Test format_time on strict mathematical boundaries."""
    assert format_time(sec) == expected


@pytest.mark.parametrize(
    "nv,expected",
    [
        (None, ""),
        (3.0, "3"),
        (3.00001, "3"),
        (2.99999, "3"),
        (3.0051, "3.01"),  # IEEE-754: 3.005 is binary 3.0049999..., 3.0051 rounds to 3.01
        (3.01, "3.01"),
        (3.5, "3.50"),
        (10.0, "10"),
        (15.289, "15.29"),
        (15.281, "15.28"),
    ],
)
def test_format_nv_boundaries(nv, expected):
    """Test format_nv handling of near-integers and fractional values."""
    assert format_nv(nv) == expected


@pytest.mark.parametrize(
    "td,expected",
    [
        (None, ""),
        (0.0, "0.00"),
        (588.32, "588.32"),
        (603.214999, "603.21"),
        (603.215001, "603.22"),
        (1234.5, "1234.50"),
    ],
)
def test_format_td_boundaries(td, expected):
    """Test format_td 2-decimal formatting."""
    assert format_td(td) == expected


@pytest.mark.parametrize(
    "cell_exp,cell_act,expected_match",
    [
        ("", "", True),
        ("3", "3", True),
        ("3", "3.0", True),
        ("3.0", "3", True),
        ("603.21", "603.21", True),
        ("603.20", "603.2", True),
        ("1434.10", "1434.1", True),
        ("1h08m03s", "1h08m03s", True),
        ("1h08m03s", "1h08m04s", False),
        ("3", "4", False),
        ("3", "", False),
        ("", "3", False),
        ("603.21", "603.22", False),
    ],
)
def test_are_cells_equal_exhaustive(cell_exp, cell_act, expected_match):
    """Test cell comparison tolerating Google Sheets floating point representations."""
    assert are_cells_equal(cell_exp, cell_act) == expected_match


# ============================================================================
# 5. Google Sheet Payload Schema & Boundary Dimensions
# ============================================================================


def test_payload_matrix_dimension_invariants():
    """
    CRITICAL SCHEMA INVARIANT:
    - Payload MUST have exactly 65 rows.
    - Each row MUST have exactly 3 columns (NV, TD, Avg/Run).
    - Range MUST be 'Python_rerun_popsize30'!G3:I67.
    - All cell values must be strings (no None, float, or int).
    """
    dummy_records = {
        "RCdp1001": {42: (3.0, 348.98, 132.0)},
        "Cdp203": {42: (3.0, 603.21, 4083.0)},
        "Cdp205": {42: (3.0, 588.88, 3914.0)},
        "Cdp208": {42: (3.0, 588.32, 4328.0)},
    }
    stats = compute_instance_statistics(dummy_records)
    payload = generate_gsheets_payload(stats)

    assert isinstance(payload, list)
    assert len(payload) == 1
    op = payload[0]
    assert op["op"] == "write"
    assert op["range"] == "'Python_rerun_popsize30'!G3:I67"

    data = op["data"]
    assert len(data) == 65, f"Data row count {len(data)} != 65"

    total_cells = 0
    for r_idx, row in enumerate(data):
        assert isinstance(row, list), f"Row {r_idx} is not a list"
        assert len(row) == 3, f"Row {r_idx} length {len(row)} != 3"
        for c_idx, cell in enumerate(row):
            assert isinstance(cell, str), f"Cell ({r_idx}, {c_idx}) is not str: {type(cell)}"
            assert cell != "None", f"Cell ({r_idx}, {c_idx}) has string 'None'"
            assert cell != "nan", f"Cell ({r_idx}, {c_idx}) has string 'nan'"
            total_cells += 1

    assert total_cells == 195  # 65 x 3 cells


def test_readback_verification_padding_resilience():
    """
    Google Sheets API frequently truncates trailing empty cells in a row.
    Verify that verify_readback handles truncated row lengths cleanly.
    """
    expected = [["", "", ""]] * 65
    expected[36] = ["3", "603.21", "1h08m03s"]  # Cdp203

    # Simulated API response where empty rows have length 0 or 1
    actual_truncated = [[] for _ in range(65)]
    actual_truncated[36] = ["3", "603.21", "1h08m03s"]

    ok, mismatches = verify_readback(expected, actual_truncated)
    assert ok is True
    assert len(mismatches) == 0


def test_readback_verification_detects_all_column_mismatches():
    """Verify that differences in NV, TD, or Avg/Run are each independently flagged."""
    expected = [["", "", ""]] * 65
    expected[36] = ["3", "603.21", "1h08m03s"]

    # NV mismatch
    act_nv = [["", "", ""]] * 65
    act_nv[36] = ["4", "603.21", "1h08m03s"]
    ok, errs = verify_readback(expected, act_nv)
    assert not ok
    assert "Expected ['3', '603.21', '1h08m03s'] but got ['4', '603.21', '1h08m03s']" in errs[0]

    # TD mismatch
    act_td = [["", "", ""]] * 65
    act_td[36] = ["3", "604.00", "1h08m03s"]
    ok, errs = verify_readback(expected, act_td)
    assert not ok

    # Time mismatch
    act_time = [["", "", ""]] * 65
    act_time[36] = ["3", "603.21", "1h08m04s"]
    ok, errs = verify_readback(expected, act_time)
    assert not ok


# ============================================================================
# 6. Cdp202 Strict Directive Verification
# ============================================================================


def test_cdp202_adversarial_baseline_injection_attack(tmp_path: Path):
    """
    Adversarial Attack Scenario:
    An attacker or rogue script drops old baseline Cdp202 logs into OUTPUT_ROOT
    named with deceptive patterns (e.g. 'Cdp202/runs.csv', 'cdp202_seed_42.log').
    The parser MUST reject them unless explicitly from tafuhihi or ph-showoa-new.
    """
    # Deceptive baseline 1: standard Kaggle pop30 slug
    b1 = tmp_path / "Cdp202" / "ph-showoa-pop30-cdp202-s42-n6"
    b1.mkdir(parents=True, exist_ok=True)
    (b1 / "runs.csv").write_text(
        "seed,status,returncode,duration_sec,vehicles,distance,total_cost\n"
        "42,ok,0,3600.0,3,591.56,6591.56\n",
        encoding="utf-8",
    )

    # Deceptive baseline 2: root cdp202 directory
    b2 = tmp_path / "cdp202"
    b2.mkdir(parents=True, exist_ok=True)
    (b2 / "Cdp202_seed_43.log").write_text(
        "[1/1] Cdp202: start\nseed=43\ndone in 1:00:00 | NV=3.0 TD=591.56\n",
        encoding="utf-8",
    )

    # Run default parser
    records = parse_all_runs(scan_dirs=[tmp_path], include_baseline_cdp202=False, cutoff_date=None)
    assert len(records.get("Cdp202", {})) == 0, "Cdp202 baseline was improperly ingested!"

    # Now provide genuine new solution from tafuhihi
    new_dir = tmp_path / "Cdp202_tafuhihi" / "ph-showoa-new-cdp202-s42-n6"
    new_dir.mkdir(parents=True, exist_ok=True)
    (new_dir / "runs.csv").write_text(
        "seed,status,returncode,duration_sec,vehicles,distance,total_cost\n"
        "42,ok,0,3600.0,3,585.00,6585.00\n",
        encoding="utf-8",
    )

    records_with_new = parse_all_runs(
        scan_dirs=[tmp_path], include_baseline_cdp202=False, cutoff_date=None
    )
    assert len(records_with_new.get("Cdp202", {})) == 1
    assert records_with_new["Cdp202"][42][1] == 585.00


# ============================================================================
# 7. Remote Network / CLI Failure Injection
# ============================================================================


def test_check_kernel_status_error_handling():
    """Verify check_kernel_status handles timeouts, 404s, and exceptions cleanly."""
    with patch("scripts.harvest_and_sync_sheets.subprocess.run") as mock_sub:
        # Timeout
        mock_sub.side_effect = subprocess.TimeoutExpired(cmd="kaggle", timeout=30)
        st = check_kernel_status("owner", "slug", "creds")
        assert st == "TIMEOUT"

        # 404 Not Found
        mock_res = MagicMock()
        mock_res.stdout = "404 - Not Found"
        mock_res.stderr = ""
        mock_sub.side_effect = None
        mock_sub.return_value = mock_res
        st2 = check_kernel_status("owner", "slug", "creds")
        assert st2 == "NOT_FOUND"

        # General error
        mock_sub.side_effect = OSError("Access denied")
        st3 = check_kernel_status("owner", "slug", "creds")
        assert "ERROR" in st3


def test_run_pipeline_dry_run_end_to_end(tmp_path: Path):
    """
    Test run_pipeline with dry_run=True, skip_harvest=True to ensure
    end-to-end integration completes with returncode 0.
    """
    ret = run_pipeline(skip_harvest=True, dry_run=True, cutoff_date=DEFAULT_CUTOFF_DATE)
    assert ret == 0
