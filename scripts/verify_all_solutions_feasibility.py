import sys
import math
from pathlib import Path
import re

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.audit_instances_and_bounds import parse_vrpsdptw

DATA_ROOT = Path("D:/Project/PH-SHOWOA/data/Wang_Chen")
KAGGLE_OUT = Path("D:/Project/Kaggle/output")

SHEET_INSTANCES = [
    "RCdp1001", "RCdp1004", "RCdp1007",
    "RCdp2501", "RCdp2504", "RCdp2507",
    "RCdp5001", "RCdp5004", "RCdp5007",
    "RCdp101", "RCdp102", "RCdp103", "RCdp104", "RCdp105", "RCdp106", "RCdp107", "RCdp108",
    "RCdp201", "RCdp202", "RCdp203", "RCdp204", "RCdp205", "RCdp206", "RCdp207", "RCdp208",
    "Cdp101", "Cdp102", "Cdp103", "Cdp104", "Cdp105", "Cdp106", "Cdp107", "Cdp108", "Cdp109",
    "Cdp201", "Cdp202", "Cdp203", "Cdp204", "Cdp205", "Cdp206", "Cdp207", "Cdp208",
    "Rdp101", "Rdp102", "Rdp103", "Rdp104", "Rdp105", "Rdp106", "Rdp107", "Rdp108", "Rdp109", "Rdp110", "Rdp111", "Rdp112",
    "Rdp201", "Rdp202", "Rdp203", "Rdp204", "Rdp205", "Rdp206", "Rdp207", "Rdp208", "Rdp209", "Rdp210", "Rdp211"
]

def verify_route(nl, capacity, node_dict, dist_dict):
    if len(nl) < 2 or nl[0] != 0 or nl[-1] != 0:
        return False, "Invalid depot endpoints"
    if len(nl) == 2:
        return True, "Empty route"
        
    initial_load = sum(node_dict[node]["d"] for node in nl[1:-1])
    if initial_load > capacity + 1e-4:
        return False, f"Initial load {initial_load} > capacity {capacity}"
        
    curr_load = initial_load
    curr_time = node_dict[0]["rt"]
    prev = 0
    
    for node in nl[1:-1]:
        d_val = dist_dict.get((prev, node), 0.0)
        curr_time += d_val
        due = node_dict[node]["dt"]
        if curr_time > due + 1e-4:
            return False, f"TW violation at node {node}: arr {curr_time:.2f} > due {due}"
        curr_time = max(curr_time, node_dict[node]["rt"]) + node_dict[node]["st"]
        curr_load = curr_load - node_dict[node]["d"] + node_dict[node]["p"]
        if curr_load > capacity + 1e-4 or curr_load < -1e-4:
            return False, f"Capacity violation at node {node}: load {curr_load:.2f}"
        prev = node
        
    # Return to depot
    curr_time += dist_dict.get((prev, 0), 0.0)
    depot_due = node_dict[0]["dt"]
    if curr_time > depot_due + 1e-4:
        return False, f"Depot return TW violation: arr {curr_time:.2f} > due {depot_due}"
        
    return True, "OK"

def main():
    total_solutions_checked = 0
    total_routes_checked = 0
    violations = []
    instances_checked = 0

    all_kaggle_subdirs = [d for d in KAGGLE_OUT.iterdir() if d.is_dir()]

    for inst in SHEET_INSTANCES:
        prob_path = None
        for cand in [
            DATA_ROOT / f"explicit_{inst.lower()}.vrpsdptw",
            DATA_ROOT / f"{inst.lower()}.vrpsdptw",
            DATA_ROOT / f"{inst}.vrpsdptw"
        ]:
            if cand.exists():
                prob_path = cand
                break
                
        if not prob_path:
            for cand in DATA_ROOT.glob(f"*{inst.lower()}*"):
                prob_path = cand
                break
                
        if not prob_path or not prob_path.exists():
            print(f"Warning: problem file for {inst} not found!")
            continue

        capacity, nodes, dist = parse_vrpsdptw(prob_path)
        node_dict = {n["id"]: n for n in nodes}
        
        # Locate matching directories (case-insensitive)
        inst_dirs = [d for d in all_kaggle_subdirs if d.name.lower() == inst.lower() or d.name.lower().startswith(inst.lower() + "_")]
        sols = []
        for d in inst_dirs:
            for sf in d.rglob("best_solution.txt"):
                sols.append(sf)
            for sf in d.rglob("solution.txt"):
                sols.append(sf)
                
        sols = list(set(sols))
        inst_has_sol = False
        
        for sf in sols:
            content = sf.read_text(encoding="utf-8", errors="ignore")
            routes = []
            for line in content.splitlines():
                line = line.strip()
                if not line:
                    continue
                if "nodes:" in line:
                    r_part = line.split("nodes:", 1)[1]
                    nodes_in_r = [int(x) for x in re.findall(r"\b\d+\b", r_part)]
                    if len(nodes_in_r) >= 2 and nodes_in_r[0] == 0 and nodes_in_r[-1] == 0:
                        routes.append(nodes_in_r)
                elif line.startswith("Route") and ":" in line:
                    r_part = line.split(":", 1)[1]
                    nodes_in_r = [int(x) for x in re.findall(r"\b\d+\b", r_part)]
                    if len(nodes_in_r) >= 2 and nodes_in_r[0] == 0 and nodes_in_r[-1] == 0:
                        routes.append(nodes_in_r)
                elif line.startswith("[") and line.endswith("]"):
                    nodes_in_r = [int(x) for x in re.findall(r"\b\d+\b", line)]
                    if len(nodes_in_r) >= 2 and nodes_in_r[0] == 0 and nodes_in_r[-1] == 0:
                        routes.append(nodes_in_r)
                        
            if routes:
                inst_has_sol = True
                total_solutions_checked += 1
                for r in routes:
                    total_routes_checked += 1
                    ok, reason = verify_route(r, capacity, node_dict, dist)
                    if not ok:
                        violations.append((inst, str(sf), reason))
                        
        if inst_has_sol:
            instances_checked += 1

    print("=== FEASIBILITY VERIFICATION AUDIT ===")
    print(f"Total instances checked: {instances_checked}/65")
    print(f"Total solutions checked: {total_solutions_checked}")
    print(f"Total individual routes checked: {total_routes_checked}")
    print(f"Total violations found: {len(violations)}")
    if len(violations) == 0 and instances_checked == 65:
        print(">>> RESULT: 100% FEASIBLE! ALL VEHICLE CAPACITY & CUSTOMER TIME WINDOW CONSTRAINTS SATISFIED! <<<")
    else:
        for v in violations[:10]:
            print("Violation:", v)

if __name__ == "__main__":
    main()
