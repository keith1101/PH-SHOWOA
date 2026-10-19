"""
Unit tests for scripts/kaggle_monitor.py.
Verifies kernel specification integrity, status parsing, state transition tracking,
and parameter auditing across all 25 Kaggle kernels.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scripts.kaggle_monitor import (
    KernelSpec,
    format_status_table,
    get_all_kernel_specs,
    query_kernel_status,
    update_state_and_detect_transitions,
    verify_remote_parameters,
)


def test_kernel_specifications_count_and_distribution():
    """Verify exactly 25 kernels defined across 5 accounts (5 kernels each)."""
    specs = get_all_kernel_specs()
    assert len(specs) == 25, f"Expected 25 kernels, got {len(specs)}"

    accounts = [s.account for s in specs]
    expected_accounts = ["tafuhihi", "account-b", "account-c", "account-d", "account-e"]
    for acc in expected_accounts:
        assert accounts.count(acc) == 5, f"Expected 5 kernels for account {acc}, got {accounts.count(acc)}"

    # tafuhihi must run Cdp202 with the new solution
    tafuhihi_specs = [s for s in specs if s.account == "tafuhihi"]
    for s in tafuhihi_specs:
        assert s.instance == "Cdp202"
        assert s.is_new_solution is True
        assert "ph-showoa-new-cdp202" in s.slug

    # Seed ranges must cover 42..71 across the 5 batches (n=6)
    expected_seeds = [42, 48, 54, 60, 66]
    for acc in expected_accounts:
        acc_specs = [s for s in specs if s.account == acc]
        actual_starts = [s.seed_start for s in acc_specs]
        assert actual_starts == expected_seeds, f"Account {acc} seeds mismatch: {actual_starts}"
        for s in acc_specs:
            assert s.repeats == 6


def test_status_parsing_logic():
    """Verify parsing of various stdout/stderr strings from Kaggle CLI."""
    spec = KernelSpec(
        account="tafuhihi",
        owner="tafuhihi",
        creds_dir=Path("/tmp"),
        instance="Cdp202",
        slug="test-slug",
        seed_start=42,
        repeats=6,
        is_new_solution=True,
        solution_label="New",
    )

    test_cases = [
        ('tafuhihi/test-slug has status "KernelWorkerStatus.RUNNING"', "RUNNING", 0),
        ('tafuhihi/test-slug has status "KernelWorkerStatus.COMPLETE"', "COMPLETE", 0),
        ('tafuhihi/test-slug has status "KernelWorkerStatus.ERROR"', "ERROR", 0),
        ('tafuhihi/test-slug has status "KernelWorkerStatus.QUEUED"', "QUEUED", 0),
        ('404 - Not Found', "NOT_FOUND", 1),
    ]

    for stdout_text, expected_status, returncode in test_cases:
        with patch("subprocess.run") as mock_run:
            mock_proc = MagicMock()
            mock_proc.stdout = stdout_text
            mock_proc.stderr = "" if returncode == 0 else stdout_text
            mock_proc.returncode = returncode
            mock_run.return_value = mock_proc

            res = query_kernel_status(spec, kaggle_exe="dummy_kaggle")
            assert res["status"] == expected_status, f"Expected {expected_status} for '{stdout_text}', got {res['status']}"


def test_state_transition_detection(tmp_path: Path):
    """Verify transitions from RUNNING to COMPLETE or ERROR are detected and recorded."""
    state_file = tmp_path / "test_state.json"

    # Initial cycle: 2 kernels running
    results_cycle_1 = [
        {
            "ref": "tafuhihi/kernel-1",
            "account": "tafuhihi",
            "owner": "tafuhihi",
            "instance": "Cdp202",
            "seeds_range": "42..47",
            "status": "RUNNING",
            "is_new_solution": True,
        },
        {
            "ref": "kanhan162/kernel-2",
            "account": "account-b",
            "owner": "kanhan162",
            "instance": "Cdp202",
            "seeds_range": "42..47",
            "status": "RUNNING",
            "is_new_solution": False,
        },
    ]

    state_1, transitions_1 = update_state_and_detect_transitions(results_cycle_1, state_file)
    assert len(transitions_1) == 0, "Initial run should have no transitions"
    assert state_1["kernels"]["tafuhihi/kernel-1"]["status"] == "RUNNING"

    # Cycle 2: kernel-1 completes, kernel-2 encounters error
    results_cycle_2 = [
        {
            "ref": "tafuhihi/kernel-1",
            "account": "tafuhihi",
            "owner": "tafuhihi",
            "instance": "Cdp202",
            "seeds_range": "42..47",
            "status": "COMPLETE",
            "is_new_solution": True,
        },
        {
            "ref": "kanhan162/kernel-2",
            "account": "account-b",
            "owner": "kanhan162",
            "instance": "Cdp202",
            "seeds_range": "42..47",
            "status": "ERROR",
            "is_new_solution": False,
        },
    ]

    state_2, transitions_2 = update_state_and_detect_transitions(results_cycle_2, state_file)
    assert len(transitions_2) == 2, f"Expected 2 transitions, got {len(transitions_2)}"

    t1 = next(t for t in transitions_2 if t["ref"] == "tafuhihi/kernel-1")
    assert t1["from_status"] == "RUNNING"
    assert t1["to_status"] == "COMPLETE"

    t2 = next(t for t in transitions_2 if t["ref"] == "kanhan162/kernel-2")
    assert t2["from_status"] == "RUNNING"
    assert t2["to_status"] == "ERROR"


def test_verify_remote_parameters():
    """Verify that all 25 jobs meet remote execution parameters."""
    audit = verify_remote_parameters()
    assert audit["total_audited"] == 25
    assert audit["all_match"] is True

    for detail in audit["details"]:
        assert detail["backends_cpu"] is True, f"Kernel {detail['ref']} missing cpu backend"
        assert detail["pop_size_30"] is True, f"Kernel {detail['ref']} missing pop_size 30"
        assert detail["max_iter_1000"] is True, f"Kernel {detail['ref']} missing max_iter 1000"
        assert detail["paper_flags"] is True, f"Kernel {detail['ref']} missing paper_flags"
        assert detail["timeout_43200"] is True, f"Kernel {detail['ref']} missing timeout 43200"
        assert detail["all_passed"] is True


def test_format_status_table_rendering():
    """Verify table formatting output structure."""
    dummy_results = [
        {
            "ref": "tafuhihi/ph-showoa-new-cdp202-s42-n6",
            "account": "tafuhihi",
            "owner": "tafuhihi",
            "instance": "Cdp202",
            "seeds_range": "42..47",
            "status": "RUNNING",
            "is_new_solution": True,
            "error_msg": "",
        }
    ]
    dummy_transitions = [
        {
            "ref": "tafuhihi/ph-showoa-new-cdp202-s42-n6",
            "instance": "Cdp202",
            "seeds_range": "42..47",
            "from_status": "RUNNING",
            "to_status": "COMPLETE",
            "timestamp": "2026-10-12T15:00:00Z",
        }
    ]

    table = format_status_table(dummy_results, dummy_transitions)
    assert "KAGGLE DISTRIBUTED KERNEL MONITOR" in table
    assert "tafuhihi" in table
    assert "Cdp202" in table
    assert "RUNNING" in table
    assert "STATUS TRANSITIONS DETECTED THIS CYCLE" in table
    assert "COMPLETE" in table
