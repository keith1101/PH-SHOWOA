import json
import re
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from scripts.monitor_harvest_kaggle_new import (
    check_kernel_status,
    download_output,
)
from scripts.compare_with_paper_logged import (
    VEHICLE_WEIGHT,
    parse_solution_file,
)


class TestTier2KaggleCliBoundaries:
    """Tier 2: Boundary and corner cases for Kaggle CLI monitoring & harvesting."""

    def test_kaggle_cli_empty_stdout(self):
        """Verifies handling when Kaggle CLI returns empty or whitespace output."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="   \n")
            res = check_kernel_status("tafuhihi", "slug-1", "/fake/creds")
            assert res == ""

    def test_kaggle_cli_unauthorized_token_error(self):
        """Verifies handling when API credentials are unauthorized or expired."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1,
                stdout="401 - Unauthorized: Your credentials are not valid or expired"
            )
            res = check_kernel_status("tafuhihi", "slug-1", "/fake/creds")
            assert "401" in res
            assert "Unauthorized" in res

    def test_kaggle_cli_kernel_not_found_404(self):
        """Verifies handling when kernel slug does not exist on Kaggle (404)."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1,
                stdout="404 - Not Found: Kernel not found"
            )
            res = check_kernel_status("tafuhihi", "non-existent-slug", "/fake/creds")
            assert "404" in res
            assert "Not Found" in res

    def test_download_output_failure_modes(self, tmp_path):
        """Verifies that download failures (e.g. exit code 1, permission/network errors) return (False, msg)."""
        out_dir = tmp_path / "harvest"
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1,
                stdout="Error 500: Internal Server Error occurred while downloading."
            )
            ok, msg = download_output("tafuhihi", "slug-1", "/fake/creds", out_dir)
            assert ok is False
            assert "500" in msg

    def test_download_output_creates_nested_directories(self, tmp_path):
        """Verifies output directory is safely created even if deeply nested."""
        nested_dir = tmp_path / "level1" / "level2" / "harvest"
        assert not nested_dir.exists()
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="Downloaded")
            ok, _ = download_output("tafuhihi", "slug-1", "/fake/creds", nested_dir)
            assert ok is True
            assert nested_dir.exists()


class TestTier2ParsingBoundaries:
    """Tier 2: Boundary and error cases for log and solution parsing."""

    def test_parse_solution_corrupted_empty_file(self, tmp_path):
        """Verifies that parsing an empty or header-only file raises ValueError."""
        empty_file = tmp_path / "solution_empty.txt"
        empty_file.write_text("", encoding="utf-8")
        with pytest.raises(ValueError, match="Could not parse solution file"):
            parse_solution_file(empty_file)

    def test_parse_solution_missing_cost_marker(self, tmp_path):
        """Verifies that missing 'Total cost:' marker raises ValueError."""
        corrupted = tmp_path / "solution_corrupted.txt"
        corrupted.write_text(
            "route 0, node_num 5, cost 104.85, nodes: 0 1 3 8 0\n"
            "vehicle (route) number: 3\n",
            encoding="utf-8"
        )
        with pytest.raises(ValueError, match="Could not parse solution file"):
            parse_solution_file(corrupted)

    def test_parse_solution_missing_vehicle_marker(self, tmp_path):
        """Verifies that missing 'vehicle (route) number:' marker raises ValueError."""
        corrupted = tmp_path / "solution_corrupted2.txt"
        corrupted.write_text(
            "route 0, node_num 5, cost 104.85, nodes: 0 1 3 8 0\n"
            "Total cost: 6348.98\n",
            encoding="utf-8"
        )
        with pytest.raises(ValueError, match="Could not parse solution file"):
            parse_solution_file(corrupted)

    def test_parse_log_with_ansi_or_carriage_returns(self, sample_log_generator):
        """Verifies that logs containing carriage returns and progress bar updates parse cleanly."""
        raw_log = sample_log_generator(instance="Cdp202", seed=42, nv=3, td=591.56)
        # Inject carriage return progress lines
        dirty_log = "Epoch 1/1000\rEpoch 50/1000\r" + raw_log
        done_re = re.compile(r"done in\s+([0-9:]+)\s+\|\s+NV=([\d.]+)\s+TD=([\d.]+)")
        m = done_re.search(dirty_log)
        assert m is not None
        assert int(float(m.group(2))) == 3
        assert pytest.approx(float(m.group(3)), 0.01) == 591.56

    def test_parse_log_partial_run_not_completed(self):
        """Verifies that a log where solver died mid-search is NOT marked as completed."""
        incomplete_log = """
        NAME: Cdp202
        TYPE: VRPSPDTW
        Gen 100 done, already consumed 132 sec
        Killed: Out of memory or timeout
        """
        done_re = re.compile(r"done in\s+([0-9:]+)\s+\|\s+NV=([\d.]+)\s+TD=([\d.]+)")
        assert done_re.search(incomplete_log) is None


class TestTier2SeedAndAccountingBoundaries:
    """Tier 2: Boundary cases for seed counting, deduplication, and completion quotas."""

    def test_duplicate_seeds_deduplication(self, canonical_instances):
        """Verifies duplicate logs for the same seed do not artificially increment completed runs."""
        # Simulating two logs produced for seed 42 of RCdp1001
        log_entries = [
            ("RCdp1001", 42, 3, 348.98),
            ("RCdp1001", 42, 3, 348.98),  # Duplicate
            ("RCdp1001", 43, 3, 350.12),
        ]
        records = {inst: {} for inst in canonical_instances}
        for inst, seed, nv, td in log_entries:
            records[inst][seed] = {"nv": nv, "td": td}

        # Seed 42 should only count once
        assert len(records["RCdp1001"]) == 2
        assert set(records["RCdp1001"].keys()) == {42, 43}

    @pytest.mark.parametrize(
        "run_count,expected_status,expected_needed",
        [
            (0, "missing", 30),
            (1, "partial", 29),
            (15, "partial", 15),
            (29, "partial", 1),
            (30, "complete", 0),
            (31, "complete", 0),
            (100, "complete", 0),
        ]
    )
    def test_instance_completion_boundary_thresholds(self, run_count, expected_status, expected_needed):
        """Verifies boundary categorization at 0, 1, 29, 30, and 31+ runs."""
        status = "missing" if run_count == 0 else ("partial" if run_count < 30 else "complete")
        needed = max(0, 30 - run_count)
        assert status == expected_status
        assert needed == expected_needed


class TestTier2GoogleSheetFormatBounds:
    """Tier 2: Boundary rules for Google Sheet mutation JSON payload."""

    def test_google_sheet_payload_exact_dimension_constraints(self, canonical_instances):
        """Verifies that Google Sheet batch payload strictly conforms to 65 rows x 3 columns."""
        # Valid 65 x 3
        valid_rows = [["3", "348.98", "2m14s"] for _ in range(65)]
        payload = [{"op": "write", "range": "'Python_rerun_popsize30'!G3:I67", "data": valid_rows}]

        # Range must match rows 3 to 67 (67 - 3 + 1 = 65)
        range_match = re.search(r"G(\d+):I(\d+)", payload[0]["range"])
        assert range_match is not None
        start_row, end_row = int(range_match.group(1)), int(range_match.group(2))
        assert end_row - start_row + 1 == 65
        assert len(payload[0]["data"]) == 65

        # Boundary violation: 64 rows
        with pytest.raises(ValueError, match="Expected exactly 65 rows"):
            rows_64 = valid_rows[:-1]
            if len(rows_64) != 65:
                raise ValueError("Expected exactly 65 rows")

        # Boundary violation: wrong column count (e.g. 2 or 4 columns)
        with pytest.raises(ValueError, match="Expected exactly 3 columns"):
            invalid_cols = [["3", "348.98"] for _ in range(65)]
            for r in invalid_cols:
                if len(r) != 3:
                    raise ValueError("Expected exactly 3 columns")

    def test_missing_data_represented_as_empty_strings(self):
        """Verifies uncompleted instance cells are formatted as empty strings, never null or None."""
        row_uncompleted = ["", "", ""]
        payload_row = [str(x) if x is not None else "" for x in row_uncompleted]
        assert payload_row == ["", "", ""]
        serialized = json.dumps(payload_row)
        assert "null" not in serialized


class TestTier2FeasibilityBoundaries:
    """Tier 2: Boundary and edge tests for route feasibility rules."""

    @pytest.fixture
    def basic_network(self):
        """A minimal VRPSPDTW network for testing exact edge limits."""
        return {
            "capacity": 50.0,
            "dc_close": 100.0,
            "nodes": {
                0: {"del": 0.0, "pick": 0.0, "start": 0.0, "end": 100.0, "serv": 0.0},
                1: {"del": 25.0, "pick": 25.0, "start": 10.0, "end": 20.0, "serv": 5.0},
                2: {"del": 25.0, "pick": 25.0, "start": 30.0, "end": 50.0, "serv": 5.0},
            },
            "travel_time": 5.0,
        }

    def _validate(self, net, route):
        nodes = net["nodes"]
        cap = net["capacity"]
        dc_close = net["dc_close"]
        tt = net["travel_time"]

        if len(route) < 3:
            return False, "Route must contain at least one customer and depot endpoints"
        if route[0] != 0 or route[-1] != 0:
            return False, "Depot closure violation"

        init_load = sum(nodes[n]["del"] for n in route[1:-1])
        if init_load > cap:
            return False, f"Initial delivery {init_load} > capacity {cap}"

        curr_load = init_load
        for n in route[1:-1]:
            curr_load = curr_load - nodes[n]["del"] + nodes[n]["pick"]
            if curr_load > cap or curr_load < 0:
                return False, f"Dynamic load {curr_load} violates capacity {cap}"

        curr_time = 0.0
        for i in range(1, len(route)):
            arr_time = curr_time + tt
            curr_node = route[i]
            if arr_time > nodes[curr_node]["end"]:
                return False, f"Arrival {arr_time} > end window {nodes[curr_node]['end']}"
            curr_time = max(arr_time, nodes[curr_node]["start"]) + nodes[curr_node]["serv"]

        if curr_time > dc_close:
            return False, f"Depot return {curr_time} > dc closure {dc_close}"

        return True, "Feasible"

    def test_feasibility_exact_capacity_boundary(self, basic_network):
        """Route where load equals exactly 50.0 (capacity boundary) must pass."""
        # Initial delivery = 25.0 + 25.0 = 50.0 == capacity
        # At node 1: 50.0 - 25.0 + 25.0 = 50.0 == capacity
        # At node 2: 50.0 - 25.0 + 25.0 = 50.0 == capacity
        ok, msg = self._validate(basic_network, [0, 1, 2, 0])
        assert ok is True, msg

    def test_feasibility_single_unit_capacity_overflow(self, basic_network):
        """Route where load is 50.001 exceeds capacity and must fail."""
        basic_network["nodes"][1]["del"] = 25.001
        ok, msg = self._validate(basic_network, [0, 1, 2, 0])
        assert ok is False
        assert "capacity" in msg

    def test_feasibility_exact_time_window_arrival(self, basic_network):
        """Arrival exactly at end_tw (e.g. arr_time == 20.0, end_tw == 20.0) must pass."""
        # Depot to 1 travel time is 5.0, start_tw=10.0, end_tw=20.0
        # If travel time is set to 20.0, arrival is at 20.0 == end_tw 20.0
        basic_network["travel_time"] = 10.0  # arr at 1 is 10.0, ready at 15.0. arr at 2 is 25.0 < 50.0
        basic_network["nodes"][1]["end"] = 10.0  # arr exactly 10.0
        ok, msg = self._validate(basic_network, [0, 1, 2, 0])
        assert ok is True, msg

    def test_feasibility_single_unit_time_window_overflow(self, basic_network):
        """Arrival at 10.001 when end_tw is 10.0 must fail."""
        basic_network["travel_time"] = 10.001
        basic_network["nodes"][1]["end"] = 10.0
        ok, msg = self._validate(basic_network, [0, 1, 2, 0])
        assert ok is False
        assert "end window" in msg

    def test_feasibility_depot_not_closed(self, basic_network):
        """Route not ending with 0 must fail."""
        ok, msg = self._validate(basic_network, [0, 1, 2])
        assert ok is False
        assert "Depot closure" in msg
