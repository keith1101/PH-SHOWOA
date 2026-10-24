import sys
from pathlib import Path
import math
from ortools.constraint_solver import routing_enums_pb2
from ortools.constraint_solver import pywrapcp

sys.path.insert(0, "D:/Project/PH-SHOWOA")
from src_canonical.problem import Problem
from src_canonical.algorithm1_solver import PHSHOWOASolver, SolverConfig

DATA_DIR = Path("D:/Project/PH-SHOWOA/data/Wang_Chen")

def solve_with_ortools(prob: Problem, time_limit_sec: int = 10):
    n = prob.num_customers
    num_nodes = n + 1
    depot = 0
    max_vehicles = 10  # upper bound on vehicles for small instance
    
    manager = pywrapcp.RoutingIndexManager(num_nodes, max_vehicles, depot)
    routing = pywrapcp.RoutingModel(manager)
    
    # Distance Callback (scaled by 1000 for integer precision)
    SCALE = 1000
    def distance_callback(from_index, to_index):
        from_node = manager.IndexToNode(from_index)
        to_node = manager.IndexToNode(to_index)
        return int(round(prob.distance[from_node][to_node] * SCALE))
        
    transit_callback_index = routing.RegisterTransitCallback(distance_callback)
    routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)
    
    # Add Fixed Vehicle Cost (to minimize number of vehicles as primary objective)
    VEHICLE_FIXED_COST = 2000 * SCALE
    for v in range(max_vehicles):
        routing.SetFixedCostOfVehicle(VEHICLE_FIXED_COST, v)
        
    # Time Window Dimension
    def time_callback(from_index, to_index):
        from_node = manager.IndexToNode(from_index)
        to_node = manager.IndexToNode(to_index)
        service = prob.service_time[from_node]
        transit = prob.travel_time[from_node][to_node]
        return int(round((service + transit) * SCALE))
        
    time_callback_index = routing.RegisterTransitCallback(time_callback)
    routing.AddDimension(
        time_callback_index,
        int(prob.due_time[0] * SCALE),  # allow waiting
        int(prob.due_time[0] * SCALE),  # maximum travel time
        False,  # don't force start cumul to zero
        "Time"
    )
    time_dimension = routing.GetDimensionOrDie("Time")
    for i in range(num_nodes):
        index = manager.NodeToIndex(i)
        time_dimension.CumulVar(index).SetRange(
            int(round(prob.ready_time[i] * SCALE)),
            int(round(prob.due_time[i] * SCALE))
        )
        
    # Demand & Capacity Constraints:
    # Net change at node i: net_change_i = pickup_i - delivery_i
    # Also sum of delivery <= Q, sum of pickup <= Q
    CAP_SCALE = 100
    def net_demand_callback(from_index):
        node = manager.IndexToNode(from_index)
        if node == 0:
            return 0
        return int(round((prob.pickup[node] - prob.delivery[node]) * CAP_SCALE))
        
    demand_callback_index = routing.RegisterUnaryTransitCallback(net_demand_callback)
    routing.AddDimension(
        demand_callback_index,
        0,  # null capacity slack
        int(prob.capacity * CAP_SCALE),
        True,  # start cumul to zero
        "NetLoad"
    )
    
    # Delivery capacity bound
    def delivery_callback(from_index):
        node = manager.IndexToNode(from_index)
        return int(round(prob.delivery[node] * CAP_SCALE))
        
    deliv_callback_index = routing.RegisterUnaryTransitCallback(delivery_callback)
    routing.AddDimension(
        deliv_callback_index,
        0,
        int(prob.capacity * CAP_SCALE),
        True,
        "Delivery"
    )
    
    # Search parameters
    search_parameters = pywrapcp.DefaultRoutingSearchParameters()
    search_parameters.first_solution_strategy = (
        routing_enums_pb2.FirstSolutionStrategy.PARALLEL_CHEAPEST_INSERTION
    )
    search_parameters.local_search_metaheuristic = (
        routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    )
    search_parameters.time_limit.seconds = time_limit_sec
    
    solution = routing.SolveWithParameters(search_parameters)
    
    if not solution:
        return None
        
    # Extract OR-Tools routes
    routes = []
    total_distance = 0.0
    for v in range(max_vehicles):
        index = routing.Start(v)
        route = []
        while not routing.IsEnd(index):
            node = manager.IndexToNode(index)
            if node != 0:
                route.append(node)
            prev_index = index
            index = solution.Value(routing.NextVar(index))
            total_distance += prob.distance[manager.IndexToNode(prev_index)][manager.IndexToNode(index)]
        if route:
            routes.append(route)
            
    return {
        "nv": len(routes),
        "distance": total_distance,
        "routes": routes
    }

def run_ortools_cross_validation():
    print("=" * 80)
    print("MODULE 3: OR-TOOLS CROSS-VALIDATION ON VRPSPDTW")
    print("=" * 80)
    
    instances = ["RCdp1001.txt", "RCdp1004.txt", "RCdp1007.txt"]
    for fname in instances:
        fpath = DATA_DIR / fname
        prob = Problem.load(fpath)
        
        # 1. OR-Tools Solution
        ortools_res = solve_with_ortools(prob, time_limit_sec=5)
        
        # 2. PH-SHOWOA Canonical Solution
        cfg = SolverConfig(pop_size=20, max_iter=50, seed=42)
        solver = PHSHOWOASolver(prob, cfg)
        ph_res = solver.solve(run_index=1)
        
        print(f"\n--- Instance: {prob.name} (N={prob.num_customers}) ---")
        if ortools_res:
            print(f"  [OR-Tools]   : NV = {ortools_res['nv']:2d} vehicles | TD = {ortools_res['distance']:8.2f}")
        else:
            print("  [OR-Tools]   : No solution found within time limit")
        print(f"  [PH-SHOWOA]  : NV = {ph_res.nv:2d} vehicles | TD = {ph_res.td:8.2f} (Feasible: {ph_res.feasible})")
        
        if ortools_res:
            diff_nv = ph_res.nv - ortools_res['nv']
            diff_td = ph_res.td - ortools_res['distance']
            print(f"  [Comparison] : Delta NV = {diff_nv:+d} | Delta TD = {diff_td:+.2f}")

if __name__ == "__main__":
    run_ortools_cross_validation()
