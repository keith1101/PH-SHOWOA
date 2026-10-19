from __future__ import annotations

import math
import random
from typing import List
from .problem import Problem
from .solution import Solution
from .algorithm7_mutation import _apply_intra_operation, _apply_inter_operation
from .algorithm9_feasibility import is_route_feasible_operational, is_solution_feasible_operational
from .algorithm10_repair import repair_procedure


def based_on_woa_update(
    whale: Solution,
    best_whale: Solution,
    a: float,
    problem: Problem,
    rng: random.Random,
) -> Solution:
    """
    Algorithm 4. BasedOnWOAUpdate (Best-Guided Intensification)
    Encircling prey, spiral movement, and controlled local perturbations
    anchored to the current global best solution.
    """
    routes = [list(r) for r in whale.routes if len(r) > 0]
    best_routes = [list(r) for r in best_whale.routes if len(r) > 0]

    dim = len(routes)
    best_dim = len(best_routes)
    limit = min(dim, best_dim)

    # Line 9-10: Random vectors A in [-a, a], C in [0, 2]
    coeff_a = [2.0 * a * rng.random() - a for _ in range(dim)]
    coeff_c = [2.0 * rng.random() for _ in range(dim)]

    for i in range(limit):
        p = rng.random()
        route = routes[i]
        best_route = best_routes[i]
        backup_all_routes = [list(r) for r in routes]

        ai = coeff_a[i]
        ci = coeff_c[i]

        if p < 0.5:
            if abs(ai) < 1.0:
                # ENCIRCLING_PREY: align shared customer order toward best_route
                fraction = (1.0 - abs(ai)) * (ci / 2.0)
                _relink(route, best_route, fraction, ai >= 0.0)
            else:
                if rng.random() < 0.5:
                    # ApplyRandomOperation (intra: swap, insert, 2-opt)
                    op = rng.randint(0, 2)
                    _apply_intra_operation(route, op, rng)
                else:
                    # ApplyRandomMultiRouteOperation (inter: Pd-shift, Pd-exchange)
                    op = rng.randint(0, 1)
                    _apply_inter_operation(routes, op, rng)
                    all_ok = all(is_route_feasible_operational(r, problem) for r in routes)
                    if not all_ok:
                        routes = backup_all_routes
                        route = routes[i]
        else:
            # SPIRAL_MOVEMENT
            l = ci - 1.0
            fraction = min(1.0, abs(math.exp(l) * math.cos(2.0 * math.pi * l)))
            _relink(route, best_route, fraction, l >= 0.0)

        # Line 33-35: Route feasibility check
        if not is_route_feasible_operational(route, problem):
            routes = backup_all_routes

    # Clean empty routes
    routes = [r for r in routes if len(r) > 0]
    cand = Solution(routes, problem)

    # Validate overall candidate solution (Paper lines 37-39: ValidateRoutes)
    if not is_solution_feasible_operational(cand, problem):
        cand = repair_procedure(cand, problem)
        if not is_solution_feasible_operational(cand, problem):
            return whale.copy()

    return cand


def _relink(route: List[int], target_route: List[int], fraction: float, from_start: bool) -> None:
    """Relinks the shared customer order in route toward target_route order."""
    target_pos = {c: idx for idx, c in enumerate(target_route)}
    shared_indices = [i for i, c in enumerate(route) if c in target_pos]
    m = len(shared_indices)
    if m < 2:
        return

    num_insertions = max(1, min(m - 1, int(math.ceil(m * fraction))))
    shared_customers = [route[i] for i in shared_indices]
    target_order = sorted(shared_customers, key=lambda c: target_pos[c])

    if not from_start:
        target_order.reverse()
        shared_indices = shared_indices[::-1]

    # Insert up to num_insertions customers in the target relative positions
    for step in range(num_insertions):
        desired_c = target_order[step]
        cur_idx = shared_customers.index(desired_c)
        if cur_idx != step:
            shared_customers.pop(cur_idx)
            shared_customers.insert(step, desired_c)

    if not from_start:
        shared_customers.reverse()
        shared_indices = shared_indices[::-1]

    for idx, c in zip(shared_indices, shared_customers):
        route[idx] = c
