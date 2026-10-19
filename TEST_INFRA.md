# TEST_INFRA.md — E2E Campaign Test Infrastructure & Specification

## 1. Executive Architecture

This document specifies the end-to-end test infrastructure for the **Kaggle Distributed Multi-Account Campaign Orchestrator & Benchmark Verifier** (`PH-SHOWOA`).

### Dual Track Strategy
The project follows a **Dual Track** execution model:
1. **Implementation & Operational Track**: Remote distributed execution across 5 authenticated Kaggle accounts (`tafuhihi`, `kanhan162`, `dautromduoicuop`, `keith1101`, `giahaohuynh`), orchestrating 25 concurrent kernels (150 seeds in total) and mutating the production Google Sheet tab `Python_rerun_popsize30`.
2. **Quality & Test Track**: Self-contained, automated test suite (`tests/e2e_campaign/`) executing under pytest. The test suite verifies the pipeline, data transformations, API payloads, queue logic, and solution feasibility without running metaheuristic optimization on local CPUs.

---

## 2. Test Tiers & Scope Hierarchy

| Tier | File | Target Scope | Authoritative Source |
|---|---|---|---|
| **Tier 1: Feature Coverage** | `test_tier1_feature_coverage.py` | Individual core requirements (R1: Remote monitoring, R2: Wave 2 completion queue, R3: Output harvesting & sheet format, R4: Paper targets & feasibility rules). | `PROJECT.md` § Interface Contracts, `ORIGINAL_REQUEST.md`, `tests/paper_performance_targets.csv` |
| **Tier 2: Boundary & Corner Cases** | `test_tier2_boundaries_corners.py` | System boundaries, corrupt files, expired auth tokens, empty/partial responses, duplicate seeds, invalid route formats, and schema limits. | Contract edge limits, Kaggle CLI failure modes, Google Sheets batch bounds |
| **Tier 3: Cross-Feature Integration** | `test_tier3_cross_feature.py` | Inter-module pipelines: (Harvesting $\rightarrow$ Parser $\rightarrow$ Matrix aggregation $\rightarrow$ GSheets JSON mutation), and (Solution Log $\rightarrow$ Route extraction $\rightarrow$ Feasibility & paper target verification). | Full end-to-end dataflow contracts |
| **Tier 4: Acceptance Scenarios** | `test_tier4_acceptance.py` | Real-world acceptance verification against actual harvested log files in `tmp/pop30_completed/` and `outputs/`, verifying 100% feasibility and matrix integrity. | Actual production artifacts, BKS paper targets |

---

## 3. CPU Isolation & Mocking Strategy

### Local CPU Protection
The original user request mandates: **"No heavy solver execution occurs on the local machine CPU."**
To adhere strictly to this constraint:
1. **Subprocess Mocks**: All calls to `kaggle kernels status`, `kaggle kernels output`, and `python -m src` are mocked in unit and synthetic test layers via `unittest.mock.patch`.
2. **Deterministic Synthetics**: Test data generators create realistic log streams, solution outputs, and JSON payloads with microsecond execution overhead.
3. **Artifact-Based Acceptance**: Acceptance tests inspect pre-computed production run logs (from `tmp/pop30_completed/` and `outputs/`) rather than invoking metaheuristic search loops.

---

## 4. Fixture Architecture (`tests/e2e_campaign/conftest.py`)

- `canonical_instances`: Returns the 65 canonical instance names in exact Google Sheet order (Rows 3 to 67: `RCdp1001` through `Rdp211`).
- `paper_targets`: Loads and parses `tests/paper_performance_targets.csv` into a dictionary indexed by lowercased instance name with integer vehicle targets and float distance targets.
- `sample_log_generator`: Produces synthetic solver log files containing runtime, convergence history, vehicle count (`NV`), travel distance (`TD`), and route details.
- `sample_solution_generator`: Produces synthetic `solution.txt` outputs containing node sequences, route costs, vehicle counts, and total costs.

---

## 5. Interface Contracts & Authoritative Assertions

### R1. Kaggle CLI Monitoring Contract
- Command: `kaggle kernels status <owner>/<slug>`
- Status mapping:
  - `KernelWorkerStatus.RUNNING` $\rightarrow$ `RUNNING`
  - `KernelWorkerStatus.COMPLETE` $\rightarrow$ `COMPLETE`
  - `KernelWorkerStatus.ERROR` $\rightarrow$ `ERROR`
  - `KernelWorkerStatus.QUEUED` $\rightarrow$ `QUEUED`
- Account credentials isolation: `KAGGLE_CONFIG_DIR` set to respective account directory (`C:\Users\LENOVO\.kaggle` or `D:\Project\Kaggle\credentials\account-<x>`).

### R2. Wave 2 Completion Queue Contract
- 65 instances $\times$ 30 runs = 1,950 total required runs.
- Missing instances ($0$ runs) and Partial instances ($1 \le \text{runs} < 30$) are cataloged dynamically.
- Dispatch queue computes $\text{remaining\_runs} = 30 - \text{completed\_runs}$.

### R3. Output Harvesting & Google Sheets Sync Format
- Target: Google Sheet ID `1q498GxIhgMLg38hN44w-hWStl89EsSNDBHOp5Ksd2rA`, tab `'Python_rerun_popsize30'`, range `'Python_rerun_popsize30'!G3:I67`.
- Schema:
  ```json
  [
    {
      "op": "write",
      "range": "'Python_rerun_popsize30'!G3:I67",
      "data": [
        ["<NV>", "<TD>", "<Avg/Run>"],
        ...
      ]
    }
  ]
  ```
- Important: The field must be `"data"`, not `"values"`, and must contain exactly 65 rows with 3 columns each.

### R4. Verification Against Paper Targets & Feasibility Invariants
- Cost calculation: $\text{Total Cost} = \text{NV} \times 2000.0 + \text{TD}$.
- Target criterion: A solution meets paper performance if $\text{Total Cost} \le \text{Paper Total Cost}$, or $\text{NV} < \text{Paper NV}$, or ($\text{NV} == \text{Paper NV}$ and $\text{TD} \le \text{Paper TD}$).
- Feasibility constraints:
  1. **Depot Closure**: Route starts and ends at node 0.
  2. **Vehicle Capacity**: Dynamic load $\le Q = 200$ at all customer stops.
  3. **Time Windows**: Arrival time $\le$ customer ready end window ($arr_i \le e_i$), return time to DC $\le$ DC closing window ($t_{\text{return}} \le e_{\text{DC}}$).
  4. **Customer Partitioning**: Every customer node is visited exactly once across all active routes.

---

## 6. Test Execution Instructions

### Running the Full Test Suite
To execute all test tiers cleanly:
```powershell
C:\Users\LENOVO\miniconda3\envs\phshowoa\python.exe -m pytest tests/e2e_campaign/ -v
```

### Running Specific Tiers
```powershell
# Tier 1: Feature Coverage
C:\Users\LENOVO\miniconda3\envs\phshowoa\python.exe -m pytest tests/e2e_campaign/test_tier1_feature_coverage.py -v

# Tier 2: Boundary & Corner Cases
C:\Users\LENOVO\miniconda3\envs\phshowoa\python.exe -m pytest tests/e2e_campaign/test_tier2_boundaries_corners.py -v

# Tier 3: Cross-Feature Integration
C:\Users\LENOVO\miniconda3\envs\phshowoa\python.exe -m pytest tests/e2e_campaign/test_tier3_cross_feature.py -v

# Tier 4: Real-World Acceptance Scenarios
C:\Users\LENOVO\miniconda3\envs\phshowoa\python.exe -m pytest tests/e2e_campaign/test_tier4_acceptance.py -v
```
