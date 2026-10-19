"""
Empirical Adversarial Challenge Suite (Challenger 2).
Exposes and reproduces verified failure modes in scripts/kaggle_monitor.py:
1. Parameter verification evasion (false positives on --no_paper_flags, pop_size, backends, max_iter).
2. State persistence corruption and record drops during filtered queries.
3. Silent loss of state transition alerts after account filtering.
4. Exit code 0 masking verification failures in CLI mode.
5. Status parsing priority flaw for ambiguous error outputs.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scripts.kaggle_monitor import (
    KernelSpec,
    get_all_kernel_specs,
    query_kernel_status,
    update_state_and_detect_transitions,
    verify_remote_parameters,
)


def test_reproduce_no_paper_flags_evasion_bug(tmp_path: Path):
    """
    CRITICAL BUG 1:
    --no_paper_flags is falsely reported as paper_flags=True with mode 'EXPLICIT'.
    Cause: 'paper_flags' in nb_code matches inside '--no_paper_flags'.
    """
    nb = tmp_path / "test_nb.ipynb"
    nb.write_text(json.dumps({
        "cells": [{
            "cell_type": "code",
            "source": ["python kaggle_run.py --backends cpu --pop_size 30 --max_iter 1000 --timeout 43200 --no_paper_flags"]
        }]
    }), encoding="utf-8")

    fake_spec = KernelSpec(
        account="account-b",
        owner="kanhan162",
        creds_dir=tmp_path,
        instance="Cdp202",
        slug="test-slug",
        seed_start=42,
        repeats=6,
        is_new_solution=False,
        solution_label="Baseline",
        notebook_path=nb,
    )

    with patch("scripts.kaggle_monitor.get_all_kernel_specs", return_value=[fake_spec]):
        audit = verify_remote_parameters()
        detail = audit["details"][0]

        # REMEDIATED BEHAVIOR:
        # Instead of reporting paper_flags=True, it strictly flags paper_flags=False and DISABLED
        assert detail["paper_flags"] is False, "--no_paper_flags correctly flagged as False"
        assert detail["paper_flags_mode"] == "DISABLED", "paper_flags_mode correctly marked DISABLED"
        assert detail["all_passed"] is False
        assert audit["all_match"] is False


def test_reproduce_pop_size_false_positive_bug(tmp_path: Path):
    """
    CRITICAL BUG 2 REMEDIATION:
    --pop_size 50 is rejected even when '30' appears in a comment.
    """
    nb = tmp_path / "test_pop.ipynb"
    nb.write_text(json.dumps({
        "cells": [{
            "cell_type": "code",
            "source": [
                "python kaggle_run.py --backends cpu --pop_size 50 --max_iter 1000 --timeout 43200 --paper_flags\n",
                "# Target repeats = 30\n"
            ]
        }]
    }), encoding="utf-8")

    fake_spec = KernelSpec(
        account="account-b",
        owner="kanhan162",
        creds_dir=tmp_path,
        instance="Cdp202",
        slug="test-slug",
        seed_start=42,
        repeats=6,
        is_new_solution=False,
        solution_label="Baseline",
        notebook_path=nb,
    )

    with patch("scripts.kaggle_monitor.get_all_kernel_specs", return_value=[fake_spec]):
        audit = verify_remote_parameters()
        detail = audit["details"][0]

        assert detail["pop_size_30"] is False, "pop_size 50 rejected despite '30' in comment"
        assert detail["all_passed"] is False
        assert audit["all_match"] is False


def test_reproduce_backends_gpu_false_positive_bug(tmp_path: Path):
    """
    CRITICAL BUG 3 REMEDIATION:
    --backends gpu is rejected even when 'cpu' appears in os.cpu_count().
    """
    nb = tmp_path / "test_gpu.ipynb"
    nb.write_text(json.dumps({
        "cells": [{
            "cell_type": "code",
            "source": [
                "import os\n",
                "print('Logical CPUs:', os.cpu_count())\n",
                "python kaggle_run.py --backends gpu --pop_size 30 --max_iter 1000 --timeout 43200 --paper_flags\n"
            ]
        }]
    }), encoding="utf-8")

    fake_spec = KernelSpec(
        account="account-b",
        owner="kanhan162",
        creds_dir=tmp_path,
        instance="Cdp202",
        slug="test-slug",
        seed_start=42,
        repeats=6,
        is_new_solution=False,
        solution_label="Baseline",
        notebook_path=nb,
    )

    with patch("scripts.kaggle_monitor.get_all_kernel_specs", return_value=[fake_spec]):
        audit = verify_remote_parameters()
        detail = audit["details"][0]

        assert detail["backends_cpu"] is False, "--backends gpu rejected despite 'cpu' in script"
        assert detail["all_passed"] is False
        assert audit["all_match"] is False


def test_reproduce_max_iter_prefix_matching_bug(tmp_path: Path):
    """
    CRITICAL BUG 4 REMEDIATION:
    --max_iter 10000 is rejected due to strict word boundary check.
    """
    nb = tmp_path / "test_iter.ipynb"
    nb.write_text(json.dumps({
        "cells": [{
            "cell_type": "code",
            "source": [
                "python kaggle_run.py --backends cpu --pop_size 30 --max_iter 10000 --timeout 43200 --paper_flags\n"
            ]
        }]
    }), encoding="utf-8")

    fake_spec = KernelSpec(
        account="account-b",
        owner="kanhan162",
        creds_dir=tmp_path,
        instance="Cdp202",
        slug="test-slug",
        seed_start=42,
        repeats=6,
        is_new_solution=False,
        solution_label="Baseline",
        notebook_path=nb,
    )

    with patch("scripts.kaggle_monitor.get_all_kernel_specs", return_value=[fake_spec]):
        audit = verify_remote_parameters()
        detail = audit["details"][0]

        assert detail["max_iter_1000"] is False, "--max_iter 10000 rejected due to boundary match"
        assert detail["all_passed"] is False
        assert audit["all_match"] is False


def test_reproduce_state_loss_on_account_filtering(tmp_path: Path):
    """
    CRITICAL BUG 5:
    Querying a subset of kernels (e.g. filtered by account) purges all other
    kernel records from the persistent state file, corrupting state and history.
    """
    state_file = tmp_path / "test_state.json"

    # Initial state with 25 kernels
    all_kernels = [
        {
            "ref": f"account_{i // 5}/kernel_{i}",
            "account": f"account_{i // 5}",
            "owner": f"owner_{i // 5}",
            "instance": "Cdp202",
            "seeds_range": "42..47",
            "status": "RUNNING",
            "is_new_solution": (i // 5 == 0),
        }
        for i in range(25)
    ]
    state1, _ = update_state_and_detect_transitions(all_kernels, state_file)
    assert len(state1["kernels"]) == 25

    # Filtered query for account_0 (5 kernels)
    filtered_kernels = [k for k in all_kernels if k["account"] == "account_0"]
    assert len(filtered_kernels) == 5

    state2, _ = update_state_and_detect_transitions(filtered_kernels, state_file)

    # REMEDIATED BEHAVIOR: state_file retains all 25 kernels; unmonitored kernels are merged
    assert len(state2["kernels"]) == 25, "All 25 kernels preserved after filtered query"
    persisted = json.loads(state_file.read_text(encoding="utf-8"))
    assert len(persisted["kernels"]) == 25, "All 25 kernels preserved on disk in state file"


def test_reproduce_missed_state_transitions_after_purge(tmp_path: Path):
    """
    CRITICAL BUG 6 REMEDIATION:
    Transitions for unmonitored kernels are captured when they complete,
    because their state was not purged during filtered runs.
    """
    state_file = tmp_path / "test_state.json"

    all_kernels = [
        {
            "ref": f"account_{i // 5}/kernel_{i}",
            "account": f"account_{i // 5}",
            "owner": f"owner_{i // 5}",
            "instance": "Cdp202",
            "seeds_range": "42..47",
            "status": "RUNNING",
            "is_new_solution": (i // 5 == 0),
        }
        for i in range(25)
    ]
    # Step 1: full initial run (all RUNNING)
    update_state_and_detect_transitions(all_kernels, state_file)

    # Step 2: filtered run (only account_0 monitored)
    filtered = [k for k in all_kernels if k["account"] == "account_0"]
    update_state_and_detect_transitions(filtered, state_file)

    # Step 3: next full run, kernel 6 (account_1) transitioned from RUNNING to COMPLETE
    updated_all = list(all_kernels)
    updated_all[6] = dict(updated_all[6])
    updated_all[6]["status"] = "COMPLETE"

    state3, transitions3 = update_state_and_detect_transitions(updated_all, state_file)

    # REMEDIATED BEHAVIOR: transition for kernel_6 is successfully captured
    t_k6 = [t for t in transitions3 if t["ref"] == "account_1/kernel_6"]
    assert len(t_k6) == 1, "Transition from RUNNING to COMPLETE for kernel 6 captured"
    assert t_k6[0]["from_status"] == "RUNNING"
    assert t_k6[0]["to_status"] == "COMPLETE"
    k6_history = state3["kernels"]["account_1/kernel_6"]["history"]
    assert k6_history[-1]["from"] == "RUNNING"
    assert k6_history[-1]["to"] == "COMPLETE"


def test_reproduce_ambiguous_stdout_misparsed_as_running():
    """
    CRITICAL BUG 7 REMEDIATION:
    If stdout contains both RUNNING and ERROR (e.g. error diagnostic referencing running state),
    ERROR check is prioritized over RUNNING.
    """
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

    ambiguous_output = 'KernelWorkerStatus.ERROR: Notebook crashed while in KernelWorkerStatus.RUNNING state'

    with patch("subprocess.run") as mock_run:
        mock_proc = MagicMock()
        mock_proc.stdout = ambiguous_output
        mock_proc.stderr = ""
        mock_proc.returncode = 0
        mock_run.return_value = mock_proc

        res = query_kernel_status(spec, kaggle_exe="dummy_kaggle")
        assert res["status"] == "ERROR", "ERROR output correctly recognized rather than misclassified as RUNNING"
        assert "ERROR" in res["error_msg"]


def test_verify_params_clean_exit_code():
    """Verify that --verify-params returns 0 on match and 1 on mismatch without query fall-through."""
    from scripts.kaggle_monitor import main
    with patch("scripts.kaggle_monitor.verify_remote_parameters") as mock_verify, \
         patch("scripts.kaggle_monitor.print_parameter_audit_report"), \
         patch("sys.argv", ["kaggle_monitor.py", "--verify-params"]):
        mock_verify.return_value = {"all_match": True, "required_parameters": {}, "details": []}
        ret_pass = main()
        assert ret_pass == 0

        mock_verify.return_value = {"all_match": False, "required_parameters": {}, "details": []}
        ret_fail = main()
        assert ret_fail == 1


def test_http_401_error_capture_from_stdout():
    """Verify HTTP 401 error message in raw_stdout is captured in error_msg."""
    spec = KernelSpec(
        account="account-b",
        owner="kanhan162",
        creds_dir=Path("/tmp"),
        instance="Cdp202",
        slug="test-slug",
        seed_start=42,
        repeats=6,
        is_new_solution=False,
        solution_label="Baseline",
    )
    with patch("subprocess.run") as mock_run:
        mock_proc = MagicMock()
        mock_proc.returncode = 1
        mock_proc.stdout = "401 Client Error: Unauthorized for url: https://www.kaggle.com/api/v1/kernels/status"
        mock_proc.stderr = ""
        mock_run.return_value = mock_proc

        res = query_kernel_status(spec, kaggle_exe="dummy_kaggle")
        assert res["status"] == "ERROR_CODE_1"
        assert "401 Client Error" in res["error_msg"]


def test_format_status_table_error_notes():
    """Verify formatted table notes show diagnostics for various failure statuses."""
    from scripts.kaggle_monitor import format_status_table
    results = [
        {
            "account": "tafuhihi",
            "owner": "tafuhihi",
            "instance": "Cdp202",
            "seeds_range": "42..47",
            "is_new_solution": True,
            "status": "NETWORK_ERROR",
            "exit_code": 1,
            "error_msg": "DNS getaddrinfo failed",
        },
        {
            "account": "account-b",
            "owner": "kanhan162",
            "instance": "Cdp202",
            "seeds_range": "42..47",
            "is_new_solution": False,
            "status": "TIMEOUT",
            "exit_code": -1,
            "error_msg": "Command timed out after 30s",
        },
        {
            "account": "account-c",
            "owner": "dautromduoicuop",
            "instance": "Cdp203",
            "seeds_range": "42..47",
            "is_new_solution": False,
            "status": "ERROR_CODE_1",
            "exit_code": 1,
            "error_msg": "401 Unauthorized",
        },
    ]
    table = format_status_table(results)
    assert "NET_ERR" in table or "DNS getaddrinfo failed" in table
    assert "TIMEOUT" in table
    assert "FAIL" in table or "401 Unauthorized" in table
