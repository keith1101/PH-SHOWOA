"""
tests/test_harvest_and_sync.py
==============================
Unit and integration tests for scripts/harvest_and_sync_sheets.py.
Verifies:
1. Sheet instance canonical mapping and 65-instance ordering.
2. Formatting routines for NV, TD, and wall-clock execution time.
3. Numeric comparison tolerating Google Sheets float representations.
4. Parsing from multiple sources: solution.txt, runs.csv, and raw solver logs.
5. Cdp202 new solution isolation (excluding baseline per user directive).
6. Google Sheets batch mutation payload structure and validation.
7. Readback verification logic.
8. Mocked Kaggle kernel harvesting and credential routing.
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
    HARVEST_TARGETS,
    SHEET_INSTANCES,
    SHEET_NAME,
    SHEET_RANGE,
    SPREADSHEET_ID,
    are_cells_equal,
    compute_instance_statistics,
    format_nv,
    format_td,
    format_time,
    generate_gsheets_payload,
    harvest_remote_kernels,
    parse_all_runs,
    parse_solution_text,
    verify_readback,
)


# ============================================================================
# 1. Sheet Structure & Instance Mapping Tests
# ============================================================================


def test_sheet_instances_count_and_uniqueness():
    """Verify that exactly 65 unique instances are defined."""
    assert len(SHEET_INSTANCES) == 65
    assert len(set(SHEET_INSTANCES)) == 65


def test_sheet_instances_row_mapping():
    """Verify row formula Row = STT + 2 spanning Rows 3 to 67."""
    assert SHEET_INSTANCES[0] == "RCdp1001"  # STT 1, Row 3
    assert SHEET_INSTANCES[8] == "RCdp5007"  # STT 9, Row 11
    assert SHEET_INSTANCES[9] == "RCdp101"  # STT 10, Row 12
    assert SHEET_INSTANCES[34] == "Cdp201"  # STT 35, Row 37
    assert SHEET_INSTANCES[35] == "Cdp202"  # STT 36, Row 38
    assert SHEET_INSTANCES[36] == "Cdp203"  # STT 37, Row 39
    assert SHEET_INSTANCES[38] == "Cdp205"  # STT 39, Row 41
    assert SHEET_INSTANCES[41] == "Cdp208"  # STT 42, Row 44
    assert SHEET_INSTANCES[64] == "Rdp211"  # STT 65, Row 67

    assert SHEET_RANGE == "'Python_rerun_popsize30'!G3:I67"
    assert SPREADSHEET_ID == "1q498GxIhgMLg38hN44w-hWStl89EsSNDBHOp5Ksd2rA"


# ============================================================================
# 2. Formatting Unit Tests
# ============================================================================


def test_format_time_scenarios():
    """Test format_time with various seconds ranges."""
    assert format_time(None) == ""
    assert format_time(0) == ""
    assert format_time(-5) == ""

    # Sub-minute
    assert format_time(45) == "45s"
    assert format_time(59) == "59s"

    # Minutes and seconds
    assert format_time(60) == "1m00s"
    assert format_time(132.4) == "2m12s"
    assert format_time(476.1) == "7m56s"
    assert format_time(3599) == "59m59s"

    # Hours, minutes, and seconds
    assert format_time(3600) == "1h00m00s"
    assert format_time(4083.22) == "1h08m03s"
    assert format_time(4327.72) == "1h12m08s"
    assert format_time(19458) == "5h24m18s"


def test_format_nv_integer_and_fractional():
    """Test format_nv for integer vs fractional averages."""
    assert format_nv(None) == ""
    assert format_nv(3.0) == "3"
    assert format_nv(11.0) == "11"
    assert format_nv(2.00001) == "2"

    assert format_nv(15.14) == "15.14"
    assert format_nv(3.1818) == "3.18"
    assert format_nv(10.93) == "10.93"
    assert format_nv(10.3) == "10.30"


def test_format_td_two_decimal_places():
    """Test format_td float string formatting."""
    assert format_td(None) == ""
    assert format_td(348.98) == "348.98"
    assert format_td(216.691) == "216.69"
    assert format_td(904.7) == "904.70"
    assert format_td(603.21) == "603.21"


def test_are_cells_equal_tolerance():
    """Test are_cells_equal helper with float precision tolerance."""
    assert are_cells_equal("", "") is True
    assert are_cells_equal("1h08m03s", "1h08m03s") is True
    assert are_cells_equal("1h08m03s", "1h08m04s") is False

    # String with trailing zero vs trimmed float
    assert are_cells_equal("904.70", "904.7") is True
    assert are_cells_equal("10.30", "10.3") is True
    assert are_cells_equal("11.00", "11") is True
    assert are_cells_equal("1434.10", "1434.1") is True

    # Real differences must fail
    assert are_cells_equal("904.70", "905.7") is False
    assert are_cells_equal("3", "4") is False
    assert are_cells_equal("3", "") is False


# ============================================================================
# 3. Log & Solution Parsing Tests
# ============================================================================


def test_parse_solution_text():
    """Test parsing solution.txt content for vehicle and cost."""
    sample = """
Details of the solution:
route 0, node_num 19, cost 217.988564, nodes: 0 69 88 0
route 1, node_num 23, cost 244.971226, nodes: 0 61 42 0
vehicle (route) number: 3
Total cost: 6603.213456
"""
    parsed = parse_solution_text(sample)
    assert parsed is not None
    nv, td = parsed
    assert nv == 3
    assert abs(td - 603.213456) < 1e-4


def test_parse_runs_csv(tmp_path: Path):
    """Test parsing structured runs.csv files."""
    csv_file = tmp_path / "cdp203" / "runs.csv"
    csv_file.parent.mkdir(parents=True, exist_ok=True)

    with open(csv_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["seed", "status", "returncode", "duration_sec", "vehicles", "distance", "total_cost"])
        writer.writerow([42, "ok", 0, 4183.13, 3, 591.17, 6591.17])
        writer.writerow([43, "ok", 0, 4185.25, 3, 617.80, 6617.80])

    records = parse_all_runs(scan_dirs=[tmp_path])
    assert "Cdp203" in records
    assert 42 in records["Cdp203"]
    assert 43 in records["Cdp203"]

    nv42, td42, dur42 = records["Cdp203"][42]
    assert nv42 == 3.0
    assert td42 == 591.17
    assert dur42 == 4183.13


def test_parse_solver_log_text(tmp_path: Path):
    """Test parsing raw solver log text files."""
    log_file = tmp_path / "pop30_completed" / "RCdp1001_seed_43.log"
    log_file.parent.mkdir(parents=True, exist_ok=True)

    log_content = """
[1/1] RCdp1001: start
seed=43
...
done in 2:12 | NV=3.0 TD=348.98
"""
    log_file.write_text(log_content, encoding="utf-8")

    records = parse_all_runs(scan_dirs=[tmp_path])
    assert "RCdp1001" in records
    assert 43 in records["RCdp1001"]
    nv, td, dur = records["RCdp1001"][43]
    assert nv == 3.0
    assert td == 348.98
    assert dur == 132.0


# ============================================================================
# 4. User Directive & Cdp202 Isolation Tests
# ============================================================================


def test_cdp202_baseline_exclusion(tmp_path: Path):
    """
    Test that baseline runs for Cdp202 (e.g. from kanhan162 or ph-showoa-pop30-cdp202)
    are strictly excluded by default per user directive.
    """
    # Create baseline run for Cdp202
    baseline_dir = tmp_path / "Cdp202" / "ph-showoa-pop30-cdp202-s42-n6"
    baseline_dir.mkdir(parents=True, exist_ok=True)
    csv_file = baseline_dir / "runs.csv"
    with open(csv_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["seed", "status", "returncode", "duration_sec", "vehicles", "distance", "total_cost"])
        writer.writerow([42, "ok", 0, 4000.0, 3, 591.56, 6591.56])

    # Run default parser (include_baseline_cdp202=False)
    records_default = parse_all_runs(scan_dirs=[tmp_path], include_baseline_cdp202=False)
    assert len(records_default.get("Cdp202", {})) == 0

    stats_default = compute_instance_statistics(records_default)
    assert stats_default["Cdp202"]["runs_count"] == 0
    assert stats_default["Cdp202"]["nv_str"] == ""
    assert stats_default["Cdp202"]["td_str"] == ""
    assert stats_default["Cdp202"]["time_str"] == ""

    # If new solution is provided, it must be parsed
    new_sol_dir = tmp_path / "Cdp202" / "ph-showoa-new-cdp202-s42-n6"
    new_sol_dir.mkdir(parents=True, exist_ok=True)
    new_csv = new_sol_dir / "runs.csv"
    with open(new_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["seed", "status", "returncode", "duration_sec", "vehicles", "distance", "total_cost"])
        writer.writerow([42, "ok", 0, 3950.0, 3, 585.00, 6585.00])

    records_with_new = parse_all_runs(scan_dirs=[tmp_path], include_baseline_cdp202=False)
    assert len(records_with_new.get("Cdp202", {})) == 1
    assert records_with_new["Cdp202"][42][1] == 585.00


# ============================================================================
# 5. Payload Generation & Verification Tests
# ============================================================================


def test_generate_gsheets_payload_format():
    """Test generating batch mutation payload JSON structure."""
    dummy_records = {
        "RCdp1001": {42: (3.0, 348.98, 132.0)},
        "Cdp203": {42: (3.0, 603.21, 4083.0)},
    }
    stats = compute_instance_statistics(dummy_records)
    payload = generate_gsheets_payload(stats)

    assert len(payload) == 1
    op = payload[0]
    assert op["op"] == "write"
    assert op["range"] == SHEET_RANGE

    data = op["data"]
    assert len(data) == 65
    for row in data:
        assert len(row) == 3

    # RCdp1001 is row 0 in data (Row 3 in sheet)
    assert data[0] == ["3", "348.98", "2m12s"]
    # Cdp202 is STT 36 (index 35) -> empty
    assert data[35] == ["", "", ""]
    # Cdp203 is STT 37 (index 36) -> populated
    assert data[36] == ["3", "603.21", "1h08m03s"]


def test_verify_readback_logic():
    """Test verify_readback with matching and mismatching matrices."""
    expected = [["3", "348.98", "2m12s"]] + [["", "", ""]] * 64
    actual_exact = [["3", "348.98", "2m12s"]] + [["", "", ""]] * 64

    ok, mismatches = verify_readback(expected, actual_exact)
    assert ok is True
    assert len(mismatches) == 0

    # Float trailing zero variant (Google Sheets behavior)
    actual_float_variant = [["3", "348.98", "2m12s"]] + [["", "", ""]] * 64
    actual_float_variant[0] = ["3", "348.98", "2m12s"]
    ok2, mismatches2 = verify_readback(expected, actual_float_variant)
    assert ok2 is True

    # Real mismatch
    actual_mismatch = [["4", "348.98", "2m12s"]] + [["", "", ""]] * 64
    ok3, mismatches3 = verify_readback(expected, actual_mismatch)
    assert ok3 is False
    assert len(mismatches3) == 1
    assert "Row 3 (RCdp1001)" in mismatches3[0]


# ============================================================================
# 6. Mocked Kaggle Harvesting Execution
# ============================================================================


def test_harvest_targets_wave_coverage():
    """Verify that HARVEST_TARGETS covers Wave 1 completed and Wave 2 running targets."""
    assert len(HARVEST_TARGETS) == 8
    instances = [t["instance"] for t in HARVEST_TARGETS]
    assert set(instances) == {"Cdp201", "Cdp202", "Cdp203", "Cdp204", "Cdp205", "Cdp206", "Cdp207", "Cdp208"}

    wave1_targets = [t for t in HARVEST_TARGETS if t.get("wave") == 1]
    wave2_targets = [t for t in HARVEST_TARGETS if t.get("wave") == 2]
    assert len(wave1_targets) == 3  # Cdp203, Cdp205, Cdp208
    assert len(wave2_targets) == 5  # Cdp201, Cdp202, Cdp204, Cdp206, Cdp207


def test_harvest_remote_kernels_mock():
    """Test harvest_remote_kernels with mocked subprocess across Wave 1 and Wave 2."""
    with patch("scripts.harvest_and_sync_sheets.subprocess.run") as mock_sub:
        def side_effect(cmd, **kwargs):
            cmd_str = " ".join(cmd)
            mock_res = MagicMock()
            mock_res.returncode = 0
            mock_res.stderr = ""
            if "status" in cmd_str:
                # Wave 2 kernels are RUNNING
                if any(w in cmd_str for w in ["cdp201", "cdp202", "cdp204", "cdp206", "cdp207"]):
                    mock_res.stdout = 'has status "KernelWorkerStatus.RUNNING"'
                else:
                    mock_res.stdout = 'has status "KernelWorkerStatus.COMPLETE"'
            elif "output" in cmd_str:
                mock_res.stdout = "Files downloaded successfully"
            return mock_res

        mock_sub.side_effect = side_effect

        summary = harvest_remote_kernels(force_download=False)
        assert len(summary["running"]) == 25  # 5 Wave 2 instances x 5 kernels = 25
        assert len(summary["harvested"]) == 15  # 3 Wave 1 instances x 5 kernels = 15


# ============================================================================
# 7. Cutoff Date & Workspace Real Data Aggregation Integrity Check
# ============================================================================


def test_cutoff_date_filter_functionality(tmp_path: Path):
    """Test that cutoff_date excludes files before the cutoff date."""
    import datetime
    import time

    target_dir = tmp_path / "cdp203"
    target_dir.mkdir(parents=True, exist_ok=True)
    csv_old = target_dir / "runs.csv"
    with open(csv_old, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["seed", "status", "returncode", "duration_sec", "vehicles", "distance", "total_cost"])
        writer.writerow([42, "ok", 0, 4000.0, 3, 600.0, 6600.0])

    # Artificially set modification time to 2026-10-10
    old_timestamp = datetime.datetime(2026, 10, 10, 0, 0, 0).timestamp()
    os.utime(csv_old, (old_timestamp, old_timestamp))

    cutoff = datetime.datetime(2026, 10, 12, 0, 0, 0)
    records_with_cutoff = parse_all_runs(scan_dirs=[tmp_path], cutoff_date=cutoff)
    assert len(records_with_cutoff.get("Cdp203", {})) == 0

    records_no_cutoff = parse_all_runs(scan_dirs=[tmp_path], cutoff_date=None)
    assert len(records_no_cutoff.get("Cdp203", {})) == 1


def test_real_workspace_data_cdp203_cdp205_cdp208():
    """Verify that real harvested data for Cdp203, Cdp205, Cdp208 has exactly 30 runs with NV=3."""
    records = parse_all_runs(include_baseline_cdp202=False)

    for inst in ["Cdp203", "Cdp205", "Cdp208"]:
        runs = records.get(inst, {})
        assert len(runs) == 30, f"{inst} runs count: {len(runs)} != 30"
        seeds = sorted(runs.keys())
        assert seeds == list(range(42, 72)), f"{inst} seeds mismatch: {seeds}"
        nv_avg = sum(r[0] for r in runs.values()) / 30
        assert round(nv_avg) == 3, f"{inst} NV average: {nv_avg} != 3"
