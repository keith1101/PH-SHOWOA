from pathlib import Path
from src_canonical.problem import Problem
from src_canonical.algorithm1_solver import PHSHOWOASolver, SolverConfig


def test_smoke_solver_rcdp1001():
    inst_path = Path("data/Wang_Chen/explicit_rcdp1001.vrpsdptw")
    if not inst_path.exists():
        inst_path = Path("data/Wang_Chen/rcdp1001.txt")
    problem = Problem.load(inst_path)

    config = SolverConfig(
        pop_size=10,
        max_iter=5,
        seed=42,
        local_search_interval=2,
        workers=1,
    )
    solver = PHSHOWOASolver(problem, config)
    res = solver.solve(run_index=1)

    assert res.feasible, f"Smoke test produced infeasible solution: {res.violation_note}"
    assert res.nv >= 1
    assert res.td > 0.0
    assert res.best_solution is not None


def test_smoke_solver_rcdp2501():
    inst_path = Path("data/Wang_Chen/rcdp2501.txt")
    assert inst_path.exists(), f"Benchmark instance file missing: {inst_path}"
    problem = Problem.load(inst_path)

    config = SolverConfig(
        pop_size=10,
        max_iter=5,
        seed=42,
        local_search_interval=2,
        workers=1,
    )
    solver = PHSHOWOASolver(problem, config)
    res = solver.solve(run_index=1)

    assert res.feasible, f"Smoke test produced infeasible solution: {res.violation_note}"
    assert res.nv >= 1
    assert res.td > 0.0
    assert res.best_solution is not None

