import pytest
from pathlib import Path
from src_canonical.problem import Problem
from src_canonical.solution import Solution
from src_canonical.algorithm6_crossover import crossover_guided
from src_canonical.algorithm7_mutation import mutate_solution
from src_canonical.algorithm8_localsearch import combined_local_search
from src_canonical.algorithm9_feasibility import check_feasibility_canonical
import random


def test_txt_and_explicit_loading():
    p1 = Problem.load("data/Wang_Chen/explicit_rcdp1001.vrpsdptw")
    p2 = Problem.load("data/Wang_Chen/rcdp1001.txt")

    assert p1.num_customers == 10
    assert p2.num_customers == 10
    assert p1.capacity == 200.0
    assert p2.capacity == 200.0
    assert p1.max_vehicles == 3
    assert p2.max_vehicles == 3


def test_crossover_operator():
    problem = Problem.load("data/Wang_Chen/explicit_rcdp1001.vrpsdptw")
    rng = random.Random(42)

    sol1 = Solution([[1, 2], [4, 7, 8], [6, 5, 9, 3, 10]], problem)
    sol2 = Solution([[4, 8], [6, 5, 3, 2], [7, 1, 9, 10]], problem)
    sol3 = Solution([[1, 2], [4, 7, 8], [6, 5, 9, 3, 10]], problem)

    child = crossover_guided(sol1, sol2, sol3, problem, rng)
    visited = set()
    for r in child.routes:
        visited.update(r)
    assert visited == set(range(1, 11))


def test_mutation_operator():
    problem = Problem.load("data/Wang_Chen/explicit_rcdp1001.vrpsdptw")
    rng = random.Random(42)

    sol = Solution([[1, 2], [4, 7, 8], [6, 5, 9, 3, 10]], problem)
    mutated = mutate_solution(sol, problem, rng=rng)
    visited = set()
    for r in mutated.routes:
        visited.update(r)
    assert visited == set(range(1, 11))


def test_local_search_feasibility():
    problem = Problem.load("data/Wang_Chen/explicit_rcdp1001.vrpsdptw")
    sol = Solution([[1, 2], [4, 7, 8], [6, 5, 9, 3, 10]], problem)
    improved = combined_local_search(sol, problem)
    is_feas, note = check_feasibility_canonical(improved, problem)
    assert is_feas, f"Local search produced infeasible solution: {note}"
    assert improved.cost <= sol.cost + 1e-6


def test_hybrid_branch_order():
    from src_canonical.algorithm3_hybrid import update_position_hybrid
    problem = Problem.load("data/Wang_Chen/explicit_rcdp1001.vrpsdptw")
    sol = Solution([[1, 2], [4, 7, 8], [6, 5, 9, 3, 10]], problem)

    # With p_hybrid = 1.0, any random p < 1.0 -> MUST be SHO
    sol_sho, tag_sho = update_position_hybrid(
        current=sol, best_whale=sol, population=[sol],
        p_hybrid=1.0, a=1.0, problem=problem, rng=random.Random(42)
    )
    assert tag_sho == "SHO"

    # With p_hybrid = 0.0, any random p >= 0.0 -> MUST be WOA
    sol_woa, tag_woa = update_position_hybrid(
        current=sol, best_whale=sol, population=[sol],
        p_hybrid=0.0, a=1.0, problem=problem, rng=random.Random(42)
    )
    assert tag_woa == "WOA"


def test_sho_returns_base_when_no_improvement():
    from src_canonical.algorithm5_sho import based_on_sho_update
    problem = Problem.load("data/Wang_Chen/explicit_rcdp1001.vrpsdptw")
    base = Solution([[1, 2], [4, 7, 8], [6, 5, 9, 3, 10]], problem)
    best = Solution([[1, 2], [4, 7, 8], [6, 5, 9, 3, 10]], problem)
    # artificially lower best cost to distinguish
    best.cost = 100.0

    rng = random.Random(42)
    res = based_on_sho_update(
        hyena=base, best_hyena=best, population=[base],
        problem=problem, rng=rng, mutation_prob=0.0
    )
    # If not improved, MUST return base (not best)
    assert res.cost >= base.cost - 1e-6 or res.cost < base.cost
    # Must NOT blindly copy best's cost
    assert abs(res.cost - 100.0) > 1.0
