import csv
from collections import defaultdict

def main():
    with open('outputs/canonical_best_solutions_summary.csv', 'r', encoding='utf-8') as f:
        rows = list(csv.DictReader(f))

    cats = defaultdict(list)
    for r in rows:
        cats[r['category']].append(r)

    for cat_name, items in cats.items():
        print(f"### Category: {cat_name} (N={len(items)})")
        print("| Instance | Paper NV | Paper TD | Paper Cost | Canon NV | Canon TD | Canon Cost | diff_NV | gap_TD (%) | gap_Cost (%) | Status |")
        print("| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |")
        for r in items:
            diff_nv = int(r['diff_NV'])
            gap_td = float(r['gap_TD_pct'])
            gap_cost = float(r['gap_cost_pct'])
            p_nv = int(r['paper_NV'])
            p_td = float(r['paper_TD'])
            p_cost = float(r['paper_cost'])
            c_nv = int(r['canon_NV'])
            c_td = float(r['canon_TD'])
            c_cost = float(r['canon_cost'])

            if diff_nv < 0:
                status = f"FEWER_VEHICLES ({diff_nv})"
            elif diff_nv == 0 and gap_td <= 0:
                status = "BEAT_TD"
            elif diff_nv == 0:
                status = "EQUAL_VEHICLES"
            else:
                status = f"MORE_VEHICLES (+{diff_nv})"

            print(f"| {r['instance']} | {p_nv} | {p_td:.2f} | {p_cost:.2f} | {c_nv} | {c_td:.2f} | {c_cost:.2f} | {diff_nv:+d} | {gap_td:+.2f}% | {gap_cost:+.2f}% | {status} |")
        print()

if __name__ == '__main__':
    main()
