# Project: Kaggle Distributed Multi-Account Campaign Orchestrator & Benchmark Verifier

## Architecture
- **Distributed Remote Execution Engine**: 5 authenticated accounts (`tafuhihi`, `kanhan162`, `dautromduoicuop`, `keith1101`, `giahaohuynh`), supporting 5 concurrent kernels each (up to 25 concurrent remote kernels, 150 parallel seeds).
- **Algorithmic Core**: Kaggle dataset `keith1101/phshowoa-code` containing:
  - `src/granular_neighborhood.py`: Spatio-temporal granular neighborhood pruning.
  - `src/search_framework.py`: Active Route Elimination with Regret-2 reinsertion to eliminate redundant vehicles.
  - `--paper_flags`: SA initialization and Targeted Feasibility-Repair.
- **Harvesting & Parsing Pipeline**: Remote outputs downloaded via `kaggle kernels output` to `D:\Project\Kaggle\output\`. Logs parsed by `scripts/check_instance_completion.py` and local parsers.
- **Google Sheets Integration**: Spreadsheet ID `1q498GxIhgMLg38hN44w-hWStl89EsSNDBHOp5Ksd2rA`, tab `Python_rerun_popsize30`, rows 3–67 (Row = STT + 2), columns G (NV), H (TD), I (Avg/Run). Updated via CLI `gsheets.cmd` (`BypassSandbox: true`).
- **Benchmark Ground Truth & Verification**: `tests/paper_performance_targets.csv` (100% identical to Tables 3, 4, 5 of the published paper), in-process and post-hoc route feasibility checkers (capacity, time windows, DC closure).

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | Multi-Account Remote Kernel Monitoring | Monitor live 25 kernels across accounts tafuhihi, b, c, d, e until completion without local CPU usage | M1 | Survey |
| 2 | Automated Kernel Output Harvesting | Download completed kernel output bundles to D:\Project\Kaggle\output\ | M2 | Survey |
| 3 | Run Log Extraction & Statistical Aggregation | Extract NV, TD, runtime per seed; calculate averages and best solutions across 30 runs per instance | M2 | Survey |
| 4 | Google Sheets Tab Synchronization | Update columns G (NV), H (TD), and I (Avg/Run) for all 65 instances (rows 3–67) in tab Python_rerun_popsize30 | M2 | Survey |
| 5 | Wave 2 Partial Instance Launch & Queue Management | Prepare and launch subsequent batches for 44 partial instances (e.g., Cdp207:3, RCdp203:3, RCdp204:3, Rdp202:4) using the new solution | M3 | Survey |
| 6 | Solution Feasibility & Route Constraint Auditing | Programmatically verify 100% feasibility (capacity, time windows, and DC closure) on all harvested solutions | M4 | Survey |
| 7 | Benchmark Performance Verification Against Paper Targets | Audit NV and TD against tests/paper_performance_targets.csv and Tables 3, 4, 5, confirming NV matches or beats paper targets | M4 | Survey |

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| 1 | Remote Execution & Kernel Monitoring | Monitor 25 live kernels for Cdp202, Cdp203, Cdp205, Cdp208 across tafuhihi, kanhan162, dautromduoicuop, keith1101, giahaohuynh | none | DONE (scripts/kaggle_monitor.py, 33/33 tests passed, 20 kernels COMPLETE, 5 RUNNING) |
| 2 | Output Harvesting & Google Sheets Sync | Harvest completed outputs to D:\Project\Kaggle\output\, parse runs, update Google Sheet Python_rerun_popsize30 rows 3–67 | M1 | DONE (scripts/harvest_and_sync_sheets.py, 16/16 unit tests, 57/57 adversarial tests, Cdp203/205/208 harvested & synced, readback 100% verified) |
| 3 | Wave 2 Execution & Instance 30-Run Completion | Launch batches for 44 partial instances with new solution until all 65 instances have 30 completed runs | M2 | IN_PROGRESS (Wave 2 active: 25 kernels across 5 accounts for Cdp202, Cdp201, Cdp204, Cdp206, Cdp207) |
| 4 | Feasibility & Benchmark Paper Target Audit | Validate 100% feasibility and verify NV and TD against paper targets | M3 | PLANNED |

## Interface Contracts

### Kaggle CLI ↔ Remote Workers
- Environment: `KAGGLE_CONFIG_DIR` pointing to credential directory (`C:\Users\LENOVO\.kaggle` or `D:\Project\Kaggle\credentials\account-<x>`).
- Execution: `kaggle kernels status <owner>/<kernel-slug>` and `kaggle kernels output <owner>/<kernel-slug> -p <path>`.
- Networking: Requires `BypassSandbox: true` in PowerShell for DNS resolution to `www.kaggle.com`.

### Harvesting Parser ↔ Google Sheets CLI
- Output directory: `D:\Project\Kaggle\output\<instance>\` or `tmp/pop30_completed/<instance>_seed_<seed>.log`.
- Data structure: Matrix of 65 rows x 3 columns `[[NV, TD, Avg/Run], ...]`.
- Update command: `& "C:\Users\LENOVO\.gemini\config\plugins\gsheets\skills\gsheets\scripts\gsheets.cmd" mutate batch 1q498GxIhgMLg38hN44w-hWStl89EsSNDBHOp5Ksd2rA -f <request.json>` with `BypassSandbox: true`.

### Solution Log ↔ Feasibility & Target Auditor
- Solution format: `vehicle (route) number: <NV>`, `Total cost: <TC>`, `nodes: 0 <c1> ... 0`.
- Target comparison: Target NV and TD from `tests/paper_performance_targets.csv`.
- Invariants: Capacity $\le Q$, time window arrival $\le e_i$, depot return $\le e_{\text{DC}}$, customer coverage complete and unique.

## Code Layout
- `scripts/kaggle_run.py`: Remote kernel bootstrap script.
- `scripts/compare_with_paper_logged.py`: Experiment runner inside kernel.
- `scripts/check_instance_completion.py`: Instance completion audit script.
- `scripts/prepare_tafuhihi_job.py`: Kernel generator and submission script.
- `src/granular_neighborhood.py`: Spatio-temporal neighbor pruning.
- `src/search_framework.py`: Metaheuristic solver with Active Route Elimination.
- `tests/paper_performance_targets.csv`: Ground truth paper targets.
- `D:\Project\Kaggle\output\`: Local harvest destination.
