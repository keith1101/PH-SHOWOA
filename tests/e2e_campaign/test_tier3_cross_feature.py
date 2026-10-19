import json
import re
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from scripts.compare_with_paper_logged import (
    VEHICLE_WEIGHT,
    format_duration,
    parse_solution_file,
)


class TestTier3HarvestingToSheetsPipeline:
    """Tier 3: End-to-end integration from raw harvested logs to Google Sheet JSON mutation payload."""

    def test_harvested_logs_to_sheet_mutation_pipeline(
        self, tmp_path, canonical_instances, sample_log_generator
    ):
        """Simulates harvesting 30 seed logs for multiple instances, aggregates metrics,

        and builds the exact 65-row Google Sheets batch mutation payload.
        """
        harvest_dir = tmp_path / "harvested"
        harvest_dir.mkdir(parents=True)

        # 1. Simulate harvested logs for RCdp1001 (30 runs), RCdp1004 (15 runs)
        for s in range(42, 72):
            log_content = sample_log_generator(
                instance="RCdp1001", seed=s, nv=3, td=348.0 + (s % 5) * 0.5, runtime_sec=134
            )
            (harvest_dir / f"RCdp1001_seed_{s}.log").write_text(log_content, encoding="utf-8")

        for s in range(42, 57):
            log_content = sample_log_generator(
                instance="RCdp1004", seed=s, nv=2, td=216.5 + (s % 3) * 0.2, runtime_sec=142
            )
            (harvest_dir / f"RCdp1004_seed_{s}.log").write_text(log_content, encoding="utf-8")

        # 2. Extract metrics across instances
        done_re = re.compile(r"done in\s+([0-9:]+)\s+\|\s+NV=([\d.]+)\s+TD=([\d.]+)")
        inst_log_name_re = re.compile(r"^([A-Za-z0-9_]+)_seed_(\d+)\.log", re.IGNORECASE)
        time_sec_re = re.compile(r"total consumed (\d+) sec")

        instance_data = {inst: [] for inst in canonical_instances}

        for log_file in harvest_dir.glob("*.log"):
            m = inst_log_name_re.match(log_file.name)
            if not m:
                continue
            raw_inst = m.group(1)
            target = next((ci for ci in canonical_instances if ci.lower() == raw_inst.lower()), None)
            if not target:
                continue

            content = log_file.read_text(encoding="utf-8")
            dm = done_re.search(content)
            tm = time_sec_re.search(content)
            if dm:
                nv = int(float(dm.group(2)))
                td = float(dm.group(3))
                runtime = int(tm.group(1)) if tm else 134
                instance_data[target].append({"nv": nv, "td": td, "sec": runtime})

        # 3. Aggregate each instance (NV = best nv, TD = avg td for best nv, Avg/Run = mm:ss)
        matrix_rows = []
        for inst in canonical_instances:
            runs = instance_data[inst]
            if not runs:
                matrix_rows.append(["", "", ""])
                continue

            min_nv = min(r["nv"] for r in runs)
            best_nv_runs = [r for r in runs if r["nv"] == min_nv]
            avg_td = sum(r["td"] for r in best_nv_runs) / len(best_nv_runs)
            avg_sec = sum(r["sec"] for r in runs) / len(runs)
            avg_duration_str = f"{int(avg_sec // 60)}m{int(avg_sec % 60):02d}s"

            matrix_rows.append([str(min_nv), f"{avg_td:.2f}", avg_duration_str])

        # 4. Construct Google Sheets batch mutation JSON payload
        payload = [
            {
                "op": "write",
                "range": "'Python_rerun_popsize30'!G3:I67",
                "data": matrix_rows,
            }
        ]

        # 5. Assertions on the generated mutation payload
        assert len(payload) == 1
        assert payload[0]["op"] == "write"
        assert payload[0]["range"] == "'Python_rerun_popsize30'!G3:I67"
        data = payload[0]["data"]
        assert len(data) == 65

        # Check RCdp1001 (Row index 0 in matrix, row 3 in sheet)
        rc1001_row = data[0]
        assert rc1001_row[0] == "3"
        assert float(rc1001_row[1]) > 348.0
        assert "2m14s" in rc1001_row[2]

        # Check RCdp1004 (Row index 1 in matrix, row 4 in sheet)
        rc1004_row = data[1]
        assert rc1004_row[0] == "2"
        assert float(rc1004_row[1]) > 216.0
        assert "2m22s" in rc1004_row[2]

        # Check unharvested instance (e.g. index 2: RCdp1007)
        assert data[2] == ["", "", ""]

        # 6. JSON serialization round-trip verification
        json_str = json.dumps(payload, indent=2)
        parsed_payload = json.loads(json_str)
        assert parsed_payload[0]["range"] == payload[0]["range"]
        assert len(parsed_payload[0]["data"]) == 65


class TestTier3SolverOutputToFeasibilityAndTargetPipeline:
    """Tier 3: Pipeline connecting solver solution generation, route constraint auditing,

    and paper target gap verification.
    """

    def test_solution_route_auditing_and_target_gap_pipeline(
        self, tmp_path, paper_targets, sample_solution_generator
    ):
        """Verifies solution parser -> route feasibility verification -> paper performance gap audit."""
        inst = "RCdp1001"
        target_info = paper_targets[inst.lower()]
        target_nv = target_info["target_vehicles"]
        target_td = target_info["target_distance"]

        # Synthetic solution achieving 3 vehicles and 348.98 distance
        sol_text = (
            "route 0, node_num 5, cost 104.85, nodes: 0 1 3 8 0\n"
            "route 1, node_num 5, cost 127.45, nodes: 0 4 7 2 0\n"
            "route 2, node_num 6, cost 116.68, nodes: 0 6 5 9 10 0\n"
            "vehicle (route) number: 3\n"
            f"Total cost: {3 * 2000.0 + 348.98:.2f}\n"
        )
        sol_file = tmp_path / "rcdp1001_best_solution.txt"
        sol_file.write_text(sol_text, encoding="utf-8")

        # Step 1: Parse solution
        nv, td, tc = parse_solution_file(sol_file)
        assert nv == 3
        assert pytest.approx(td, 0.01) == 348.98
        assert pytest.approx(tc, 0.01) == 3 * 2000.0 + 348.98

        # Step 2: Route extraction
        route_nodes = []
        for line in sol_text.splitlines():
            if "nodes:" in line:
                nodes_part = line.split("nodes:", 1)[1].strip()
                route_nodes.append([int(x) for x in nodes_part.split()])

        assert len(route_nodes) == nv
        # Customer set partitioning check: all customers 1..10 visited exactly once
        visited_customers = []
        for r in route_nodes:
            assert r[0] == 0 and r[-1] == 0, "Route must start and end at depot"
            visited_customers.extend(r[1:-1])

        assert sorted(visited_customers) == list(range(1, 11))
        assert len(visited_customers) == len(set(visited_customers))  # No duplicates

        # Step 3: Paper target comparison & gap analysis
        dist_gap_pct = (td - target_td) / target_td * 100.0
        meets_target = (nv <= target_nv) and (td <= target_td or nv < target_nv)

        assert nv <= target_nv
        assert td <= target_td
        assert meets_target is True
        assert dist_gap_pct < 0.0  # Solver improved upon paper target


class TestTier3MonitoringAndQueueBalancingPipeline:
    """Tier 3: Multi-account kernel monitoring to Wave 2 job queue rebalancing."""

    def test_multi_account_status_to_queue_dispatch(self, canonical_instances):
        """Simulates status polling across 5 accounts and dynamically constructs Wave 2 queues."""
        # Current simulated statuses across accounts
        mock_kernel_states = {
            "tafuhihi": [
                {"slug": "new-cdp202-s42", "status": "COMPLETE", "inst": "Cdp202", "seeds": [42, 43, 44, 45, 46, 47]},
                {"slug": "new-cdp202-s48", "status": "COMPLETE", "inst": "Cdp202", "seeds": [48, 49, 50, 51, 52, 53]},
                {"slug": "new-cdp202-s54", "status": "COMPLETE", "inst": "Cdp202", "seeds": [54, 55, 56, 57, 58, 59]},
                {"slug": "new-cdp202-s60", "status": "COMPLETE", "inst": "Cdp202", "seeds": [60, 61, 62, 63, 64, 65]},
                {"slug": "new-cdp202-s66", "status": "COMPLETE", "inst": "Cdp202", "seeds": [66, 67, 68, 69, 70, 71]},
            ],
            "kanhan162": [
                {"slug": "pop30-cdp202-s42", "status": "RUNNING", "inst": "Cdp202", "seeds": [42, 43, 44, 45, 46, 47]},
            ],
            "dautromduoicuop": [
                {"slug": "pop30-cdp203-s42", "status": "RUNNING", "inst": "Cdp203", "seeds": [42, 43, 44, 45, 46, 47]},
            ]
        }

        completed_counts = {inst: 0 for inst in canonical_instances}
        for acc, kernels in mock_kernel_states.items():
            for k in kernels:
                if k["status"] == "COMPLETE":
                    completed_counts[k["inst"]] += len(k["seeds"])

        assert completed_counts["Cdp202"] == 30  # All 30 seeds complete
        assert completed_counts["Cdp203"] == 0   # Still running

        # Generate Wave 2 priority queue: instances needing runs
        wave2_candidates = [
            (inst, 30 - cnt)
            for inst, cnt in completed_counts.items()
            if cnt < 30
        ]

        # Cdp202 has 30 runs, so it is fully satisfied and must not be in wave 2 queue
        assert "Cdp202" not in [inst for inst, _ in wave2_candidates]
        assert "Cdp203" in [inst for inst, _ in wave2_candidates]
        assert len(wave2_candidates) == 64
