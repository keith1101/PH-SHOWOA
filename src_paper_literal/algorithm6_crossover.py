from __future__ import annotations

import random
from typing import List, Set
from .problem import Problem
from .solution import Solution
from .algorithm10_repair import repair_procedure
from .algorithm9_feasibility import is_route_feasible_operational


def crossover_guided(
    best: Solution,
    partner: Solution,
    current: Solution,
    problem: Problem,
    rng: random.Random,
) -> Solution:
    """
    Algorithm 6. CrossoverGuided for VRPSPDTW
    Preserves 1 or 2 seed routes from best,
    collects remaining customers from partner then current,
    reconstructs routes checking capacity and time feasibility,
    and repairs coverage if necessary.
    """
    if not best.routes:
        return current.copy()

    # Lines 9-13: Select seed routes from best
    num_best_routes = len(best.routes)
    if num_best_routes == 1:
        take = 1
    else:
        take = 1 if rng.random() < 0.6 else 2
        take = min(take, num_best_routes)

    # Line 14: random permutation
    route_indices = list(range(num_best_routes))
    rng.shuffle(route_indices)

    seed_routes: List[List[int]] = []
    kept_customers: Set[int] = set()

    for k in range(take):
        segment = list(best.routes[route_indices[k]])
        seed_routes.append(segment)
        kept_customers.update(segment)

    # Lines 21-30: Collect remaining customers from partner then current
    remaining: List[int] = []
    seen: Set[int] = set(kept_customers)

    for parent in [partner, current]:
        for r in parent.routes:
            for c in r:
                if c not in seen:
                    seen.add(c)
                    remaining.append(c)

    # Lines 32-35: Initialize offspring routes with seed routes
    offspring_routes: List[List[int]] = [list(r) for r in seed_routes]

    # Lines 36-53: Insert remaining customers
    current_route: List[int] = []
    current_load: float = 0.0

    for c in remaining:
        # Paper literal demand formula: line 40: demand <- pickup - delivery
        demand = problem.pickup[c] - problem.delivery[c]

        # Check capacity constraint (and operational route feasibility)
        cand_route = current_route + [c]
        exceeds_cap = len(current_route) >= 1 and (current_load + demand > problem.capacity)
        not_feasible = len(current_route) >= 1 and not is_route_feasible_operational(cand_route, problem)

        if exceeds_cap or not_feasible:
            if current_route:
                offspring_routes.append(current_route)
            current_route = [c]
            current_load = demand
        else:
            current_route.append(c)
            current_load += demand

    if current_route:
        offspring_routes.append(current_route)

    # Wrap as Solution and repair if any customer missing or fleet size exceeded
    offspring = Solution(offspring_routes, problem)
    repaired = repair_procedure(offspring, problem)
    return repaired
