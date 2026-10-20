from __future__ import annotations

import random
from typing import List, Set
from .problem import Problem
from .solution import Solution
from .algorithm10_repair import repair_procedure
from .algorithm9_feasibility import is_route_feasible


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
    reconstructs routes checking operational capacity and time feasibility,
    and repairs coverage if necessary.
    """
    if not best.routes:
        return current.copy()

    num_best_routes = len(best.routes)
    if num_best_routes == 1:
        take = 1
    else:
        take = 1 if rng.random() < 0.6 else 2
        take = min(take, num_best_routes)

    route_indices = list(range(num_best_routes))
    rng.shuffle(route_indices)

    seed_routes: List[List[int]] = []
    kept_customers: Set[int] = set()

    for k in range(take):
        segment = list(best.routes[route_indices[k]])
        seed_routes.append(segment)
        kept_customers.update(segment)

    # Collect remaining customers from partner then current
    remaining: List[int] = []
    seen: Set[int] = set(kept_customers)

    for parent in [partner, current]:
        for r in parent.routes:
            for c in r:
                if c not in seen:
                    seen.add(c)
                    remaining.append(c)

    # Initialize offspring routes with seed routes
    offspring_routes: List[List[int]] = [list(r) for r in seed_routes]

    # Insert remaining customers
    current_route: List[int] = []

    for c in remaining:
        cand_route = current_route + [c]
        if current_route and not is_route_feasible(cand_route, problem):
            offspring_routes.append(current_route)
            current_route = [c]
        else:
            current_route.append(c)

    if current_route:
        offspring_routes.append(current_route)

    # Wrap as Solution and repair if necessary
    offspring = Solution(offspring_routes, problem)
    repaired = repair_procedure(offspring, problem)
    return repaired
