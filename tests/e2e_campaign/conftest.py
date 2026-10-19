import csv
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
TARGETS_CSV = PROJECT_ROOT / "tests" / "paper_performance_targets.csv"

# 65 Canonical instances per Google Sheet tab Python_rerun_popsize30 (Rows 3 to 67)
CANONICAL_65_INSTANCES = [
    "RCdp1001", "RCdp1004", "RCdp1007",
    "RCdp2501", "RCdp2504", "RCdp2507",
    "RCdp5001", "RCdp5004", "RCdp5007",
    "RCdp101", "RCdp102", "RCdp103", "RCdp104", "RCdp105", "RCdp106", "RCdp107", "RCdp108",
    "RCdp201", "RCdp202", "RCdp203", "RCdp204", "RCdp205", "RCdp206", "RCdp207", "RCdp208",
    "Cdp101", "Cdp102", "Cdp103", "Cdp104", "Cdp105", "Cdp106", "Cdp107", "Cdp108", "Cdp109",
    "Cdp201", "Cdp202", "Cdp203", "Cdp204", "Cdp205", "Cdp206", "Cdp207", "Cdp208",
    "Rdp101", "Rdp102", "Rdp103", "Rdp104", "Rdp105", "Rdp106", "Rdp107", "Rdp108", "Rdp109", "Rdp110", "Rdp111", "Rdp112",
    "Rdp201", "Rdp202", "Rdp203", "Rdp204", "Rdp205", "Rdp206", "Rdp207", "Rdp208", "Rdp209", "Rdp210", "Rdp211"
]

SAMPLE_LOG_TEMPLATE = """
NAME: {instance}
TYPE: VRPSPDTW
DIMENSION: 11
VEHICLES: 5
DISPATCHINGCOST: 2000
UNITCOST: 1.0
CAPACITY: 200
---------------------------------Run 1---------------------------
Gen 100 done, already consumed 132 sec
Run 1 finishes
Avg {tc:.4f}, Best {tc:.4f}, Worst {tc:.4f}, Best vehicles {nv}
Best solution update: {tc:.4f}
------------Summary-----------
Total 1 runs, total consumed {runtime_sec} sec
This cost {tc:.6f}, check total cost {tc:.6f}, diff 0.000000
Details of the solution:
{route_details}
vehicle (route) number: {nv}
Total cost: {tc}
In run 1, gen 1000, find this solution, at time {runtime_sec}.
Time to surpass BKS: 0.
command: python -m src --problem data/Wang_Chen/explicit_{instance_lower}.vrpsdptw --runs 1 --pop_size 30 --random_seed {seed}
--instances {instance}
[1/1] run 1/1 seed={seed} -> tmp/pop30_completed/{instance}_seed_{seed}.log

done in {duration_str} | NV={nv} TD={td:.2f} TC={tc:.2f}
"""

SAMPLE_SOLUTION_TEMPLATE = """route 0, node_num 5, cost 104.85, nodes: 0 1 3 8 0
route 1, node_num 5, cost 127.45, nodes: 0 4 7 2 0
route 2, node_num 6, cost 116.68, nodes: 0 6 5 9 10 0
vehicle (route) number: {nv}
Total cost: {tc}
"""

@pytest.fixture
def canonical_instances() -> List[str]:
    return list(CANONICAL_65_INSTANCES)

@pytest.fixture
def paper_targets() -> Dict[str, dict]:
    """Loads tests/paper_performance_targets.csv mapped by lower-case instance name."""
    assert TARGETS_CSV.exists(), f"Target CSV not found at {TARGETS_CSV}"
    targets = {}
    with TARGETS_CSV.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            inst = row["instance"].strip()
            targets[inst.lower()] = {
                "instance": inst,
                "path": row["path"].strip(),
                "size": int(row["size"]),
                "target_vehicles": int(row["target_vehicles"]),
                "target_distance": float(row["target_distance"]),
                "table": int(row["table"]),
            }
    return targets

@pytest.fixture
def sample_log_generator():
    """Generates synthetic log content matching actual Kaggle/PH-SHOWOA solver output."""
    def _generate(instance="RCdp1001", seed=43, nv=3, td=348.98, runtime_sec=134, duration_str="00:02:14"):
        tc = nv * 2000.0 + td
        instance_lower = instance.lower()
        route_details = (
            "route 0, node_num 5, cost 104.846281, nodes: 0 1 3 8 0\n"
            "route 1, node_num 5, cost 127.453528, nodes: 0 4 7 2 0\n"
            "route 2, node_num 6, cost 116.682555, nodes: 0 6 5 9 10 0"
        )
        return SAMPLE_LOG_TEMPLATE.format(
            instance=instance,
            instance_lower=instance_lower,
            seed=seed,
            nv=nv,
            td=td,
            tc=tc,
            runtime_sec=runtime_sec,
            duration_str=duration_str,
            route_details=route_details,
        )
    return _generate

@pytest.fixture
def sample_solution_generator():
    """Generates synthetic solution.txt content."""
    def _generate(nv=3, td=348.98):
        tc = nv * 2000.0 + td
        return SAMPLE_SOLUTION_TEMPLATE.format(nv=nv, tc=tc)
    return _generate
