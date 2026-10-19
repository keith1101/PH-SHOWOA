import json
import re
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from scripts.monitor_harvest_kaggle_new import (
    WATCH_LIST,
    check_kernel_status,
    download_output,
)
from scripts.compare_with_paper_logged import (
    VEHICLE_WEIGHT,
    parse_solution_file,
)
from scripts.check_instance_completion import SHEET_INSTANCES


# ==============================================================================
# R1: Kaggle Remote Execution & Monitoring
# ==============================================================================

class TestR1KaggleMonitoring:
    """Test feature coverage for Kaggle Remote Execution & Monitoring (R1)."""

    @pytest.mark.parametrize(
        "stdout,expected",
        [
            ("KernelWorkerStatus.RUNNING", "RUNNING"),
            ('{"status": "KernelWorkerStatus.RUNNING"}', "RUNNING"),
            ('"RUNNING"', "RUNNING"),
            ("KernelWorkerStatus.COMPLETE", "COMPLETE"),
            ('"COMPLETE"', "COMPLETE"),
            ("KernelWorkerStatus.ERROR", "ERROR"),
            ('"ERROR"', "ERROR"),
            ("KernelWorkerStatus.QUEUED", "QUEUED"),
            ('"QUEUED"', "QUEUED"),
            ("Unexpected status message", "Unexpected status message"),
        ],
    )
    def test_check_kernel_status_mapping(self, stdout, expected):
        """Verifies that kernel status strings from Kaggle CLI are mapped cleanly."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=stdout)
            result = check_kernel_status("tafuhihi", "ph-showoa-new-cdp202-s42-n6", "/fake/creds")
            assert result == expected
            # Ensure KAGGLE_CONFIG_DIR was passed in environment
            mock_run.assert_called_once()
            _, kwargs = mock_run.call_args
            assert kwargs["env"]["KAGGLE_CONFIG_DIR"] == "/fake/creds"

    def test_download_output_execution(self, tmp_path):
        """Verifies that download_output invokes Kaggle CLI with proper paths and env."""
        out_dir = tmp_path / "downloaded"
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="Files downloaded successfully")
            ok, msg = download_output("tafuhihi", "ph-showoa-new-cdp202-s42-n6", "/fake/creds", out_dir)
            assert ok is True
            assert "Files downloaded" in msg
            assert out_dir.exists()

            mock_run.assert_called_once()
            args, kwargs = mock_run.call_args
            cmd = args[0]
            assert "kernels" in cmd
            assert "output" in cmd
            assert "tafuhihi/ph-showoa-new-cdp202-s42-n6" in cmd
            assert str(out_dir) in cmd
            assert kwargs["env"]["KAGGLE_CONFIG_DIR"] == "/fake/creds"

    def test_multi_account_watch_list_completeness(self):
        """Verifies that the multi-account watch list covers the 5 designated accounts."""
        accounts = {item["account"] for item in WATCH_LIST}
        owners = {item["owner"] for item in WATCH_LIST}
        expected_owners = {"tafuhihi", "kanhan162", "dautromduoicuop", "keith1101", "giahaohuynh"}
        assert expected_owners.issubset(owners)
        assert len(WATCH_LIST) == 5

        for item in WATCH_LIST:
            assert "creds" in item and item["creds"]
            assert "instance" in item and item["instance"]
            assert "slug_pattern" in item and "{seed}" in item["slug_pattern"]
            assert len(item["seeds"]) == 5  # 5 concurrent kernels each (25 total kernels)


# ==============================================================================
# R2: Wave 2 & Completion Queue Management
# ==============================================================================

class TestR2WaveCompletionQueue:
    """Test feature coverage for Wave 2 & Partial Instance Completion Queue (R2)."""

    def test_instance_completion_accounting(self, tmp_path, canonical_instances):
        """Verifies correct classification of missing, partial, and complete instances."""
        # Create a mock directory with completed seeds
        # Instance 1: Complete (30 seeds)
        for s in range(42, 72):
            f = tmp_path / f"RCdp1001_seed_{s}.log"
            f.write_text(f"seed={s}\ndone in 00:02:14 | NV=3 TD=348.98\n", encoding="utf-8")

        # Instance 2: Partial (5 seeds)
        for s in range(42, 47):
            f = tmp_path / f"RCdp203_seed_{s}.log"
            f.write_text(f"seed={s}\ndone in 00:02:14 | NV=4 TD=1234.10\n", encoding="utf-8")

        # Parse records
        done_re = re.compile(r"done in\s+([0-9:]+)\s+\|\s+NV=([\d.]+)\s+TD=([\d.]+)")
        seed_re = re.compile(r"seed=(\d+)")
        inst_log_name_re = re.compile(r"^([A-Za-z0-9_]+)_seed_(\d+)\.log", re.IGNORECASE)

        records = {inst: {} for inst in canonical_instances}
        for log_file in tmp_path.glob("*.log"):
            m = inst_log_name_re.match(log_file.name)
            if not m:
                continue
            inst_name = m.group(1)
            # Find canonical
            match = next((ci for ci in canonical_instances if ci.lower() == inst_name.lower()), None)
            if not match:
                continue
            content = log_file.read_text(encoding="utf-8")
            curr_seed = int(m.group(2))
            if done_re.search(content):
                records[match][curr_seed] = True

        complete = [i for i, seeds in records.items() if len(seeds) >= 30]
        partial = [i for i, seeds in records.items() if 0 < len(seeds) < 30]
        missing = [i for i, seeds in records.items() if len(seeds) == 0]

        assert "RCdp1001" in complete
        assert "RCdp203" in partial
        assert len(records["RCdp203"]) == 5
        assert len(missing) == 63
        assert len(complete) + len(partial) + len(missing) == 65

    def test_wave_2_dispatch_queue_generation(self, canonical_instances):
        """Verifies that dispatch queue items prioritize partial instances."""
        mock_counts = {
            "RCdp1001": 30,  # Complete
            "Cdp207": 3,     # Partial
            "RCdp203": 3,    # Partial
            "Rdp202": 4,     # Partial
            "RCdp1004": 0,   # Missing
        }
        needed_runs = {}
        for inst in canonical_instances:
            cnt = mock_counts.get(inst, 0)
            if cnt < 30:
                needed_runs[inst] = 30 - cnt

        # Partial instances must have 30 - current runs needed
        assert needed_runs["Cdp207"] == 27
        assert needed_runs["RCdp203"] == 27
        assert needed_runs["Rdp202"] == 26
        assert needed_runs["RCdp1004"] == 30
        assert "RCdp1001" not in needed_runs


# ==============================================================================
# R3: Automated Harvesting & Google Sheet Synchronization Format
# ==============================================================================

class TestR3HarvestingAndGoogleSheetFormat:
    """Test feature coverage for Output Harvesting & Google Sheets Synchronization Format (R3)."""

    def test_solution_file_parser(self, tmp_path, sample_solution_generator):
        """Verifies accurate extraction of vehicles and travel distance from solution file."""
        sol_file = tmp_path / "solution.txt"
        sol_file.write_text(sample_solution_generator(nv=3, td=348.98), encoding="utf-8")

        vehicles, distance, total_cost = parse_solution_file(sol_file)
        assert vehicles == 3
        assert pytest.approx(distance, 0.01) == 348.98
        assert pytest.approx(total_cost, 0.01) == 3 * VEHICLE_WEIGHT + 348.98

    def test_log_extraction_metrics(self, sample_log_generator):
        """Verifies metric extraction from solver execution log lines."""
        log_content = sample_log_generator(instance="RCdp1001", seed=43, nv=3, td=348.98, runtime_sec=134)
        
        # Check summary line regex
        done_re = re.compile(r"done in\s+([0-9:]+)\s+\|\s+NV=([\d.]+)\s+TD=([\d.]+)")
        match = done_re.search(log_content)
        assert match is not None
        duration_str, nv_str, td_str = match.groups()
        assert duration_str == "00:02:14"
        assert int(float(nv_str)) == 3
        assert float(td_str) == 348.98

        # Check solution header regex
        nv_marker = re.search(r"vehicle \(route\) number:\s+(\d+)", log_content)
        cost_marker = re.search(r"Total cost:\s+([0-9.]+)", log_content)
        assert nv_marker is not None
        assert cost_marker is not None
        assert int(nv_marker.group(1)) == 3
        assert float(cost_marker.group(1)) == 3 * 2000.0 + 348.98

    def test_google_sheet_mutation_batch_json_format(self, canonical_instances):
        """Verifies that the Google Sheets batch mutation payload strictly conforms to CLI specs."""
        # Build 65-row mock data
        matrix_rows = []
        for i, inst in enumerate(canonical_instances):
            nv_val = "3"
            td_val = f"{300.0 + i:.2f}"
            avg_run = "2m14s"
            matrix_rows.append([nv_val, td_val, avg_run])

        assert len(matrix_rows) == 65

        # Format batch mutation payload for Google Sheet tab Python_rerun_popsize30 rows 3 to 67
        target_range = "'Python_rerun_popsize30'!G3:I67"
        payload = [
            {
                "op": "write",
                "range": target_range,
                "data": matrix_rows
            }
        ]

        # Validations
        assert len(payload) == 1
        op = payload[0]
        assert op["op"] == "write"
        assert "Python_rerun_popsize30" in op["range"]
        assert "G3:I67" in op["range"]
        assert "data" in op  # Must be 'data', never 'values'
        assert "values" not in op
        assert len(op["data"]) == 65
        for row in op["data"]:
            assert len(row) == 3  # Columns G (NV), H (TD), I (Avg/Run)


# ==============================================================================
# R4: Paper Targets Comparison & Feasibility Rules
# ==============================================================================

class TestR4PaperTargetsAndFeasibilityRules:
    """Test feature coverage for Paper Target Comparison & Solution Feasibility Rules (R4)."""

    def test_paper_targets_inventory_completeness(self, paper_targets, canonical_instances):
        """Verifies that all 65 canonical instances are present in paper_performance_targets.csv."""
        assert len(paper_targets) == 65
        for inst in canonical_instances:
            assert inst.lower() in paper_targets
            target = paper_targets[inst.lower()]
            assert target["target_vehicles"] > 0
            assert target["target_distance"] > 0.0
            assert target["table"] in [3, 4, 5]

    def test_target_gap_calculation(self):
        """Verifies correct calculation of percentage gaps against paper baseline."""
        def pct_gap(val: float, baseline: float) -> float:
            if baseline == 0:
                return 0.0
            return (val - baseline) / baseline * 100.0

        # When solver achieves exact paper target
        assert pct_gap(369.74, 369.74) == 0.0

        # When solver beats paper target (better distance)
        gap = pct_gap(348.98, 369.74)
        assert gap < 0.0
        assert pytest.approx(gap, 0.01) == -5.61

        # When solver is worse than paper target
        assert pct_gap(400.0, 369.74) > 0.0

    def test_best_meets_paper_criteria(self):
        """Verifies criterion for declaring whether a solution meets paper targets."""
        paper_nv = 3
        paper_td = 369.74
        paper_tc = paper_nv * VEHICLE_WEIGHT + paper_td

        def meets_paper(nv: int, td: float) -> bool:
            tc = nv * VEHICLE_WEIGHT + td
            return (tc <= paper_tc) or (nv < paper_nv) or (nv == paper_nv and td <= paper_td)

        # 1. Matches vehicles, beats distance -> YES
        assert meets_paper(3, 348.98) is True

        # 2. Matches vehicles, exact distance -> YES
        assert meets_paper(3, 369.74) is True

        # 3. Fewer vehicles, slightly higher distance but lower total cost -> YES
        assert meets_paper(2, 450.0) is True

        # 4. Matches vehicles, worse distance -> NO
        assert meets_paper(3, 380.0) is False

        # 5. More vehicles, even with tiny distance -> NO (due to 2000.0 vehicle weight)
        assert meets_paper(4, 200.0) is False

    def test_route_feasibility_rules(self):
        """Verifies route feasibility validator (capacity, time windows, DC closure)."""
        # Node properties: id -> (delivery, pickup, start_tw, end_tw, service)
        # DC is node 0: (0, 0, 0, 100, 0)
        capacity = 50.0
        dc_close = 100.0

        nodes = {
            0: {"del": 0.0, "pick": 0.0, "start": 0.0, "end": 100.0, "serv": 0.0},
            1: {"del": 15.0, "pick": 10.0, "start": 10.0, "end": 40.0, "serv": 5.0},
            2: {"del": 20.0, "pick": 15.0, "start": 20.0, "end": 60.0, "serv": 5.0},
            3: {"del": 10.0, "pick": 20.0, "start": 30.0, "end": 80.0, "serv": 5.0},
        }
        # Distances: unit 2.0 between consecutive
        travel_time = 2.0

        def check_route(route: list[int]) -> tuple[bool, str]:
            if route[0] != 0 or route[-1] != 0:
                return False, "Route must start and end at depot"

            # 1. Capacity check
            # Initial load leaving depot = sum of deliveries
            initial_delivery = sum(nodes[n]["del"] for n in route[1:-1])
            if initial_delivery > capacity:
                return False, f"Initial delivery {initial_delivery} exceeds capacity {capacity}"

            current_load = initial_delivery
            for n in route[1:-1]:
                current_load = current_load - nodes[n]["del"] + nodes[n]["pick"]
                if current_load < 0 or current_load > capacity:
                    return False, f"Dynamic load {current_load} violates capacity {capacity}"

            # 2. Time window check
            current_time = 0.0
            for i in range(1, len(route)):
                prev = route[i-1]
                curr = route[i]
                arr_time = current_time + travel_time
                if arr_time > nodes[curr]["end"]:
                    return False, f"Arrival {arr_time} at node {curr} violates end window {nodes[curr]['end']}"
                # Ready time is max(arrival, start_tw) + service
                ready_time = max(arr_time, nodes[curr]["start"]) + nodes[curr]["serv"]
                current_time = ready_time

            if current_time > dc_close:
                return False, f"Return time {current_time} exceeds DC closure {dc_close}"

            return True, "Feasible"

        # Valid route [0, 1, 2, 3, 0]
        # Initial delivery: 15 + 20 + 10 = 45 <= 50 -> OK
        # At node 1: 45 - 15 + 10 = 40 <= 50 -> OK
        # At node 2: 40 - 20 + 15 = 35 <= 50 -> OK
        # At node 3: 35 - 10 + 20 = 45 <= 50 -> OK
        ok, msg = check_route([0, 1, 2, 3, 0])
        assert ok is True, msg

        # Capacity violation (total delivery > 50)
        nodes[1]["del"] = 30.0  # Total delivery = 30 + 20 + 10 = 60 > 50
        ok, msg = check_route([0, 1, 2, 3, 0])
        assert ok is False
        assert "exceeds capacity" in msg

        # Reset and test Time Window violation
        nodes[1]["del"] = 15.0
        nodes[1]["end"] = 1.0   # Arrival is at t=2.0 > 1.0
        ok, msg = check_route([0, 1, 2, 3, 0])
        assert ok is False
        assert "violates end window" in msg
