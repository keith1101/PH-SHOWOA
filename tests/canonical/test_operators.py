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


def test_sho_candidate_does_not_blindly_copy_best():
    """
    Direction B & Paper Line 20 Fix:
    Ensures that based_on_sho_update does NOT blindly copy best_hyena's cost,
    which would cause premature population collapse.
    """
    from src_canonical.algorithm5_sho import based_on_sho_update
    problem = Problem.load("data/Wang_Chen/explicit_rcdp1001.vrpsdptw")
    base = Solution([[1, 2], [4, 7, 8], [6, 5, 9, 3, 10]], problem)
    best = Solution([[1, 2], [4, 7, 8], [6, 5, 9, 3, 10]], problem)
    best.cost = 100.0

    rng = random.Random(42)
    res = based_on_sho_update(
        hyena=base, best_hyena=best, population=[base],
        problem=problem, rng=rng, mutation_prob=0.0
    )
    # Must NOT blindly copy best's cost
    assert abs(res.cost - 100.0) > 1.0
    is_feas, note = check_feasibility_canonical(res, problem)
    assert is_feas, f"Candidate infeasible: {note}"


def test_sho_candidate_generator_direction_b():
    """
    Direction B: based_on_sho_update acts as candidate generator and CAN return
    a feasible candidate with cost > base.cost (worse solution) so Master SA can evaluate it.
    """
    from src_canonical.algorithm5_sho import based_on_sho_update
    problem = Problem.load("data/Wang_Chen/explicit_rcdp1001.vrpsdptw")
    # Generate a high-performing base solution
    sol_init = Solution([[1, 2], [4, 7, 8], [6, 5, 9, 3, 10]], problem)
    sol_better = based_on_sho_update(
        hyena=sol_init,
        best_hyena=Solution([[4, 8], [6, 5, 3, 2], [7, 1, 9, 10]], problem),
        population=[sol_init],
        problem=problem,
        rng=random.Random(10),
        mutation_prob=0.8,
    )
    # With seed 1, candidate generated is worse than sol_better
    res_worse = based_on_sho_update(
        hyena=sol_better,
        best_hyena=sol_better,
        population=[sol_better],
        problem=problem,
        rng=random.Random(1),
        mutation_prob=0.5,
    )
    assert res_worse.cost > sol_better.cost + 1e-6, "Direction B must allow returning worse candidate"
    is_feas, note = check_feasibility_canonical(res_worse, problem)
    assert is_feas, f"Generated candidate must be feasible: {note}"


def test_woa_candidate_generator_direction_b():
    """
    Direction B: based_on_woa_update acts as candidate generator and CAN return
    a feasible candidate with cost > base.cost (worse solution) so Master SA can evaluate it.
    """
    from src_canonical.algorithm4_woa import based_on_woa_update
    from src_canonical.algorithm2_initialization import construct_initial_solution
    problem = Problem.load("data/Wang_Chen/rcdp2501.txt")
    s1 = construct_initial_solution(problem, random.Random(42))
    s_best = construct_initial_solution(problem, random.Random(43))

    # Seed 55 produces a candidate with cost > s1.cost
    woa_cand = based_on_woa_update(whale=s1, best_whale=s_best, a=2.0, problem=problem, rng=random.Random(55))
    assert woa_cand.cost > s1.cost + 1e-6, "Direction B must allow returning worse candidate from WOA"
    is_feas, note = check_feasibility_canonical(woa_cand, problem)
    assert is_feas, f"Generated candidate must be feasible: {note}"


def test_master_sa_metropolis_acceptance_direction_b():
    """
    Direction B: Deep verification of Master SA Metropolis criterion in Algorithm 1.
    Tests metropolis_accept across improving, equal, worse, freezing (T=0), and extreme boundaries.
    """
    from src_canonical.algorithm1_solver import metropolis_accept

    # 1. Improving candidate: always accepted regardless of T or RNG
    assert metropolis_accept(current_cost=6000.0, candidate_cost=5500.0, temperature=1.0, rng=random.Random(1)) is True
    assert metropolis_accept(current_cost=6000.0, candidate_cost=5500.0, temperature=0.0, rng=random.Random(1)) is True

    # 2. Equal cost candidate: always accepted (neutral plateau exploration)
    assert metropolis_accept(current_cost=6000.0, candidate_cost=6000.0, temperature=1.0, rng=random.Random(1)) is True
    assert metropolis_accept(current_cost=6000.0, candidate_cost=6000.0, temperature=0.0, rng=random.Random(1)) is True

    # 3. Worse candidate at high temperature (T = 1.0): strictly positive probability
    # delta = 50 on cost 6000 -> prob = exp(-50 / 6000.000001) ~ 0.9917
    rng_lucky = random.Random(42)  # rng_lucky.random() is ~0.6394 < 0.9917
    assert metropolis_accept(current_cost=6000.0, candidate_cost=6050.0, temperature=1.0, rng=rng_lucky) is True

    # 4. Worse candidate at freezing temperature (T = 0.0): strictly rejected
    # arg = -50 / 1e-6 = -50,000,000 < -700.0 -> prob = 0.0 -> must be False
    rng_any = random.Random(42)
    assert metropolis_accept(current_cost=6000.0, candidate_cost=6050.0, temperature=0.0, rng=rng_any) is False

    # 5. Massive delta (underflow guard): arg << -700.0 -> returns False without exception
    assert metropolis_accept(current_cost=6000.0, candidate_cost=1e8, temperature=1.0, rng=random.Random(1)) is False

    # 6. Degenerate boundaries: zero current cost and zero temperature
    assert metropolis_accept(current_cost=0.0, candidate_cost=10.0, temperature=0.0, rng=random.Random(1)) is False



def test_operator_fallback_on_repair_failure():
    """
    Direction B: When an operator candidate cannot be made feasible (repair fails),
    it must safely fall back to the base solution without raising errors or returning
    infeasible solutions.
    """
    from unittest import mock
    from src_canonical.algorithm5_sho import based_on_sho_update
    from src_canonical.algorithm4_woa import based_on_woa_update
    problem = Problem.load("data/Wang_Chen/explicit_rcdp1001.vrpsdptw")
    base = Solution([[1, 2], [4, 7, 8], [6, 5, 9, 3, 10]], problem)
    best = Solution([[1, 2], [4, 7, 8], [6, 5, 9, 3, 10]], problem)

    # Mock is_solution_feasible to return False (simulating complete repair failure)
    with mock.patch("src_canonical.algorithm5_sho.is_solution_feasible", return_value=False):
        res_sho = based_on_sho_update(
            hyena=base, best_hyena=best, population=[base],
            problem=problem, rng=random.Random(42)
        )
        assert res_sho.routes == base.routes
        assert res_sho.cost == base.cost

    with mock.patch("src_canonical.algorithm4_woa.is_solution_feasible", return_value=False):
        res_woa = based_on_woa_update(
            whale=base, best_whale=best, a=1.0,
            problem=problem, rng=random.Random(42)
        )
        assert res_woa.routes == base.routes
        assert res_woa.cost == base.cost


def test_solver_master_sa_active_direction_b():
    """
    Direction B: Integration test on PHSHOWOASolver confirming that
    worse candidates (nf > cf) are actively generated by sub-operators
    and processed by the Master SA Metropolis criterion during an actual run.
    """
    from src_canonical.algorithm1_solver import PHSHOWOASolver, SolverConfig
    import src_canonical.algorithm1_solver as solver_mod

    problem = Problem.load("data/Wang_Chen/explicit_rcdp1001.vrpsdptw")
    worse_evaluated = 0

    orig_accept = solver_mod.metropolis_accept

    def tracking_accept(current_cost: float, candidate_cost: float, temperature: float, rng: random.Random) -> bool:
        nonlocal worse_evaluated
        if candidate_cost > current_cost:
            worse_evaluated += 1
        return orig_accept(current_cost, candidate_cost, temperature, rng)

    solver_mod.metropolis_accept = tracking_accept
    try:
        config = SolverConfig(pop_size=20, max_iter=10, seed=42, workers=1)
        solver = PHSHOWOASolver(problem, config)
        res = solver.solve(run_index=1)
        assert res.feasible, f"Solver produced infeasible solution: {res.violation_note}"
        assert worse_evaluated > 0, "Direction B must generate and evaluate worse candidates in Master SA"
    finally:
        solver_mod.metropolis_accept = orig_accept



