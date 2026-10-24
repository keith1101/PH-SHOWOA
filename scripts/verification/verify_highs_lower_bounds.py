import sys
from pathlib import Path
import highspy
import numpy as np

sys.path.insert(0, "D:/Project/PH-SHOWOA/src_canonical")
from problem import Problem

DATA_DIR = Path("D:/Project/PH-SHOWOA/data/Wang_Chen")

def compute_clique_lower_bound_highs(prob: Problem):
    n = prob.num_customers
    Q = prob.capacity
    
    # 1. Build Conflict Graph G = (V, E)
    # Edge (i, j) exists if i and j CANNOT be on the same vehicle route
    incompatible_pairs = set()
    compatible_pairs = []
    
    for i in range(1, n + 1):
        for j in range(i + 1, n + 1):
            is_incompatible = False
            
            # Check Capacity bounds
            if prob.delivery[i] + prob.delivery[j] > Q + 1e-6:
                is_incompatible = True
            elif prob.pickup[i] + prob.pickup[j] > Q + 1e-6:
                is_incompatible = True
            else:
                # Check Time Window Incompatibility
                # Can i precede j? (at depot -> i -> j -> depot)
                earliest_j = max(prob.ready_time[0] + prob.travel_time[0][i], prob.ready_time[i]) + prob.service_time[i] + prob.travel_time[i][j]
                can_i_then_j = (earliest_j <= prob.due_time[j]) and (earliest_j + prob.service_time[j] + prob.travel_time[j][0] <= prob.due_time[0])
                
                # Can j precede i? (at depot -> j -> i -> depot)
                earliest_i = max(prob.ready_time[0] + prob.travel_time[0][j], prob.ready_time[j]) + prob.service_time[j] + prob.travel_time[j][i]
                can_j_then_i = (earliest_i <= prob.due_time[i]) and (earliest_i + prob.service_time[i] + prob.travel_time[i][0] <= prob.due_time[0])
                
                if not can_i_then_j and not can_j_then_i:
                    is_incompatible = True
            
            if is_incompatible:
                incompatible_pairs.add((i, j))
            else:
                compatible_pairs.append((i, j))
                
    # 2. Formulate Maximum Clique Problem using HiGHS
    # Maximum Clique in G is Maximum Independent Set in complement graph G_bar
    # Max sum x_i
    # s.t. x_i + x_j <= 1 for all (i, j) in compatible_pairs
    # x_i in {0, 1}
    h = highspy.Highs()
    h.setOptionValue("output_flag", False)
    
    # Add n binary variables
    # In Highs: addVars(num_vars, lower_bounds, upper_bounds)
    inf = highspy.kHighsInf
    h.addVars(n, np.zeros(n), np.ones(n))
    for i in range(n):
        h.changeColIntegrality(i, highspy.HighsVarType.kInteger)
        h.changeColCost(i, 1.0) # Maximization cost
    
    h.changeObjectiveSense(highspy.ObjSense.kMaximize)
    
    # Add constraints: for every compatible pair (u, v), x_{u-1} + x_{v-1} <= 1
    # Note: indices in Highs are 0-based
    for u, v in compatible_pairs:
        h.addRow(0.0, 1.0, 2, np.array([u - 1, v - 1], dtype=np.int32), np.array([1.0, 1.0]))
        
    h.run()
    
    clique_size = int(round(h.getObjectiveValue()))
    
    # 3. Bin Packing Lower Bounds
    sum_del = sum(prob.delivery[1:])
    sum_pick = sum(prob.pickup[1:])
    nv_bpp_del = int(np.ceil(sum_del / Q))
    nv_bpp_pick = int(np.ceil(sum_pick / Q))
    nv_bpp = max(nv_bpp_del, nv_bpp_pick)
    
    combined_lb = max(clique_size, nv_bpp)
    
    return {
        "instance": prob.name,
        "n_cust": n,
        "clique_lb": clique_size,
        "bpp_del_lb": nv_bpp_del,
        "bpp_pick_lb": nv_bpp_pick,
        "combined_nv_lb": combined_lb
    }

def run_highs_verification():
    print("=" * 80)
    print("MODULE 2: HIGHS (highspy) THEORETICAL LOWER BOUNDS (RULE 5.1 COMPLIANCE)")
    print("=" * 80)
    
    test_files = [
        "RCdp1001.txt", "RCdp1004.txt", "RCdp1007.txt",
        "RCdp2501.txt", "RCdp2504.txt", "RCdp2507.txt",
        "RCdp5001.txt", "RCdp5004.txt", "RCdp5007.txt",
        "RCdp101.txt", "Cdp101.txt", "Rdp101.txt"
    ]
    
    results = []
    for fname in test_files:
        fpath = DATA_DIR / fname
        if not fpath.exists():
            continue
        prob = Problem.load(fpath)
        lb_info = compute_clique_lower_bound_highs(prob)
        results.append(lb_info)
        print(f"Instance: {lb_info['instance']:10s} (N={lb_info['n_cust']:3d}) | "
              f"Clique Incompatibility LB: {lb_info['clique_lb']:2d} vehicles | "
              f"BPP LB: {max(lb_info['bpp_del_lb'], lb_info['bpp_pick_lb']):2d} | "
              f"==> COMBINED THEORETICAL LB: NV >= {lb_info['combined_nv_lb']:2d}")

if __name__ == "__main__":
    run_highs_verification()
