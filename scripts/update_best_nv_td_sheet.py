import json
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path("D:/Project/PH-SHOWOA")
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
from update_google_sheet_pop30 import parse_all_runs, SHEET_INSTANCES, SPREADSHEET_ID, SHEET_NAME

def update_best_columns():
    records = parse_all_runs()
    
    data_matrix = []
    print("\nExtracting Best Cost (2000*NV + TD) for each instance:")
    print(f"{'STT':<4} | {'INSTANCE':<10} | {'BEST NV':<8} | {'BEST TD':<10} | {'BEST COST':<12} | {'SEED':<6}")
    print("-" * 65)
    
    for idx, inst in enumerate(SHEET_INSTANCES, 1):
        runs = records.get(inst, {})
        if runs:
            # Best cost: min (2000 * NV + TD)
            best_seed = min(runs.keys(), key=lambda s: 2000.0 * runs[s][0] + runs[s][1])
            best_nv, best_td, best_sec = runs[best_seed]
            best_cost = 2000.0 * best_nv + best_td
            
            nv_str = str(int(round(best_nv)))
            td_str = f"{best_td:.2f}"
            data_matrix.append([nv_str, td_str])
            print(f"{idx:<4} | {inst:<10} | {nv_str:<8} | {td_str:<10} | {best_cost:<12.2f} | {best_seed:<6}")
        else:
            data_matrix.append(["", ""])
            print(f"{idx:<4} | {inst:<10} | {'EMPTY':<8} | {'EMPTY':<10} | {'EMPTY':<12} | -")
            
    # Target range: Best_NV is Col G, Best_TD is Col H (Row 3 to 67)
    target_range = f"'{SHEET_NAME}'!G3:H{2 + len(data_matrix)}"
    req = [
        {
            "op": "write",
            "range": target_range,
            "data": data_matrix
        }
    ]
    
    req_file = PROJECT_ROOT / "tmp" / "gsheets_update_best_nv_td.json"
    req_file.parent.mkdir(parents=True, exist_ok=True)
    with open(req_file, "w", encoding="utf-8") as fp:
        json.dump(req, fp, indent=2, ensure_ascii=False)
        
    print(f"\nSaved batch update request to {req_file}")
    print(f"Total rows to write: {len(data_matrix)} to {target_range}")
    
    GSHEETS_CMD = r"C:\Users\LENOVO\.gemini\config\plugins\gsheets\skills\gsheets\scripts\gsheets.cmd"
    cmd = [
        GSHEETS_CMD, "mutate", "batch",
        SPREADSHEET_ID,
        "-f", str(req_file)
    ]
    print(f"Running command: {' '.join(cmd)}")
    res = subprocess.run(cmd, capture_output=True, text=True, shell=True)
    print(f"Exit code: {res.returncode}")
    print(f"STDOUT:\n{res.stdout}")
    print(f"STDERR:\n{res.stderr}")

if __name__ == "__main__":
    update_best_columns()
