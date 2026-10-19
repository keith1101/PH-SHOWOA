from __future__ import annotations

from typing import List, Tuple
from .problem import Problem
from .solution import Solution


def check_feasibility_algorithm9(solution: Solution, problem: Problem) -> Tuple[bool, str]:
    """
    Algorithm 9. FeasibilityCheck
    EXACT LITERAL FORMULA AS PRINTED IN PAPER (Lines 880-900):

    Input: Solution S, customer data, capacity, travel-time matrix
    Output: true if the solution is feasible; false otherwise.
    1: Initialize visited[1..N] <- false
    2: for each route r in S do
    3: load <- 0; time <- 0
    4: for each consecutive customer pair (i,j) in r do
    5: time <- time + travelTime(i,j)
    6: if j != depot then
    7: if time < readyTime(j) then time <- readyTime(j)
    8: if time > dueTime(j) then return false // time-window violation
    9: load <- load + delivery(j) - pickup(j)
    10: if load < 0 or load > capacity then return false // capacity violation
    11: if visited[j] = true then return false // duplicate visit
    12: visited[j] <- true
    13: time <- time + serviceTime(j)
    14: end if
    15: end for
    16: end for
    17: if exists customer k with visited[k] = false then return false // missing customer
    18: return true
    """
    if solution.nv > problem.max_vehicles:
        return False, f"Vehicle limit exceeded: {solution.nv} > {problem.max_vehicles}"

    visited = [False] * (problem.num_customers + 1)
    for r_idx, r in enumerate(solution.routes):
        load = 0.0
        time = problem.ready_time[0]  # depot start time
        prev = 0
        # consecutive customer pairs (prev, curr)
        for curr in r:
            time += problem.travel_time[prev][curr]
            if curr != 0:
                if time < problem.ready_time[curr]:
                    time = problem.ready_time[curr]
                if time > problem.due_time[curr] + 1e-9:
                    return False, f"Algorithm 9 time-window violation at customer {curr}: arrival {time:.2f} > due {problem.due_time[curr]:.2f}"
                load = load + problem.delivery[curr] - problem.pickup[curr]
                if load < -1e-9:
                    return False, f"Algorithm 9 capacity violation: load < 0 (pickup > delivery) at customer {curr} (load={load:.2f})"
                if load > problem.capacity + 1e-9:
                    return False, f"Algorithm 9 capacity violation: load > capacity ({load:.2f} > {problem.capacity}) at customer {curr}"
                if visited[curr]:
                    return False, f"Algorithm 9 duplicate visit: customer {curr}"
                visited[curr] = True
                time += problem.service_time[curr]
            prev = curr

    for k in range(1, problem.num_customers + 1):
        if not visited[k]:
            return False, f"Algorithm 9 missing customer: {k}"

    return True, ""


def is_route_feasible_operational(route: List[int], problem: Problem) -> bool:
    """
    Standard operational VRPSPDTW route check (Section 3 physical formulation):
    Vehicle departs depot loaded with all deliveries for route customers,
    delivers goods, collects pickups, stays within [0, Q], arrives within time windows,
    and returns to depot before depot due time.
    """
    if not route:
        return True

    # 1. Total initial delivery
    load = sum(problem.delivery[c] for c in route)
    if load > problem.capacity + 1e-9:
        return False

    time = problem.ready_time[0]
    prev = 0
    for curr in route:
        if curr <= 0 or curr > problem.num_customers:
            return False
        time += problem.travel_time[prev][curr]
        if time < problem.ready_time[curr]:
            time = problem.ready_time[curr]
        if time > problem.due_time[curr] + 1e-9:
            return False
        time += problem.service_time[curr]
        load = load - problem.delivery[curr] + problem.pickup[curr]
        if load < -1e-9 or load > problem.capacity + 1e-9:
            return False
        prev = curr

    # Return to depot
    time += problem.travel_time[prev][0]
    if time > problem.due_time[0] + 1e-9:
        return False

    return True


def is_solution_feasible_operational(solution: Solution, problem: Problem) -> bool:
    """Checks physical VRPSPDTW feasibility of the entire solution."""
    if solution.nv > problem.max_vehicles:
        return False
    visited = [False] * (problem.num_customers + 1)
    for r in solution.routes:
        for c in r:
            if c <= 0 or c > problem.num_customers or visited[c]:
                return False
            visited[c] = True
        if not is_route_feasible_operational(r, problem):
            return False
    for k in range(1, problem.num_customers + 1):
        if not visited[k]:
            return False
    return True
