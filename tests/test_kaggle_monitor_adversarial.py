"""
Adversarial Stress Test Suite for scripts/kaggle_monitor.py.
Author: Challenger 1 (critic / specialist)

Stress-tests scripts/kaggle_monitor.py against hostile conditions:
1. Simulated CLI network errors, DNS drops, and subprocess timeouts.
2. Malformed, corrupted, and non-standard CLI responses and HTTP error outputs.
3. Missing, corrupted, and unauthenticated credentials.
4. Concurrency hazards, thread errors, and state persistence corruption.
5. Parameter audit perturbation detection (tampered notebooks & generator scripts).
6. Table rendering resilience under malformed / edge-case statuses.
7. Local resource consumption and zero heavy CPU execution verification.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scripts.kaggle_monitor import (
    DEFAULT_STATE_FILE,
    KernelSpec,
    format_status_table,
    get_all_kernel_specs,
    query_all_kernels_concurrent,
    query_kernel_status,
    resolve_kaggle_exe,
    update_state_and_detect_transitions,
    verify_remote_parameters,
)


# ==============================================================================
# 1. NETWORK FAILURE & CLI ERROR RESILIENCE
# ==============================================================================

def test_adversarial_network_dns_failure():
    """Verify simulated DNS resolution failure is categorized as NETWORK_ERROR."""
    spec = KernelSpec(
        account="tafuhihi",
        owner="tafuhihi",
        creds_dir=Path("/tmp/creds"),
        instance="Cdp202",
        slug="test-slug",
        seed_start=42,
        repeats=6,
        is_new_solution=True,
        solution_label="New Solution",
    )

    with patch("subprocess.run") as mock_run:
        mock_proc = MagicMock()
        mock_proc.returncode = 1
        mock_proc.stdout = ""
        mock_proc.stderr = (
            "urllib3.exceptions.MaxRetryError: HTTPSConnectionPool(host='www.kaggle.com', port=443): "
            "Max retries exceeded with url: /api/v1/kernels/status "
            "(Caused by NewConnectionError('<urllib3.connection.HTTPSConnection object>: "
            "Failed to establish a new connection: [Errno 11001] getaddrinfo failed'))"
        )
        mock_run.return_value = mock_proc

        result = query_kernel_status(spec, "dummy_kaggle", timeout=5)
        assert result["status"] == "NETWORK_ERROR", f"Expected NETWORK_ERROR, got {result['status']}"
        assert result["exit_code"] == 1
        assert "getaddrinfo failed" in result["error_msg"]


def test_adversarial_connection_reset_by_peer():
    """Verify connection drop / reset is detected as NETWORK_ERROR."""
    spec = KernelSpec(
        account="account-b",
        owner="kanhan162",
        creds_dir=Path("/tmp/creds"),
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
        mock_proc.stdout = ""
        mock_proc.stderr = "requests.exceptions.ConnectionError: Connection reset by peer"
        mock_run.return_value = mock_proc

        result = query_kernel_status(spec, "dummy_kaggle", timeout=5)
        assert result["status"] == "NETWORK_ERROR", f"Expected NETWORK_ERROR, got {result['status']}"
        assert result["exit_code"] == 1


def test_adversarial_subprocess_timeout():
    """Verify subprocess timeout is trapped cleanly without crashing the caller."""
    spec = KernelSpec(
        account="tafuhihi",
        owner="tafuhihi",
        creds_dir=Path("/tmp/creds"),
        instance="Cdp202",
        slug="test-slug",
        seed_start=42,
        repeats=6,
        is_new_solution=True,
        solution_label="New Solution",
    )

    with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd=["kaggle"], timeout=2)):
        result = query_kernel_status(spec, "dummy_kaggle", timeout=2)
        assert result["status"] == "TIMEOUT"
        assert result["exit_code"] == -1
        assert "timed out after 2s" in result["error_msg"]


def test_adversarial_concurrent_all_workers_timeout():
    """Stress test query_all_kernels_concurrent when ALL 25 workers time out simultaneously."""
    specs = get_all_kernel_specs()

    with patch("scripts.kaggle_monitor.query_kernel_status") as mock_query:
        mock_query.side_effect = lambda spec, exe, timeout: {
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
            "checked_at": "2026-10-12T00:00:00Z",
            "error_msg": "Timeout",
        }

        results = query_all_kernels_concurrent(specs, "dummy_kaggle", max_workers=5, timeout=1)
        assert len(results) == 25
        assert all(r["status"] == "TIMEOUT" for r in results)


# ==============================================================================
# 2. MALFORMED CLI OUTPUT & UNEXPECTED RESPONSES
# ==============================================================================

def test_adversarial_html_gateway_error():
    """Simulate Cloudflare 502 Bad Gateway HTML returned instead of status string."""
    spec = KernelSpec(
        account="tafuhihi",
        owner="tafuhihi",
        creds_dir=Path("/tmp"),
        instance="Cdp202",
        slug="slug-test",
        seed_start=42,
        repeats=6,
        is_new_solution=True,
        solution_label="New",
    )

    with patch("subprocess.run") as mock_run:
        mock_proc = MagicMock()
        mock_proc.returncode = 1
        mock_proc.stdout = "<html><head><title>502 Bad Gateway</title></head><body><h1>502 Bad Gateway</h1></body></html>"
        mock_proc.stderr = ""
        mock_run.return_value = mock_proc

        result = query_kernel_status(spec, "dummy_kaggle")
        assert result["status"] == "ERROR_CODE_1"
        assert "502 Bad Gateway" in result["raw_output"]


def test_adversarial_warning_prepended_to_status():
    """Simulate CLI stdout having warnings/notices printed before the status line."""
    spec = KernelSpec(
        account="account-c",
        owner="dautromduoicuop",
        creds_dir=Path("/tmp"),
        instance="Cdp203",
        slug="slug-test",
        seed_start=42,
        repeats=6,
        is_new_solution=False,
        solution_label="Baseline",
    )

    with patch("subprocess.run") as mock_run:
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = (
            "D:\\python\\lib\\site-packages\\urllib3\\connectionpool.py:1061: InsecureRequestWarning: "
            "Unverified HTTPS request is being made to host 'www.kaggle.com'.\n"
            "FutureWarning: This feature is deprecated.\n"
            'dautromduoicuop/slug-test has status "KernelWorkerStatus.COMPLETE"\n'
        )
        mock_proc.stderr = ""
        mock_run.return_value = mock_proc

        result = query_kernel_status(spec, "dummy_kaggle")
        assert result["status"] == "COMPLETE"


def test_adversarial_novel_status_fallback_regex():
    """Simulate an unrecognized status string parsed via regex fallback."""
    spec = KernelSpec(
        account="account-d",
        owner="keith1101",
        creds_dir=Path("/tmp"),
        instance="Cdp205",
        slug="slug-test",
        seed_start=42,
        repeats=6,
        is_new_solution=False,
        solution_label="Baseline",
    )

    with patch("subprocess.run") as mock_run:
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = 'keith1101/slug-test has status "KernelWorkerStatus.SUSPENDED_NODE"\n'
        mock_proc.stderr = ""
        mock_run.return_value = mock_proc

        result = query_kernel_status(spec, "dummy_kaggle")
        assert result["status"] == "SUSPENDED_NODE"


def test_adversarial_empty_cli_output():
    """Simulate completely empty stdout/stderr with returncode 0."""
    spec = KernelSpec(
        account="account-e",
        owner="giahaohuynh",
        creds_dir=Path("/tmp"),
        instance="Cdp208",
        slug="slug-test",
        seed_start=42,
        repeats=6,
        is_new_solution=False,
        solution_label="Baseline",
    )

    with patch("subprocess.run") as mock_run:
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = ""
        mock_proc.stderr = ""
        mock_run.return_value = mock_proc

        result = query_kernel_status(spec, "dummy_kaggle")
        assert result["status"] == "UNKNOWN"


# ==============================================================================
# 3. CREDENTIAL ISSUES & ENVIRONMENT ISOLATION
# ==============================================================================

def test_adversarial_missing_credentials():
    """Simulate missing kaggle.json in KAGGLE_CONFIG_DIR."""
    spec = KernelSpec(
        account="tafuhihi",
        owner="tafuhihi",
        creds_dir=Path("/nonexistent/credentials/path"),
        instance="Cdp202",
        slug="slug-test",
        seed_start=42,
        repeats=6,
        is_new_solution=True,
        solution_label="New",
    )

    with patch("subprocess.run") as mock_run:
        mock_proc = MagicMock()
        mock_proc.returncode = 1
        mock_proc.stdout = ""
        mock_proc.stderr = (
            "Could not find kaggle.json. Make sure it's located in /nonexistent/credentials/path. "
            "Or use the environment method."
        )
        mock_run.return_value = mock_proc

        result = query_kernel_status(spec, "dummy_kaggle")
        assert result["status"] == "ERROR_CODE_1"
        assert "Could not find kaggle.json" in result["error_msg"]


def test_adversarial_env_isolation():
    """Verify query_kernel_status does NOT mutate parent os.environ."""
    original_config = os.environ.get("KAGGLE_CONFIG_DIR")
    fake_creds = Path("D:/Fake/Creds/Dir")

    spec = KernelSpec(
        account="tafuhihi",
        owner="tafuhihi",
        creds_dir=fake_creds,
        instance="Cdp202",
        slug="slug-test",
        seed_start=42,
        repeats=6,
        is_new_solution=True,
        solution_label="New",
    )

    with patch("subprocess.run") as mock_run:
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = 'tafuhihi/slug-test has status "RUNNING"'
        mock_proc.stderr = ""
        mock_run.return_value = mock_proc

        query_kernel_status(spec, "dummy_kaggle")

        # Verify child process got the custom creds_dir
        called_env = mock_run.call_args[1]["env"]
        assert called_env["KAGGLE_CONFIG_DIR"] == str(fake_creds)

        # Verify parent environment is unchanged
        assert os.environ.get("KAGGLE_CONFIG_DIR") == original_config


# ==============================================================================
# 4. CONCURRENCY & STATE FILE CORRUPTION RESILIENCE
# ==============================================================================

def test_adversarial_corrupted_state_file_recovery(tmp_path: Path):
    """Verify that a corrupted / invalid JSON state file is gracefully overwritten."""
    corrupted_file = tmp_path / "corrupted_state.json"
    corrupted_file.write_text("{ this is completely invalid JSON {{{", encoding="utf-8")

    dummy_results = [
        {
            "ref": "tafuhihi/kernel-1",
            "account": "tafuhihi",
            "owner": "tafuhihi",
            "instance": "Cdp202",
            "seeds_range": "42..47",
            "status": "RUNNING",
            "is_new_solution": True,
        }
    ]

    # Should not crash on invalid JSON, should reinitialize
    new_state, transitions = update_state_and_detect_transitions(dummy_results, corrupted_file)
    assert new_state["total_kernels"] == 1
    assert new_state["kernels"]["tafuhihi/kernel-1"]["status"] == "RUNNING"
    # State file should now be valid JSON
    saved_data = json.loads(corrupted_file.read_text(encoding="utf-8"))
    assert saved_data["total_kernels"] == 1


def test_adversarial_nested_dir_creation(tmp_path: Path):
    """Verify state file writer creates non-existent intermediate directories."""
    nested_path = tmp_path / "sub1" / "sub2" / "state.json"
    assert not nested_path.parent.exists()

    dummy_results = [
        {
            "ref": "tafuhihi/kernel-1",
            "account": "tafuhihi",
            "owner": "tafuhihi",
            "instance": "Cdp202",
            "seeds_range": "42..47",
            "status": "RUNNING",
            "is_new_solution": True,
        }
    ]

    new_state, _ = update_state_and_detect_transitions(dummy_results, nested_path)
    assert nested_path.exists()
    assert new_state["total_kernels"] == 1


def test_adversarial_rapid_state_flapping(tmp_path: Path):
    """Verify state transitions history records multiple state transitions accurately."""
    state_file = tmp_path / "flapping_state.json"
    ref = "tafuhihi/kernel-flapper"

    statuses = ["RUNNING", "NETWORK_ERROR", "RUNNING", "COMPLETE"]
    for idx, s in enumerate(statuses):
        res = [{
            "ref": ref,
            "account": "tafuhihi",
            "owner": "tafuhihi",
            "instance": "Cdp202",
            "seeds_range": "42..47",
            "status": s,
            "is_new_solution": True,
        }]
        state, trans = update_state_and_detect_transitions(res, state_file)
        if idx == 0:
            assert len(trans) == 0
        else:
            assert len(trans) == 1
            assert trans[0]["to_status"] == s
            assert trans[0]["from_status"] == statuses[idx - 1]

    # Inspect final history log
    final_kernel = state["kernels"][ref]
    # Note: cycle 1 adds initial record with from: None, plus 3 subsequent transitions = 4 records
    assert len(final_kernel["history"]) == 4
    assert final_kernel["history"][0]["from"] is None
    assert final_kernel["history"][-1]["to"] == "COMPLETE"
    assert final_kernel["status"] == "COMPLETE"


# ==============================================================================
# 5. PARAMETER AUDIT PERTURBATION & TAMPER DETECTION
# ==============================================================================

def test_adversarial_parameter_audit_detects_mismatch(tmp_path: Path):
    """Verify that tampering with max_iter is caught by verify_remote_parameters."""
    specs = get_all_kernel_specs()

    tampered_nb = tmp_path / "tampered.ipynb"
    tampered_content = {
        "cells": [
            {
                "cell_type": "code",
                "source": [
                    "python scripts/kaggle_run.py --backends cpu --pop_size 30 --max_iter 500 --timeout 43200"
                ],
            }
        ]
    }
    tampered_nb.write_text(json.dumps(tampered_content), encoding="utf-8")
    specs[0].notebook_path = tampered_nb

    with patch("scripts.kaggle_monitor.get_all_kernel_specs", return_value=specs):
        audit = verify_remote_parameters()
        assert audit["all_match"] is False, "Audit should fail on tampered parameters"
        assert audit["details"][0]["max_iter_1000"] is False
        assert audit["details"][0]["all_passed"] is False


def test_adversarial_reproduce_no_paper_flags_substring_bypass(tmp_path: Path):
    """
    REMEDIATION VERIFICATION:
    Verifies that verify_remote_parameters strictly detects '--no_paper_flags'
    and sets paper_flags to False with mode 'DISABLED', preventing audit bypass.
    """
    specs = get_all_kernel_specs()

    tampered_nb = tmp_path / "tampered_flags.ipynb"
    tampered_content = {
        "cells": [
            {
                "cell_type": "code",
                "source": [
                    "python scripts/kaggle_run.py --backends cpu --pop_size 30 --max_iter 1000 --no_paper_flags --timeout 43200"
                ],
            }
        ]
    }
    tampered_nb.write_text(json.dumps(tampered_content), encoding="utf-8")
    specs[0].notebook_path = tampered_nb

    with patch("scripts.kaggle_monitor.get_all_kernel_specs", return_value=specs):
        audit = verify_remote_parameters()
        detail = audit["details"][0]
        assert detail["paper_flags"] is False, "Strict regex correctly flagged --no_paper_flags as False"
        assert detail["paper_flags_mode"] == "DISABLED", "Mode correctly reported as DISABLED"
        assert detail["all_passed"] is False
        assert audit["all_match"] is False


def test_adversarial_reproduce_pop_size_loose_substring_bypass(tmp_path: Path):
    """
    REMEDIATION VERIFICATION:
    Verifies that verify_remote_parameters uses strict word boundaries so that
    '--pop_size 50' is not fooled by '30' in comments.
    """
    specs = get_all_kernel_specs()

    tampered_nb = tmp_path / "tampered_pop.ipynb"
    tampered_content = {
        "cells": [
            {
                "cell_type": "code",
                "source": [
                    "python scripts/kaggle_run.py --backends cpu --pop_size 50 # takes 30 seconds --max_iter 1000 --timeout 43200"
                ],
            }
        ]
    }
    tampered_nb.write_text(json.dumps(tampered_content), encoding="utf-8")
    specs[0].notebook_path = tampered_nb

    with patch("scripts.kaggle_monitor.get_all_kernel_specs", return_value=specs):
        audit = verify_remote_parameters()
        detail = audit["details"][0]
        assert detail["pop_size_30"] is False, "Strict regex correctly rejected --pop_size 50"
        assert detail["all_passed"] is False
        assert audit["all_match"] is False


# ==============================================================================
# 6. STATUS TABLE RESILIENCE UNDER EXTREME STRINGS
# ==============================================================================

def test_adversarial_format_status_table_extreme_inputs():
    """Verify format_status_table does not crash on None, empty strings, huge error logs."""
    results = [
        {
            "account": "acc-long-name-here",
            "owner": "verylongowneraccountname",
            "instance": "RCdp201",
            "seeds_range": "100..105",
            "is_new_solution": True,
            "status": "CUSTOM_ERROR_404_TIMEOUT_FAIL",
            "error_msg": "A" * 1000,  # 1000-character error string
        },
        {
            "account": "acc2",
            "owner": "owner2",
            "instance": "Cdp201",
            "seeds_range": "42..47",
            "is_new_solution": False,
            "status": "QUEUED",
            "error_msg": "",
        },
    ]
    table = format_status_table(results)
    assert "CUSTOM_ERROR_404_TIMEOUT_FAIL" in table
    assert "QUEUED" in table
    assert "acc-long-name-here" in table


# ==============================================================================
# 7. RESOURCE BOUNDS & ZERO LOCAL CPU INTENSITY
# ==============================================================================

def test_adversarial_zero_heavy_cpu_consumption():
    """
    Verify that query execution and formatting consume minimal local CPU.
    Monitors processor time spent during execution of query batch.
    """
    specs = get_all_kernel_specs()[:5]

    start_cpu = time.process_time()
    start_wall = time.time()

    with patch("subprocess.run") as mock_run:
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = 'tafuhihi/test has status "KernelWorkerStatus.RUNNING"'
        mock_proc.stderr = ""
        mock_run.return_value = mock_proc

        results = query_all_kernels_concurrent(specs, "dummy_kaggle", max_workers=5)
        _ = format_status_table(results)

    elapsed_cpu = time.process_time() - start_cpu
    elapsed_wall = time.time() - start_wall

    # Local CPU time consumed must be < 0.25 seconds for a batch of queries
    assert elapsed_cpu < 0.25, f"Excessive CPU usage detected: {elapsed_cpu:.4f}s"
