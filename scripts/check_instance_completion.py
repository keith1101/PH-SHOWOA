import re
from pathlib import Path
from collections import defaultdict

PROJECT = Path("D:/Project/PH-SHOWOA")
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

def check():
    scan_dirs = [
        PROJECT / "tmp" / "pop32-completed",
        PROJECT / "tmp" / "pop30_completed",
        PROJECT / "tmp" / "pop32-logs",
        PROJECT / "outputs",
        KAGGLE_OUT
    ]

    files = []
    for d in scan_dirs:
        if d.exists():
            for f in d.rglob("*"):
                if f.is_file() and f.suffix in [".log", ".txt", ".out"]:
                    files.append(f)

    target_map = {t.lower(): t for t in SHEET_INSTANCES}
    job_re = re.compile(r"ph-showoa-pop\d+-([^-]+)-s(\d+)-n(\d+)", re.IGNORECASE)
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
        curr_seed = int(nm.group(2)) if nm else None
            
        for line in content.splitlines():
            sm = seed_re.search(line)
            if sm and ("run " in line or "seed=" in line):
                curr_seed = int(sm.group(1))
                
            dm = done_re.search(line)
            if dm and curr_seed is not None:
                records[canonical][curr_seed] = True
                if not nm:
                    curr_seed = None
                continue
                
            dm2 = done_sec_re.search(line)
            if dm2 and curr_seed is not None:
                records[canonical][curr_seed] = True
                if not nm:
                    curr_seed = None

    missing = []
    partial = []
    complete = []

    for inst in SHEET_INSTANCES:
        cnt = len(records[inst])
        if cnt == 0:
            missing.append((inst, cnt))
        elif cnt < 30:
            partial.append((inst, cnt))
        else:
            complete.append((inst, cnt))

    print(f"Total instances: {len(SHEET_INSTANCES)}")
    print(f"Complete (>=30 runs): {len(complete)}")
    print(f"Partial (1-29 runs): {len(partial)} -> {[f'{i}:{c}' for i, c in partial]}")
    print(f"Missing (0 runs): {len(missing)} -> {[i for i, _ in missing]}")

if __name__ == "__main__":
    check()
