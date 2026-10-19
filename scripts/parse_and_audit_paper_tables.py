import re
import csv
from pathlib import Path

def parse_markdown_table(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Pattern for Table 3, 4, 5
    tables = {}
    for table_num in [3, 4, 5]:
        pattern = rf"\*\*Table {table_num}\..*?\*\*\s*```text\s*(.*?)\s*```"
        match = re.search(pattern, content, re.DOTALL)
        if match:
            tables[table_num] = match.group(1).strip()
            
    return tables

def parse_table_lines(table_text):
    rows = []
    lines = table_text.split('\n')
    header_found = False
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if line.startswith('Instance') or line.startswith('NV') or line.startswith('---'):
            continue
            
        parts = re.split(r'\s+', line)
        if len(parts) >= 6 and (parts[0].startswith('RCdp') or parts[0].startswith('Rdp') or parts[0].startswith('Cdp')):
            # Row format varies slightly
            rows.append(parts)
    return rows

def analyze_all_tables():
    paper_path = Path('.agents/PH-SHOWOA_markdown/PH-SHOWOA_2026.md')
    tables = parse_markdown_table(paper_path)
    
    print("=== AUDIT OF ALL TABLES (3, 4, 5) IN THE PUBLISHED PAPER ===\n")
    
    # 1. Check Table 3
    print("--- Table 3: Small WC Instances ---")
    t3_lines = tables[3].split('\n')
    for line in t3_lines[2:]:
        if not line.strip() or line.startswith('Instance'): continue
        p = re.split(r'\s+', line.strip())
        if len(p) >= 11:
            inst = p[0]
            size = p[1]
            sho_nv, sho_td = int(p[2]), float(p[3])
            woa_nv, woa_td = int(p[5]), float(p[6])
            ph_nv, ph_td = int(p[8]), float(p[9])
            
            # Anomalies:
            notes = []
            if sho_nv < ph_nv:
                notes.append(f"SHO has FEWER vehicles ({sho_nv} < {ph_nv})! Cost difference: SHO wins by {2000*(ph_nv - sho_nv) + (ph_td - sho_td):.2f}")
            if woa_nv < ph_nv:
                notes.append(f"WOA has FEWER vehicles ({woa_nv} < {ph_nv})! Cost difference: WOA wins by {2000*(ph_nv - woa_nv) + (ph_td - woa_td):.2f}")
            if inst == 'RCdp1001' and sho_nv == 2:
                notes.append("MATHEMATICALLY IMPOSSIBLE (2 veh cannot cover RCdp1001)")
                
            status = " [SUSPICIOUS]" if notes else " [OK]"
            print(f"{inst:<10} Size={size:<3} SHO:({sho_nv}, {sho_td:.2f}) WOA:({woa_nv}, {woa_td:.2f}) PH:({ph_nv}, {ph_td:.2f}){status}")
            for n in notes:
                print(f"   -> {n}")

    # 2. Check Table 4
    print("\n--- Table 4: Type 1 WC Instances (100 customers) ---")
    t4_lines = tables[4].split('\n')
    td_values = {}
    for line in t4_lines:
        line = line.strip()
        if not line or line.startswith('Instance') or line.startswith('NV'): continue
        p = re.split(r'\s+', line)
        if len(p) >= 8 and (p[0].startswith('Rdp') or p[0].startswith('Cdp') or p[0].startswith('RCdp')):
            inst = p[0]
            size = p[1]
            sho_nv, sho_td = int(p[2]), float(p[3])
            woa_nv, woa_td = int(p[4]), float(p[5])
            ph_nv, ph_td = int(p[6]), float(p[7])
            
            notes = []
            if ph_td in td_values:
                notes.append(f"DUPLICATE TD! Identical to {td_values[ph_td]} (TD={ph_td})")
            td_values[ph_td] = inst
            
            if sho_nv < ph_nv:
                notes.append(f"SHO has fewer vehicles ({sho_nv} < {ph_nv})")
            if woa_nv < ph_nv:
                notes.append(f"WOA has fewer vehicles ({woa_nv} < {ph_nv})")
                
            # Check if SHO had better TD with same NV
            if sho_nv == ph_nv and sho_td < ph_td:
                gap = (ph_td - sho_td) / sho_td * 100
                notes.append(f"SHO has SHORTER distance with same NV! ({sho_td:.2f} vs {ph_td:.2f}, +{gap:.2f}% worse in PH-SHOWOA)")
                
            status = " [SUSPICIOUS]" if notes else ""
            if status:
                print(f"{inst:<10} SHO:({sho_nv}, {sho_td:.2f}) WOA:({woa_nv}, {woa_td:.2f}) PH:({ph_nv}, {ph_td:.2f}){status}")
                for n in notes:
                    print(f"   -> {n}")

    # 3. Check Table 5
    print("\n--- Table 5: Type 2 WC Instances (100 customers) ---")
    t5_lines = tables[5].split('\n')
    for line in t5_lines:
        line = line.strip()
        if not line or line.startswith('Instance') or line.startswith('NV'): continue
        p = re.split(r'\s+', line)
        if len(p) >= 8 and (p[0].startswith('Rdp') or p[0].startswith('Cdp') or p[0].startswith('RCdp')):
            inst = p[0]
            size = p[1]
            sho_nv, sho_td = int(p[2]), float(p[3])
            woa_nv, woa_td = int(p[4]), float(p[5])
            ph_nv, ph_td = int(p[6]), float(p[7])
            
            notes = []
            if sho_nv < ph_nv:
                notes.append(f"SHO has fewer vehicles ({sho_nv} < {ph_nv})")
            if woa_nv < ph_nv:
                notes.append(f"WOA has fewer vehicles ({woa_nv} < {ph_nv})")
            if sho_nv == ph_nv and sho_td < ph_td:
                gap = (ph_td - sho_td) / sho_td * 100
                notes.append(f"SHO has SHORTER distance with same NV! ({sho_td:.2f} vs {ph_td:.2f}, +{gap:.2f}% worse in PH-SHOWOA)")
                
            if notes:
                print(f"{inst:<10} SHO:({sho_nv}, {sho_td:.2f}) WOA:({woa_nv}, {woa_td:.2f}) PH:({ph_nv}, {ph_td:.2f}) [SUSPICIOUS]")
                for n in notes:
                    print(f"   -> {n}")

if __name__ == '__main__':
    analyze_all_tables()
