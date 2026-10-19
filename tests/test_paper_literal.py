import pytest
import random
from pathlib import Path

from src_paper_literal.problem import Problem, Node
from src_paper_literal.solution import Solution
from src_paper_literal.algorithm9_feasibility import (
    check_feasibility_algorithm9,
    is_route_feasible_operational,
    is_solution_feasible_operational,
)
from src_paper_literal.algorithm10_repair import repair_procedure
from src_paper_literal.algorithm6_crossover import crossover_guided
from src_paper_literal.algorithm7_mutation import mutate_solution
from src_paper_literal.algorithm8_localsearch import combined_local_search
from src_paper_literal.algorithm4_woa import based_on_woa_update
from src_paper_literal.algorithm5_sho import based_on_sho_update, tournament_select
from src_paper_literal.algorithm2_initialization import construct_initial_solution, initialize_solution_sa
from src_paper_literal.algorithm1_solver import PHSHOWOASolver, SolverConfig


@pytest.fixture
def rcdp1001_problem():
    path = Path("data/Wang_Chen/RCdp1001.txt")
    if not path.is_file():
        path = Path("data/RCdp/RCdp1001.txt")
    return Problem.load(path)


def test_problem_loading_txt(rcdp1001_problem):
    p = rcdp1001_problem
    assert p.name.upper() == "RCDP1001"
    assert p.num_customers == 10
    assert p.capacity == 200.0
    assert p.dispatch_cost == 2000.0
    assert p.unit_cost == 1.0
    assert len(p.distance) == 11
    assert len(p.distance[0]) == 11


def test_problem_loading_explicit():
    path = Path("data/Wang_Chen/explicit_cdp101.vrpsdptw")
    if path.is_file():
        p = Problem.load(path)
        assert p.num_customers == 100
        assert p.capacity == 200.0


def test_solution_evaluation(rcdp1001_problem):
    p = rcdp1001_problem
    routes = [[1, 2, 3], [4, 5]]
    sol = Solution(routes, p)
    assert sol.nv == 2
    assert sol.td > 0.0
    assert sol.cost == 2000.0 * 2 + sol.td


def test_algorithm9_literal_capacity_check(rcdp1001_problem):
    p = rcdp1001_problem
    # In RCdp1001, customer index 2 corresponds to CUST 48, which has delivery=10, pickup=40.
    # Algorithm 9 starts load at 0. At customer 2, load = 0 + 10 - 40 = -30 < 0!
    # Even in a single customer route, it must flag load < 0.
    sol = Solution([[2]], p)
    is_feas, note = check_feasibility_algorithm9(sol, p)
    assert not is_feas
    assert "load < 0 (pickup > delivery)" in note


def test_algorithm9_missing_and_duplicate(rcdp1001_problem):
    p = rcdp1001_problem
    # Incomplete solution missing customers:
    # Customer 1 has delivery=10, pickup=10 (net=0). Single customer route [1] doesn't violate capacity.
    # Then Algorithm 9 checks missing customers and flags it.
    sol_missing = Solution([[1]], p)
    is_feas, note = check_feasibility_algorithm9(sol_missing, p)
    assert not is_feas
    assert "missing customer" in note.lower()

    # Duplicate visit: route [1, 1] visits customer 1 twice
    sol_dup = Solution([[1, 1]], p)
    is_feas, note = check_feasibility_algorithm9(sol_dup, p)
    assert not is_feas
    assert "duplicate visit" in note.lower()


def test_construct_and_repair(rcdp1001_problem):
    p = rcdp1001_problem
    rng = random.Random(42)
    s0 = construct_initial_solution(p, rng)
    # Check that all customers 1..10 are present
    custs = [c for r in s0.routes for c in r]
    assert sorted(custs) == list(range(1, 11))
    assert is_solution_feasible_operational(s0, p)


def test_algorithm2_sa(rcdp1001_problem):
    p = rcdp1001_problem
    rng = random.Random(42)
    s0 = construct_initial_solution(p, rng)
    s_opt = initialize_solution_sa(s0, p, rng, t0=1.0, alpha=0.9, t_min=0.1, iter_max=10)
    assert s_opt.td <= s0.td + 1e-6 or s_opt.nv <= s0.nv


def test_crossover_guided(rcdp1001_problem):
    p = rcdp1001_problem
    rng = random.Random(42)
    s1 = construct_initial_solution(p, rng)
    s2 = construct_initial_solution(p, rng)
    offspring = crossover_guided(best=s1, partner=s2, current=s1, problem=p, rng=rng)
    custs = [c for r in offspring.routes for c in r]
    assert sorted(custs) == list(range(1, 11))


def test_mutation_operators(rcdp1001_problem):
    p = rcdp1001_problem
    rng = random.Random(42)
    s = construct_initial_solution(p, rng)
    mut = mutate_solution(s, p, rng)
    custs = [c for r in mut.routes for c in r]
    assert sorted(custs) == list(range(1, 11))


def test_combined_local_search(rcdp1001_problem):
    p = rcdp1001_problem
    rng = random.Random(42)
    s = construct_initial_solution(p, rng)
    ls_sol = combined_local_search(s, p)
    assert ls_sol.cost <= s.cost + 1e-6
    custs = [c for r in ls_sol.routes for c in r]
    assert sorted(custs) == list(range(1, 11))


def test_woa_update(rcdp1001_problem):
    p = rcdp1001_problem
    rng = random.Random(42)
    s = construct_initial_solution(p, rng)
    cand = based_on_woa_update(whale=s, best_whale=s, a=1.5, problem=p, rng=rng)
    custs = [c for r in cand.routes for c in r]
    assert sorted(custs) == list(range(1, 11))


def test_sho_update(rcdp1001_problem):
    p = rcdp1001_problem
    rng = random.Random(42)
    pop = [construct_initial_solution(p, rng) for _ in range(5)]
    cand = based_on_sho_update(hyena=pop[0], best_hyena=pop[0], population=pop, problem=p, rng=rng)
    custs = [c for r in cand.routes for c in r]
    assert sorted(custs) == list(range(1, 11))


def test_end_to_end_solver_smoke(rcdp1001_problem):
    p = rcdp1001_problem
    config = SolverConfig(
        pop_size=5,
        max_iter=5,
        seed=42,
        local_search_interval=2,
        workers=1,
    )
    solver = PHSHOWOASolver(p, config)
    result = solver.solve(run_index=1)
    assert result.instance == "RCdp1001"
    assert result.algo == "PH-SHOWOA-PaperLiteral"
    assert result.run == 1
    assert result.nv >= 1
    assert result.td > 0.0
    assert result.cost == pytest.approx(2000.0 * result.nv + result.td, rel=1e-5)
    # Feasibility under Algorithm 9 is evaluated
    assert isinstance(result.feasible, bool)
    assert isinstance(result.violation_note, str)
    if not result.feasible:
        assert len(result.violation_note) > 0


def test_woa_update_preserves_customer_uniqueness(rcdp1001_problem):
    p = rcdp1001_problem
    rng = random.Random(123)
    s = construct_initial_solution(p, rng)
    # Perform repeated WOA updates across various values of a
    for step in range(25):
        a_val = 2.0 - 2.0 * step / 25
        step_rng = random.Random(1000 + step)
        cand = based_on_woa_update(whale=s, best_whale=s, a=a_val, problem=p, rng=step_rng)
        assert is_solution_feasible_operational(cand, p)
        custs = [c for r in cand.routes for c in r]
        assert sorted(custs) == list(range(1, p.num_customers + 1))


def test_repair_procedure_fixes_duplicate_and_missing(rcdp1001_problem):
    p = rcdp1001_problem
    # Corrupt a valid initial solution by duplicating customer 4 and removing customer 10
    routes = [[4, 7, 2], [4, 6, 5, 3, 8], [1, 9]]
    corrupted = Solution(routes, p)
    repaired = repair_procedure(corrupted, p)
    assert is_solution_feasible_operational(repaired, p)
    assert repaired.nv <= p.max_vehicles
    custs = [c for r in repaired.routes for c in r]
    assert sorted(custs) == list(range(1, p.num_customers + 1))


def test_canonical_name_normalization():
    p1 = Problem("rcdp101", [], [], [], 100, 200.0)
    assert p1.name == "RCdp101"
    p2 = Problem("explicit_rcdp0501.vrpsdptw", [], [], [], 100, 200.0)
    assert p2.name == "RCdp5001"
    p3 = Problem("cdp101.txt", [], [], [], 100, 200.0)
    assert p3.name == "Cdp101"


def test_two_opt_two_customer_route(rcdp1001_problem):
    p = rcdp1001_problem
    # Solution containing a 2-customer route [1, 9]
    sol = Solution([[4, 7, 2], [6, 5, 3, 8, 10], [1, 9]], p)
    assert is_solution_feasible_operational(sol, p)
    ls_sol = combined_local_search(sol, p)
    assert is_solution_feasible_operational(ls_sol, p)
    custs = [c for r in ls_sol.routes for c in r]
    assert sorted(custs) == list(range(1, p.num_customers + 1))

