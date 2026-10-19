import csv
import math
from pathlib import Path

def parse_vrpsdptw(path):
    with open(path, 'r') as f:
        lines = f.readlines()
        
    capacity = 200.0
    nodes = []
    dist = {}
    reading_nodes = False
    reading_dist = False
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if line.startswith('CAPACITY'):
            parts = line.split(':')
            if len(parts) > 1:
                capacity = float(parts[1].strip())
        elif line == 'NODE_SECTION':
            reading_nodes = True
            continue
        elif line == 'DISTANCETIME_SECTION':
            reading_nodes = False
            reading_dist = True
            continue
        elif line == 'DEPOT_SECTION':
            reading_nodes = False
            reading_dist = False
            break
            
        if reading_nodes:
            parts = [p.strip() for p in line.split(',')]
            if len(parts) >= 6:
                node = int(parts[0])
                d = float(parts[1])
                p = float(parts[2])
                rt = float(parts[3])
                dt = float(parts[4])
                st = float(parts[5])
                nodes.append({'id': node, 'd': d, 'p': p, 'rt': rt, 'dt': dt, 'st': st})
                
        if reading_dist:
            parts = [p.strip() for p in line.split(',')]
            if len(parts) >= 4:
                u = int(parts[0])
                v = int(parts[1])
                d_val = float(parts[2])
                t_val = float(parts[3])
                dist[(u, v)] = d_val
                dist[(v, u)] = d_val
                
    return capacity, nodes, dist

def max_clique_heuristic(adj, nodes):
    # Bron-Kerbosch with pivoting for maximum clique
    # To prevent exponential explosion on large instances, we add a step counter
    best_clique = []
    steps = 0
    max_steps = 500000
    
    def bron_kerbosch(r, p, x):
        nonlocal best_clique, steps
        steps += 1
        if steps > max_steps:
            if len(r) > len(best_clique):
                best_clique = list(r)
            return
        if not p and not x:
            if len(r) > len(best_clique):
                best_clique = list(r)
            return
        # Pivot selection
        u = next(iter(p | x)) if (p | x) else None
        pivot_neighbors = adj.get(u, set())
        for v in list(p - pivot_neighbors):
            v_neighbors = adj.get(v, set())
            bron_kerbosch(r | {v}, p & v_neighbors, x & v_neighbors)
            p.remove(v)
            x.add(v)
            
    # Also do greedy clique finding as baseline
    deg = sorted(nodes, key=lambda n: len(adj.get(n, set())), reverse=True)
    greedy_clique = []
    for n in deg:
        if all(other in adj.get(n, set()) for other in greedy_clique):
            greedy_clique.append(n)
    best_clique = greedy_clique[:]
    
    # Run Bron-Kerbosch
    p_set = set(nodes)
    bron_kerbosch(set(), p_set, set())
    return best_clique

def analyze_instance(row):
    inst_name = row['instance']
    path = Path(row['path'])
    if not path.exists():
        return None
        
    capacity, nodes, dist = parse_vrpsdptw(path)
    if not nodes:
        return None
        
    custs = [n for n in nodes if n['id'] != 0]
    total_d = sum(c['d'] for c in custs)
    total_p = sum(c['p'] for c in custs)
    cap_bound_d = math.ceil(total_d / capacity)
    cap_bound_p = math.ceil(total_p / capacity)
    cap_bound = max(cap_bound_d, cap_bound_p)
    
    # Pairwise incompatibility
    # u and v are incompatible if neither (u -> v) nor (v -> u) can ever be directly visited
    # In addition, check triangle inequality
    cust_ids = [c['id'] for c in custs]
    node_map = {c['id']: c for c in custs}
    depot = next((n for n in nodes if n['id'] == 0), {'rt': 0, 'dt': 240, 'st': 0})
    
    adj = {cid: set() for cid in cust_ids}
    
    for i in range(len(cust_ids)):
        u = cust_ids[i]
        cu = node_map[u]
        for j in range(i + 1, len(cust_ids)):
            v = cust_ids[j]
            cv = node_map[v]
            
            # Can u precede v?
            # Earliest departure from depot = depot['rt']
            # Earliest arrival at u = max(depot['rt'] + dist.get((0, u), 0), cu['rt'])
            # Earliest finish at u = arr_u + cu['st']
            # Earliest arrival at v = finish_u + dist.get((u, v), 0)
            arr_u = max(depot['rt'] + dist.get((0, u), 0), cu['rt'])
            arr_v_from_u = arr_u + cu['st'] + dist.get((u, v), 0)
            u_to_v_feasible = (arr_v_from_u <= cv['dt'])
            
            # Also check return to depot from v
            if u_to_v_feasible:
                arr_depot = max(arr_v_from_u, cv['rt']) + cv['st'] + dist.get((v, 0), 0)
                if arr_depot > depot['dt']:
                    u_to_v_feasible = False
                    
            # Also check capacity for pair
            if cu['d'] + cv['d'] > capacity:
                u_to_v_feasible = False
            # During delivery/pickup:
            # start load = cu['d'] + cv['d']
            # after u: start_load - cu['d'] + cu['p'] = cv['d'] + cu['p']
            # after v: cv['d'] + cu['p'] - cv['d'] + cv['p'] = cu['p'] + cv['p']
            if cv['d'] + cu['p'] > capacity or cu['p'] + cv['p'] > capacity:
                u_to_v_feasible = False
                
            # Can v precede u?
            arr_v = max(depot['rt'] + dist.get((0, v), 0), cv['rt'])
            arr_u_from_v = arr_v + cv['st'] + dist.get((v, u), 0)
            v_to_u_feasible = (arr_u_from_v <= cu['dt'])
            if v_to_u_feasible:
                arr_depot = max(arr_u_from_v, cu['rt']) + cu['st'] + dist.get((u, 0), 0)
                if arr_depot > depot['dt']:
                    v_to_u_feasible = False
            if cu['d'] + cv['d'] > capacity:
                v_to_u_feasible = False
            if cu['d'] + cv['p'] > capacity or cu['p'] + cv['p'] > capacity:
                v_to_u_feasible = False
                
            if not u_to_v_feasible and not v_to_u_feasible:
                adj[u].add(v)
                adj[v].add(u)
                
    clique = max_clique_heuristic(adj, cust_ids)
    clique_bound = len(clique)
    
    target_nv = int(row['target_vehicles'])
    target_td = float(row['target_distance'])
    table_num = row['table']
    
    lower_bound = max(cap_bound, clique_bound)
    suspicious = (target_nv < lower_bound)
    
    return {
        'instance': inst_name,
        'size': len(custs),
        'table': table_num,
        'capacity': capacity,
        'tot_d': total_d,
        'tot_p': total_p,
        'cap_bound': cap_bound,
        'clique_bound': clique_bound,
        'lower_bound': lower_bound,
        'target_nv': target_nv,
        'target_td': target_td,
        'suspicious': suspicious,
        'clique_sample': clique[:10] if len(clique) > 10 else clique
    }

def main():
    with open('tests/paper_performance_targets.csv', 'r') as f:
        targets = list(csv.DictReader(f))
        
    print(f"Auditing {len(targets)} benchmark instances...\n")
    print(f"{'Instance':<10} {'Size':<5} {'CapB':<5} {'CliqB':<6} {'LB':<4} {'TargetNV':<9} {'TargetTD':<10} {'Suspicious?'}")
    print("-" * 75)
    
    suspicious_list = []
    
    for row in targets:
        res = analyze_instance(row)
        if not res:
            continue
            
        susp = "YES (LB > NV!)" if res['suspicious'] else "No"
        if res['target_nv'] < res['lower_bound']:
            suspicious_list.append(res)
            
        print(f"{res['instance']:<10} {res['size']:<5} {res['cap_bound']:<5} {res['clique_bound']:<6} {res['lower_bound']:<4} {res['target_nv']:<9} {res['target_td']:<10.2f} {susp}")
        
    print("\n" + "=" * 75)
    print(f"Summary: Found {len(suspicious_list)} suspicious instances where Target NV < Lower Bound!")
    for s in suspicious_list:
        print(f" - {s['instance']}: Target NV = {s['target_nv']}, Lower Bound = {s['lower_bound']} (Cap={s['cap_bound']}, Clique={s['clique_bound']})")

if __name__ == '__main__':
    main()
