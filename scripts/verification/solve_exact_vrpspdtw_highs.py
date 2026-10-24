import sys
from pathlib import Path
import highspy
import numpy as np

sys.path.insert(0, "D:/Project/PH-SHOWOA")
from src_canonical.problem import Problem
from src_canonical.algorithm9_feasibility import check_feasibility_canonical
from src_canonical.solution import Solution

DATA_DIR = Path("D:/Project/PH-SHOWOA/data/Wang_Chen")

def solve_exact_highs_vrpspdtw(prob: Problem, time_limit_sec: float = 30.0):
    n = prob.num_customers
    nodes = list(range(n + 1))  # 0 is depot, 1..n customers
    Q = prob.capacity
    M_time = prob.due_time[0] + 100.0
    M_cost = 2000.0  # Fleet minimization penalty
    
    h = highspy.Highs()
    h.setOptionValue("output_flag", True)
    h.setOptionValue("time_limit", time_limit_sec)
    
    # 1. Variables:
    # x[i, j] in {0, 1} for i != j
    # t[i] >= ready[i] (arrival/service start time at node i)
    # L[i] in [0, Q] (vehicle load immediately upon departure from node i)
    # nv: integer number of vehicles used (sum x[0, j] for j in 1..n)
    
    var_map = {}
    col_idx = 0
    
    # x[i, j]
    for i in nodes:
        for j in nodes:
            if i != j:
                # Can vehicle travel from i to j?
                # Check basic time window feasibility
                if i != 0 and j != 0:
                    earliest = prob.ready_time[i] + prob.service_time[i] + prob.travel_time[i][j]
                    if earliest > prob.due_time[j]:
                        continue
                var_name = f"x_{i}_{j}"
                var_map[var_name] = col_idx
                # Cost is distance[i][j] + (M_cost if i == 0 else 0)
                cost = prob.distance[i][j] + (M_cost if i == 0 else 0.0)
                h.addVar(0.0, 1.0)
                h.changeColIntegrality(col_idx, highspy.HighsVarType.kInteger)
                h.changeColCost(col_idx, cost)
                col_idx += 1
                
    # t[i] for i in nodes
    t_start = col_idx
    for i in nodes:
        var_name = f"t_{i}"
        var_map[var_name] = col_idx
        h.addVar(prob.ready_time[i], prob.due_time[i])
        h.changeColIntegrality(col_idx, highspy.HighsVarType.kContinuous)
        h.changeColCost(col_idx, 0.0)
        col_idx += 1
        
    # L[i] for i in nodes
    L_start = col_idx
    for i in nodes:
        var_name = f"L_{i}"
        var_map[var_name] = col_idx
        h.addVar(0.0, Q)
        h.changeColIntegrality(col_idx, highspy.HighsVarType.kContinuous)
        h.changeColCost(col_idx, 0.0)
        col_idx += 1
        
    h.changeObjectiveSense(highspy.ObjSense.kMinimize)
    
    # 2. Constraints:
    # A. Each customer visited exactly once: sum_{i != j} x[i, j] == 1 for all j in 1..n
    for j in range(1, n + 1):
        in_vars = [var_map[f"x_{i}_{j}"] for i in nodes if f"x_{i}_{j}" in var_map]
        h.addRow(1.0, 1.0, len(in_vars), np.array(in_vars, dtype=np.int32), np.ones(len(in_vars)))
        
    # B. Flow conservation: sum_{j != i} x[i, j] - sum_{j != i} x[j, i] == 0 for all i in 1..n
    for i in range(1, n + 1):
        out_vars = [var_map[f"x_{i}_{j}"] for j in nodes if f"x_{i}_{j}" in var_map]
        in_vars = [var_map[f"x_{j}_{i}"] for j in nodes if f"x_{j}_{i}" in var_map]
        all_cols = out_vars + in_vars
        all_vals = [1.0] * len(out_vars) + [-1.0] * len(in_vars)
        h.addRow(0.0, 0.0, len(all_cols), np.array(all_cols, dtype=np.int32), np.array(all_vals))
        
    # C. Time Window propagation (MTZ subtour elimination):
    # t[i] + service[i] + travel_time[i][j] - M_time * (1 - x[i, j]) <= t[j]
    # => t[i] - t[j] + M_time * x[i, j] <= M_time - service[i] - travel_time[i][j]
    for i in range(1, n + 1):
        for j in range(1, n + 1):
            if f"x_{i}_{j}" in var_map:
                x_ij = var_map[f"x_{i}_{j}"]
                t_i = var_map[f"t_{i}"]
                t_j = var_map[f"t_{j}"]
                rhs = M_time - prob.service_time[i] - prob.travel_time[i][j]
                cols = np.array([t_i, t_j, x_ij], dtype=np.int32)
                vals = np.array([1.0, -1.0, M_time])
                h.addRow(-highspy.kHighsInf, rhs, 3, cols, vals)
                
    # D. Simultaneous Pickup & Delivery dynamic load tracking:
    # Vehicle arrives at j with load, drops delivery[j], picks up pickup[j]
    # L[j] >= L[i] - delivery[j] + pickup[j] - Q * (1 - x[i, j])  (for i != 0, j != 0)
    # => L[i] - L[j] + Q * x[i, j] <= Q + delivery[j] - pickup[j]
    for i in range(1, n + 1):
        for j in range(1, n + 1):
            if f"x_{i}_{j}" in var_map:
                x_ij = var_map[f"x_{i}_{j}"]
                L_i = var_map[f"L_{i}"]
                L_j = var_map[f"L_{j}"]
                rhs = Q + prob.delivery[j] - prob.pickup[j]
                cols = np.array([L_i, L_j, x_ij], dtype=np.int32)
                vals = np.array([1.0, -1.0, Q])
                h.addRow(-highspy.kHighsInf, rhs, 3, cols, vals)

    # Depot outbound load upper bound: L[0] <= Q
    # For first customer j visited from depot:
    # L[j] >= delivery_first_customer ? In fact, L[j] is the load after serving j.
    # Customer j load bounds: L[j] >= pickup[j], L[j] <= Q
    for j in range(1, n + 1):
        L_j = var_map[f"L_{j}"]
        h.changeColBounds(L_j, prob.pickup[j], Q)

    # 3. Solve exact MILP with HiGHS
    h.run()
    
    status = h.getModelStatus()
    print(f"\nHiGHS Exact Solver Status: {h.modelStatusToString(status)}")
    
    if status in (highspy.HighsModelStatus.kOptimal, highspy.HighsModelStatus.kTimeLimit):
        obj = h.getObjectiveValue()
        sol = h.getSolution()
        col_vals = sol.col_value
        
        # Reconstruct routes
        active_arcs = []
        for (name, col) in var_map.items():
            if name.startswith("x_") and col_vals[col] > 0.5:
                _, u, v = name.split("_")
                active_arcs.append((int(u), int(v)))
                
        # Build route paths from 0
        routes = []
        for u, v in active_arcs:
            if u == 0:
                curr = v
                route = [curr]
                while curr != 0:
                    next_nodes = [dst for src, dst in active_arcs if src == curr]
                    if not next_nodes:
                        break
                    curr = next_nodes[0]
                    if curr != 0:
                        route.append(curr)
                routes.append(route)
                
        num_vehicles = len(routes)
        total_dist = obj - M_cost * num_vehicles
        return {
            "status": h.modelStatusToString(status),
            "num_vehicles": num_vehicles,
            "total_distance": total_dist,
            "hierarchical_cost": obj,
            "routes": routes
        }
    return None

if __name__ == "__main__":
    prob = Problem.load(DATA_DIR / "RCdp1001.txt")
    print("=" * 80)
    print(f"SOLVING EXACT VRPSPDTW MILP FOR {prob.name} USING HIGHS")
    print("=" * 80)
    exact_res = solve_exact_highs_vrpspdtw(prob, time_limit_sec=20.0)
    if exact_res:
        print(f"Exact Global Optimum: NV = {exact_res['num_vehicles']}, TD = {exact_res['total_distance']:.2f}")
        print(f"Optimal Routes: {exact_res['routes']}")
