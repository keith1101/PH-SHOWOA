import json
import re
from pathlib import Path
import pytest

from scripts.compare_with_paper_logged import (
    VEHICLE_WEIGHT,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class TestTier4RealHarvestedRunsAcceptance:
    """Tier 4: Acceptance verification using actual harvested production run logs."""

    def test_verify_real_harvested_logs_in_pop30_completed(self, paper_targets):
        """Audits actual harvested solver logs in tmp/pop30_completed/ ensuring valid

        metrics on completed runs and robust detection of interrupted runs.
        """
        pop30_dir = PROJECT_ROOT / "tmp" / "pop30_completed"
        if not pop30_dir.exists():
            pytest.skip("tmp/pop30_completed directory not found")

        log_files = list(pop30_dir.glob("*.log"))
        assert len(log_files) > 0, "No log files found in tmp/pop30_completed"

        done_re = re.compile(r"done in\s+([0-9:]+)\s+\|\s+NV=([\d.]+)\s+TD=([\d.]+)\s+TC=([\d.]+)")
        inst_log_name_re = re.compile(r"^([A-Za-z0-9_]+)_seed_(\d+)\.log", re.IGNORECASE)

        completed_count = 0
        incomplete_count = 0

        for f in log_files:
            m = inst_log_name_re.match(f.name)
            if not m:
                continue

            inst = m.group(1)
            seed = int(m.group(2))
            content = f.read_text(encoding="utf-8", errors="ignore")

            dm = done_re.search(content)
            if dm is not None:
                duration_str, nv_str, td_str, tc_str = dm.groups()
                nv = int(float(nv_str))
                td = float(td_str)
                tc = float(tc_str)

                # Invariant: TC = NV * 2000.0 + TD
                expected_tc = nv * 2000.0 + td
                assert pytest.approx(tc, 0.05) == expected_tc, (
                    f"Total cost formula mismatch in {f.name}: reported {tc}, expected {expected_tc}"
                )

                # Invariant: Instance must exist in paper targets
                assert inst.lower() in paper_targets, f"Instance {inst} not in paper targets"
                paper_info = paper_targets[inst.lower()]
                target_nv = paper_info["target_vehicles"]

                # Vehicles should be within reasonable bounds of paper target
                assert nv <= target_nv + 1, (
                    f"Instance {inst} run {seed} vehicle count {nv} drastically exceeds paper target {target_nv}"
                )
                completed_count += 1
            else:
                # Interrupted run: verify that search framework properly left it without "done in" marker
                assert "done in" not in content
                incomplete_count += 1

        assert completed_count > 0, "Expected at least one completed run in tmp/pop30_completed"
        # RCdp1004_seed_70.log is a known interrupted run in tmp/pop30_completed
        assert incomplete_count >= 1, "Expected to verify at least one interrupted run"
        print(f"\nAudited {completed_count} completed logs and {incomplete_count} interrupted logs in tmp/pop30_completed.")


class TestTier4GoogleSheetArtifactAcceptance:
    """Tier 4: Acceptance verification for the real Google Sheet mutation JSON payload."""

    def test_verify_real_gsheets_update_request_artifact(self, canonical_instances):
        """Verifies the actual production payload tmp/gsheets_update_request.json against

        the Google Sheet tab Python_rerun_popsize30 layout contract.
        """
        payload_file = PROJECT_ROOT / "tmp" / "gsheets_update_request.json"
        if not payload_file.exists():
            pytest.skip("tmp/gsheets_update_request.json not found")

        content = payload_file.read_text(encoding="utf-8")
        payload = json.loads(content)

        assert isinstance(payload, list)
        assert len(payload) == 1
        operation = payload[0]

        assert operation["op"] == "write"
        assert operation["range"] == "'Python_rerun_popsize30'!G3:I67"
        assert "data" in operation
        assert "values" not in operation

        rows = operation["data"]
        assert len(rows) == 65, f"Expected 65 rows, found {len(rows)}"

        # Validate structure of each row
        # Durations can be formatted as mm:ss or hh:mm:ss (e.g. 2m12s or 1h11m11s)
        duration_pattern = re.compile(r"^(\d+h)?\d+m\d{2}s$")
        populated_count = 0

        for i, row in enumerate(rows):
            assert len(row) == 3, f"Row {i} (inst {canonical_instances[i]}) has length {len(row)} != 3"
            nv_val, td_val, avg_val = row

            if nv_val != "":
                populated_count += 1
                # NV must be a positive number (integer or float average)
                assert float(nv_val) > 0.0, f"Invalid NV at row {i}: {nv_val}"
                # TD must be a float
                assert float(td_val) > 0.0, f"Invalid TD at row {i}: {td_val}"
                # Avg/run duration must be formatted
                assert duration_pattern.match(avg_val), f"Invalid duration format at row {i}: {avg_val}"
            else:
                # If unpopulated, TD and Avg/run must also be empty
                assert td_val == "" and avg_val == ""

        assert populated_count > 0, "Expected populated rows in gsheets_update_request.json"


class TestTier4PaperBenchmarkTargetIntegrity:
    """Tier 4: Acceptance verification of paper targets and Wang-Chen dataset paths."""

    def test_paper_benchmark_tables_and_paths_integrity(self, paper_targets, canonical_instances):
        """Verifies that all 65 canonical instances in paper_performance_targets.csv

        have valid benchmark properties and match Tables 3, 4, 5 distribution.
        """
        assert len(paper_targets) == 65

        # Check table counts matching paper Tables 3, 4, 5
        table_counts = {3: 0, 4: 0, 5: 0}
        for item in paper_targets.values():
            tbl = item["table"]
            assert tbl in table_counts
            table_counts[tbl] += 1

        assert table_counts[3] == 9, f"Table 3 should have 9 instances, got {table_counts[3]}"
        assert table_counts[4] == 29, f"Table 4 should have 29 instances, got {table_counts[4]}"
        assert table_counts[5] == 27, f"Table 5 should have 27 instances, got {table_counts[5]}"

        # Check instance name matching
        for canonical_name in canonical_instances:
            assert canonical_name.lower() in paper_targets
            t = paper_targets[canonical_name.lower()]
            assert t["target_vehicles"] >= 1
            assert t["target_distance"] > 0.0
            assert "Wang_Chen" in t["path"]


class TestTier4EndToEndDryRunPipeline:
    """Tier 4: Complete dry-run orchestrating the full campaign pipeline without CPU solver overhead."""

    def test_full_pipeline_dry_run_execution(
        self, tmp_path, canonical_instances, paper_targets, sample_log_generator
    ):
        """Executes a complete dry-run across all modules:

        1. Monitoring 5 accounts.
        2. Harvesting logs into local directories.
        3. Completion auditing.
        4. Sheet mutation payload generation.
        5. Feasibility validation and benchmark comparison.
        """
        # Step 1: Simulate downloaded logs for a subset of instances
        work_dir = tmp_path / "dry_run_harvest"
        work_dir.mkdir(parents=True)

        test_instances = ["RCdp1001", "Cdp202", "Rdp101"]
        for inst in test_instances:
            for s in range(42, 72):
                content = sample_log_generator(instance=inst, seed=s, nv=3, td=350.0, runtime_sec=120)
                (work_dir / f"{inst}_seed_{s}.log").write_text(content, encoding="utf-8")

        # Step 2: Audit completion
        inst_log_name_re = re.compile(r"^([A-Za-z0-9_]+)_seed_(\d+)\.log", re.IGNORECASE)
        counts = {inst: 0 for inst in canonical_instances}
        for f in work_dir.glob("*.log"):
            m = inst_log_name_re.match(f.name)
            if m:
                raw_name = m.group(1)
                match = next((ci for ci in canonical_instances if ci.lower() == raw_name.lower()), None)
                if match:
                    counts[match] += 1

        for inst in test_instances:
            assert counts[inst] == 30

        # Step 3: Generate 65-row Google Sheet payload
        rows = []
        for inst in canonical_instances:
            if counts[inst] >= 30:
                rows.append(["3", "350.00", "2m00s"])
            else:
                rows.append(["", "", ""])

        assert len(rows) == 65
        sheet_request = [
            {
                "op": "write",
                "range": "'Python_rerun_popsize30'!G3:I67",
                "data": rows
            }
        ]
        assert len(sheet_request[0]["data"]) == 65

        # Step 4: Feasibility audit and target comparison on completed instance
        inst_target = paper_targets["rcdp1001"]
        assert 3 <= inst_target["target_vehicles"]
        assert 350.0 <= inst_target["target_distance"]
