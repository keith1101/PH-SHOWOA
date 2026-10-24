import csv
from collections import defaultdict

def main():
    with open('outputs/canonical_best_solutions_summary.csv', 'r', encoding='utf-8') as f:
        rows = list(csv.DictReader(f))

    print("Total instances:", len(rows))
    feasible_cnt = sum(1 for r in rows if r['is_feasible'] == 'True')
    print("Feasible count:", feasible_cnt)

    diff_nv_lt = sum(1 for r in rows if int(r['diff_NV']) < 0)
    diff_nv_eq = sum(1 for r in rows if int(r['diff_NV']) == 0)
    diff_nv_gt = sum(1 for r in rows if int(r['diff_NV']) > 0)
    print(f"NV comparison: Better NV (diff_NV < 0): {diff_nv_lt}, Equal NV: {diff_nv_eq}, Worse NV: {diff_nv_gt}")

    cost_lt = sum(1 for r in rows if float(r['gap_cost_pct']) < 0)
    cost_eq = sum(1 for r in rows if float(r['gap_cost_pct']) == 0)
    cost_gt = sum(1 for r in rows if float(r['gap_cost_pct']) > 0)
    print(f"Cost comparison: Better cost (gap < 0): {cost_lt}, Equal: {cost_eq}, Worse cost (gap > 0): {cost_gt}")

    td_lt = sum(1 for r in rows if float(r['gap_TD_pct']) < 0)
    td_gt = sum(1 for r in rows if float(r['gap_TD_pct']) > 0)
    print(f"TD comparison: Shorter TD (gap < 0): {td_lt}, Longer TD (gap > 0): {td_gt}")

    overall_avg_td = sum(float(r['gap_TD_pct']) for r in rows) / len(rows)
    overall_avg_cost = sum(float(r['gap_cost_pct']) for r in rows) / len(rows)
    print(f"Overall average gap TD%: {overall_avg_td:.2f}%")
    print(f"Overall average gap Cost%: {overall_avg_cost:.2f}%")

    cats = defaultdict(list)
    for r in rows:
        cats[r['category']].append(r)

    print("\n" + "=" * 95)
    print(f"{'Category':<32} | {'N':<3} | {'NV<0':<4} | {'NV=0':<4} | {'NV>0':<4} | {'Avg gap TD%':<12} | {'Avg gap Cost%':<14} | {'Cost Better':<11}")
    print("-" * 95)
    for cat, items in cats.items():
        n = len(items)
        nv_lt = sum(1 for r in items if int(r['diff_NV']) < 0)
        nv_eq = sum(1 for r in items if int(r['diff_NV']) == 0)
        nv_gt = sum(1 for r in items if int(r['diff_NV']) > 0)
        avg_td = sum(float(r['gap_TD_pct']) for r in items) / n
        avg_cost = sum(float(r['gap_cost_pct']) for r in items) / n
        c_better = sum(1 for r in items if float(r['gap_cost_pct']) < 0)
        print(f"{cat:<32} | {n:<3} | {nv_lt:<4} | {nv_eq:<4} | {nv_gt:<4} | {avg_td:>11.2f}% | {avg_cost:>13.2f}% | {c_better}/{n}")
    print("=" * 95)

    # Breakdown by table (Table 3, 4, 5)
    print("\nBreakdown by Table in Paper:")
    tables = defaultdict(list)
    for r in rows:
        tables[r['table']].append(r)
    for tbl, items in sorted(tables.items()):
        n = len(items)
        nv_lt = sum(1 for r in items if int(r['diff_NV']) < 0)
        nv_eq = sum(1 for r in items if int(r['diff_NV']) == 0)
        nv_gt = sum(1 for r in items if int(r['diff_NV']) > 0)
        avg_td = sum(float(r['gap_TD_pct']) for r in items) / n
        avg_cost = sum(float(r['gap_cost_pct']) for r in items) / n
        c_better = sum(1 for r in items if float(r['gap_cost_pct']) < 0)
        print(f"Table {tbl} (N={n}): NV<0: {nv_lt}, NV=0: {nv_eq}, NV>0: {nv_gt} | Avg TD Gap: {avg_td:.2f}% | Avg Cost Gap: {avg_cost:.2f}% | Cost Better: {c_better}/{n}")

    # Let's inspect timing from ph_showoa_canonical_results.csv
    try:
        with open('outputs/ph_showoa_canonical_results.csv', 'r', encoding='utf-8') as f:
            runs = list(csv.DictReader(f))
        print(f"\nTotal runs in log: {len(runs)}")
        feasible_runs = sum(1 for r in runs if r['feasible'] == 'True')
        print(f"Total feasible runs: {feasible_runs} / {len(runs)} ({feasible_runs/len(runs)*100:.2f}%)")
        times = [float(r['elapsed_seconds']) for r in runs if r.get('elapsed_seconds')]
        if times:
            print(f"Elapsed seconds per run: Min={min(times):.2f}s, Max={max(times):.2f}s, Mean={sum(times)/len(times):.2f}s")
            # By category timing
            cat_times = defaultdict(list)
            inst_to_cat = {r['instance']: r['category'] for r in rows}
            for r in runs:
                c = inst_to_cat.get(r['instance'], 'Unknown')
                if r.get('elapsed_seconds'):
                    cat_times[c].append(float(r['elapsed_seconds']))
            print("\nMean Runtime per run (seconds) by Category:")
            for c, t_list in cat_times.items():
                print(f"  {c:<32}: Mean = {sum(t_list)/len(t_list):.2f}s, Min = {min(t_list):.2f}s, Max = {max(t_list):.2f}s")
    except Exception as e:
        print("Error reading runs:", e)

if __name__ == '__main__':
    main()
