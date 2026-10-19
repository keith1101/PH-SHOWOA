import re
import os
import json
import subprocess
import statistics
from pathlib import Path
from collections import defaultdict

SPREADSHEET_ID = "1q498GxIhgMLg38hN44w-hWStl89EsSNDBHOp5Ksd2rA"
SHEET_NAME = "Python_rerun_popsize30"

PROJECT = Path("D:/Project/PH-SHOWOA")
KAGGLE_OUT = Path("D:/Project/Kaggle/output")

# The exact 65 instances as ordered in the Google Sheet (Rows 3 to 67):
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

import datetime

CUTOFF_DATE = datetime.datetime(2026, 10, 12, 0, 0, 0)

def parse_all_runs():
    scan_dirs = [
        KAGGLE_OUT
    ]
    
    files = []
    for d in scan_dirs:
        if d.exists():
            for f in d.rglob("*"):
                if f.is_file() and f.suffix in [".log", ".txt", ".out"]:
                    try:
                        mtime = datetime.datetime.fromtimestamp(f.stat().st_mtime)
                        if mtime >= CUTOFF_DATE:
                            files.append(f)
                    except Exception:
                        pass
                    
    print(f"Scanning {len(files)} log files (executed on/after {CUTOFF_DATE.strftime('%Y-%m-%d')})...")
    target_map = {t.lower(): t for t in SHEET_INSTANCES}
    
    job_re = re.compile(r"ph-showoa-(?:pop\d+|w\d+|supp|new)-([^-]+)-s(\d+)-n(\d+)", re.IGNORECASE)
    inst_start_re = re.compile(r"\[\d+/\d+\]\s+([A-Za-z0-9_]+):\s+start", re.IGNORECASE)
    inst_cmd_re = re.compile(r"--instances\s+([A-Za-z0-9_]+)", re.IGNORECASE)
    inst_log_name_re = re.compile(r"^([A-Za-z0-9_]+)_seed_(\d+)\.log", re.IGNORECASE)
    
    seed_re = re.compile(r"seed=(\d+)")
    done_re = re.compile(r"done in\s+([0-9:]+)\s+\|\s+NV=([\d.]+)\s+TD=([\d.]+)")
    done_sec_re = re.compile(r"done in\s+([\d.]+)s\s+\|\s+NV=([\d.]+)\s+TD=([\d.]+)")
    
    records = defaultdict(dict)
    
    for f in files:
        try:
            content = f.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
            
        if "done in" not in content:
            continue
            
        inst = None
        nm = inst_log_name_re.match(f.name)
        if nm:
            inst = nm.group(1)
        else:
            jm = job_re.search(str(f)) or job_re.search(content)
            if jm:
                inst = jm.group(1)
            else:
                sm = inst_start_re.search(content) or inst_cmd_re.search(content)
                if sm:
                    inst = sm.group(1)
                else:
                    for t in SHEET_INSTANCES:
                        if f"/{t}/" in str(f).replace("\\", "/") or f"/{t.lower()}/" in str(f).replace("\\", "/"):
                            inst = t
                            break
                            
        if not inst or inst.lower() not in target_map:
            continue
            
        canonical = target_map[inst.lower()]
        
        curr_seed = None
        if nm:
            curr_seed = int(nm.group(2))
            
        for line in content.splitlines():
            sm = seed_re.search(line)
            if sm and ("run " in line or "seed=" in line):
                curr_seed = int(sm.group(1))
                
            dm = done_re.search(line)
            if dm and curr_seed is not None:
                d_str, nv_str, td_str = dm.groups()
                parts = d_str.split(":")
                if len(parts) == 3:
                    sec = int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
                elif len(parts) == 2:
                    sec = int(parts[0]) * 60 + int(parts[1])
                else:
                    sec = float(parts[0])
                records[canonical][curr_seed] = (float(nv_str), float(td_str), sec)
                if not nm:
                    curr_seed = None
                continue
                
            dm2 = done_sec_re.search(line)
            if dm2 and curr_seed is not None:
                sec_str, nv_str, td_str = dm2.groups()
                records[canonical][curr_seed] = (float(nv_str), float(td_str), float(sec_str))
                if not nm:
                    curr_seed = None
                    
    # Also parse direct run.json files for maximum fidelity
    for p in KAGGLE_OUT.rglob("run.json"):
        try:
            mtime = datetime.datetime.fromtimestamp(p.stat().st_mtime)
            if mtime < CUTOFF_DATE:
                continue
            d = json.load(open(p, encoding="utf-8"))
            if "seed" in d and "vehicles" in d and "distance" in d:
                parts = p.as_posix().split("/")
                inst_cand = None
                for part in parts:
                    if part.lower() in target_map:
                        inst_cand = target_map[part.lower()]
                        break
                if inst_cand:
                    records[inst_cand][d["seed"]] = (float(d["vehicles"]), float(d["distance"]), float(d.get("duration_sec", 0)))
        except Exception:
            pass

    # Also parse direct runs.csv files for cleanly completed runs
    import csv
    for p in KAGGLE_OUT.rglob("runs.csv"):
        try:
            mtime = datetime.datetime.fromtimestamp(p.stat().st_mtime)
            if mtime < CUTOFF_DATE:
                continue
            parts = p.as_posix().split("/")
            inst_cand = None
            for part in parts:
                if part.lower() in target_map:
                    inst_cand = target_map[part.lower()]
                    break
            if not inst_cand:
                continue
            with open(p, "r", encoding="utf-8") as fp:
                reader = csv.DictReader(fp)
                for row in reader:
                    if row.get("status") == "ok":
                        s = int(row["seed"])
                        nv = float(row["vehicles"])
                        td = float(row["distance"])
                        sec = float(row.get("duration_sec", 0))
                        records[inst_cand][s] = (nv, td, sec)
        except Exception:
            pass

    return records

def format_time(sec):
    if not sec:
        return ""
    m, s = divmod(int(sec), 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h}h{m:02d}m{s:02d}s"
    elif m > 0:
        return f"{m}m{s:02d}s"
    else:
        return f"{s}s"

def update_sheet():
    records = parse_all_runs()
    
    data_matrix = []
    
    print("\nCalculated Stats mapped to Sheet Rows:")
    for idx, inst in enumerate(SHEET_INSTANCES, 1):
        row_num = idx + 2  # Row 3 to 67
        runs = records.get(inst, {})
        if runs:
            nvs = [r[0] for r in runs.values()]
            tds = [r[1] for r in runs.values()]
            sec_avg = sum(r[2] for r in runs.values()) / len(runs)
            
            # Best cost: min (2000 * NV + TD)
            best_seed = min(runs.keys(), key=lambda s: 2000.0 * runs[s][0] + runs[s][1])
            best_nv, best_td, _ = runs[best_seed]
            best_nv_str = str(int(round(best_nv)))
            best_td_str = f"{best_td:.2f}"
            
            nv_avg = statistics.mean(nvs)
            nv_min, nv_max = min(nvs), max(nvs)
            if nv_min == nv_max:
                nv_str = str(int(round(nv_avg)))
            else:
                nv_std = statistics.stdev(nvs) if len(nvs) > 1 else 0.0
                nv_str = f"{nv_avg:.2f} \u00b1 {nv_std:.2f}"
                
            td_avg = statistics.mean(tds)
            td_std = statistics.stdev(tds) if len(tds) > 1 else 0.0
            td_str = f"{td_avg:.2f} \u00b1 {td_std:.2f}"
            
            t_str = format_time(sec_avg)
            data_matrix.append([best_nv_str, best_td_str, nv_str, td_str, t_str])
            print(f"Row {row_num:<2} (STT {idx:<2}): {inst:<10} ({len(runs)} runs) -> Best=({best_nv_str}, {best_td_str}) | Avg NV={nv_str:<14} TD={td_str:<18} Time={t_str}")
        else:
            data_matrix.append(["", "", "", "", ""])
            print(f"Row {row_num:<2} (STT {idx:<2}): {inst:<10} (0 runs) -> [EMPTY]")
            
    # Prepare batch request file: Columns G, H, I, J, K
    target_range = f"'{SHEET_NAME}'!G3:K{2 + len(data_matrix)}"
    req = [
        {
            "op": "write",
            "range": target_range,
            "data": data_matrix
        }
    ]
    
    req_file = PROJECT / "tmp" / "gsheets_update_request.json"
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

if __name__ == '__main__':
    update_sheet()
