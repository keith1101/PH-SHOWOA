import pytest
from pathlib import Path
from src_canonical.problem import Problem
from src_canonical.solution import Solution
from src_canonical.algorithm9_feasibility import check_feasibility_canonical, is_route_feasible


def test_feasibility_rcdp1001():
    inst_path = Path("data/Wang_Chen/explicit_rcdp1001.vrpsdptw")
    if not inst_path.exists():
        inst_path = Path("data/Wang_Chen/rcdp1001.txt")
    problem = Problem.load(inst_path)

    # Feasible 3-vehicle partition on RCdp1001:
    # Route 1: 0 -> 1 -> 2 -> 0
    # Route 2: 0 -> 4 -> 7 -> 8 -> 0
    # Route 3: 0 -> 6 -> 5 -> 9 -> 3 -> 10 -> 0
    r1 = [1, 2]
    r2 = [4, 7, 8]
    r3 = [6, 5, 9, 3, 10]

    sol = Solution([r1, r2, r3], problem)
    is_feas, note = check_feasibility_canonical(sol, problem)
    assert is_feas, f"Feasibility failed: {note}"
    assert sol.nv == 3


def test_capacity_violation_caught():
    inst_path = Path("data/Wang_Chen/explicit_rcdp1001.vrpsdptw")
    if not inst_path.exists():
        inst_path = Path("data/Wang_Chen/rcdp1001.txt")
    problem = Problem.load(inst_path)

    # Force capacity to 50 so that total delivery (144) exceeds capacity Q
    problem.capacity = 50.0
    r_huge = list(range(1, problem.num_customers + 1))
    sol = Solution([r_huge], problem)
    is_feas, note = check_feasibility_canonical(sol, problem)
    assert not is_feas
    assert "capacity" in note.lower() or "exceeds" in note.lower()
