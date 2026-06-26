# PH-SHOWOA Python

PH-SHOWOA Python is a from-paper implementation target for `journal.pone.0343262.pdf`: a parallel hybrid Spotted Hyena Optimizer and Whale Optimization Algorithm for the Vehicle Routing Problem with Simultaneous Pickup and Delivery and Time Windows (VRPSPDTW).

This repository also includes a hybrid CPU-GPU execution path. The CPU keeps the metaheuristic control logic, while the CUDA backend accelerates batched route evaluation and move scoring.

## Features

- Solution initialization with `rcrs`, `rcrs_random`, or `td`.
- SHO-style peer-guided route recombination and mutation.
- WOA-style best-guided route and segment intensification.
- Adaptive hybrid probability between SHO and WOA behaviours.
- Ablation mode for PH-SHOWOA, SHO-only, and WOA-only runs.
- Simulated-annealing acceptance for non-improving updates.
- Periodic best-solution local search with stagnation-triggered diversification.
- Optional process-level parallel solution updates via `--workers`.
- Optional CUDA backend for batched route evaluation and insertion scoring.
- Parent selection with `circle`, `tournament`, or `rdslection`.
- Population replacement with `one_on_one` or `elitism`.
- Local search operators: `2-opt`, `2-opt*`, `or-opt`, and `2-exchange`.
- Escape from local optima with random/related removal and greedy/regret insertion.
- Edge pruning based on time-window and capacity feasibility.
- Best-solution output via `--output`.

## Repository Structure

```text
.
|-- README.md
|-- pyproject.toml
|-- data/
|   `-- data.tar.gz
|-- scripts/
|   `-- compare_with_paper_logged.py
`-- src/
    |-- __main__.py
    |-- main.py
    |-- compute_backend.py
    |-- data.py
    |-- search_framework.py
    |-- operator.py
    |-- solution.py
    |-- eval.py
    |-- move.py
    |-- state.py
    |-- util.py
    `-- config.py
```

`src/main.py` is the CLI entrypoint. `src/data.py` loads instances and runtime parameters. `src/search_framework.py` contains the PH-SHOWOA loop. `src/compute_backend.py` provides the CPU and CUDA route-evaluation backends. `src/operator.py`, `src/eval.py`, and `src/solution.py` implement route and solution operations.

## Requirements

- Python 3.10 or newer is recommended.
- NumPy is required.
- Numba is optional and enables the CUDA backend when installed.
- A supported NVIDIA GPU and CUDA runtime are required to use `--compute_backend cuda`.

## Installation

Install the project in editable mode:

```powershell
pip install -e .
```

Install the CUDA extra when you want GPU support:

```powershell
pip install -e ".[cuda]"
```

## Prepare Benchmark Data

Benchmarks are bundled in `data/data.tar.gz`. Extract them into the `data` directory:

```powershell
tar -xzf data\data.tar.gz -C data
```

After extraction, the repository contains benchmark sets such as `data\Liu_Tang_Yao\*.vrpsdptw` and `data\Wang_Chen\explicit_*.vrpsdptw`.

## Run

With the current layout, run the project directly from source with the `src` module:

```powershell
python -m src --problem data\Liu_Tang_Yao\200_1.vrpsdptw --runs 1 --pop_size 64 --max_iter 100
```

Run the same problem on CUDA when the GPU backend is available:

```powershell
python -m src --problem data\Liu_Tang_Yao\200_1.vrpsdptw --runs 1 --pop_size 64 --max_iter 100 --compute_backend cuda
```

Write the best solution to a file:

```powershell
python -m src --problem data\Liu_Tang_Yao\200_1.vrpsdptw --runs 1 --pop_size 64 --max_iter 100 --output result.txt
```

Set a time limit, enable pruning, and enable local-search operators:

```powershell
python -m src --problem data\Liu_Tang_Yao\200_1.vrpsdptw --time 60 --pruning --two_opt --two_opt_star --or_opt 2 --two_exchange 2
```

Run with explicit PH-SHOWOA controls:

```powershell
python -m src --problem data\Liu_Tang_Yao\200_1.vrpsdptw --runs 1 --pop_size 64 --max_iter 500 --workers 0 --local_search_interval 25 --stagnation_interval 50 --diversify_ratio 0.40 --sho_mutation_prob 0.35 --compute_backend auto
```

Show all CLI options:

```powershell
python -m src --help
```

If the project is installed, the console scripts `ph-showoa` and `vrpenstein` both point to the current `src` entrypoint.

When `--compute_backend cuda` is selected, the backend evaluates route candidates in batches on the GPU. The CPU still controls population updates, acceptance, and search strategy. If CUDA is not available, `--compute_backend auto` falls back to CPU execution.

## CUDA Backend

The CUDA path is intentionally hybrid rather than fully device-resident:

1. `src/data.py` parses the instance and flattens the customer metadata, distance matrix, and travel-time matrix into contiguous arrays.
2. `src/compute_backend.py` builds a backend snapshot and launches a Numba CUDA kernel for batched route evaluation.
3. Each kernel worker handles one candidate route at a time and checks depot endpoints, capacity, and time-window feasibility while accumulating cost.
4. `src/eval.py` routes feasibility and cost checks through the active backend.
5. `src/operator.py` groups insertion and repair candidates into batches so the GPU can score many possibilities in one launch.
6. `src/search_framework.py` stays on the CPU for orchestration, selection, acceptance, and diversification.

Practical constraints:

- `--workers` is forced to `1` when the CUDA backend is active because the backend is not multi-process safe.
- GPU acceleration is most useful when the batch size is large enough to keep the device busy.
- `--compute_backend auto` tries CUDA first and falls back to CPU if CUDA is unavailable.

## Usage

```text
python -m src --problem PROBLEM [--pruning] [--output OUTPUT] [--time TIME]
              [--runs RUNS] [--g_1 G_1] [--max_iter MAX_ITER]
              [--pop_size POP_SIZE] [--workers WORKERS]
              [--compute_backend COMPUTE_BACKEND]
              [--local_search_interval LOCAL_SEARCH_INTERVAL]
              [--stagnation_interval STAGNATION_INTERVAL]
              [--diversify_ratio DIVERSIFY_RATIO]
              [--sho_mutation_prob SHO_MUTATION_PROB]
              [--hybrid_mode HYBRID_MODE]
              [--init INIT] [--k_init K_INIT] [--no_crossover]
              [--cross_repair CROSS_REPAIR] [--k_crossover K_CROSSOVER]
              [--parent_selection PARENT_SELECTION] [--replacement REPLACEMENT]
              [--ls_prob LS_PROB] [--skip_finding_lo] [--O_1_eval]
              [--two_opt] [--two_opt_star] [--or_opt OR_OPT]
              [--two_exchange TWO_EXCHANGE] [--elo ELO]
              [--random_removal] [--related_removal] [--alpha ALPHA]
              [--removal_lower REMOVAL_LOWER] [--removal_upper REMOVAL_UPPER] [--regret_insertion]
              [--greedy_insertion] [--rd_removal_insertion] [--bks BKS]
              [--random_seed RANDOM_SEED]
```

### Main Parameters

- `--problem`: path to the input instance. Required.
- `--time`: time limit in seconds. Defaults to no limit.
- `--runs`: number of independent runs. Default: `10`.
- `--g_1`: number of generations without improvement before a run stops. Default: `500`.
- `--max_iter`: number of PH-SHOWOA update iterations. Defaults to `--g_1`.
- `--pop_size`: population size. This must be a perfect square because the code uses a Latin grid for `(lambda, gamma)` pairs. Default: `64`.
- `--workers`: number of worker processes for parallel individual updates. Use `1` for serial execution, `0` for all available CPU cores. Default: `0`.
- `--local_search_interval`: apply deep local search to the global best every N iterations. Default: `25`.
- `--stagnation_interval`: diversify after N iterations without global-best improvement. Default: `50`.
- `--diversify_ratio`: fraction of non-elite individuals rebuilt during diversification. Default: `0.40`.
- `--sho_mutation_prob`: probability of applying light mutation after the SHO-style recombination step. Default: `0.35`.
- `--hybrid_mode`: algorithm mode, one of `ph_showoa`, `sho`, or `woa`. Default: `ph_showoa`.
- `--compute_backend`: compute mode, one of `auto`, `cpu`, or `cuda`. Default: `auto`. `cuda` uses the GPU backend; `auto` tries CUDA and falls back to CPU.
- `--random_seed`: random seed. Default: `42`.
- `--bks`: best-known solution cost, used to report the time needed to reach or improve it.
- `--output`: file path for the best solution. If omitted, the best solution is printed to stdout.

### Initialization, Crossover, and Replacement

- `--init`: insertion heuristic for initialization. Supported values in the code: `rcrs`, `rcrs_random`, `td`.
- `--k_init`: number of candidates considered during initialization. Defaults to the number of customers.
- `--no_crossover`: skip crossover and copy a parent directly to the child.
- `--cross_repair`: repair heuristic after crossover. Supported values: `rcrs`, `td`, `regret`.
- `--k_crossover`: number of candidates considered during post-crossover repair. Defaults to the number of customers.
- `--parent_selection`: parent-selection strategy: `circle`, `tournament`, or `rdslection`.
- `--replacement`: replacement strategy: `one_on_one` or `elitism`.

### Local Search and Escaping Local Optima

- `--ls_prob`: probability of applying local search to each solution. Default: `1.0`.
- `--skip_finding_lo`: skip the local-optimum search phase.
- `--O_1_eval`: enable O(1) move evaluation for supported operators.
- `--two_opt`: enable 2-opt.
- `--two_opt_star`: enable 2-opt*. This is enabled by default in `config.py`; the flag also enables it explicitly from the CLI.
- `--or_opt N`: enable or-opt with maximum segment length `N`.
- `--two_exchange N`: enable 2-exchange with maximum exchange length `N`.
- `--elo N`: number of escape-local-optima attempts. Default: `1`.
- `--random_removal`: enable random removal.
- `--related_removal`: enable related removal.
- `--alpha`: relatedness coefficient used with `--related_removal`. Default: `1.0`.
- `--removal_lower`, `--removal_upper`: lower and upper customer-removal ratios. Defaults: `0.2` and `0.4`.
- `--regret_insertion`: enable regret insertion during repair.
- `--greedy_insertion`: enable greedy insertion during repair.
- `--rd_removal_insertion`: enable random removal and insertion.

## Input Instance Format

The current parser requires `EDGE_WEIGHT_TYPE: EXPLICIT` and reads the following sections:

```text
NAME: <instance_name>
TYPE: <problem_type>
DIMENSION: <number_of_nodes_including_depot>
VEHICLES: <number_of_vehicles>
DISPATCHINGCOST: <vehicle_dispatching_cost>
UNITCOST: <cost_per_distance_unit>
CAPACITY: <vehicle_capacity>
EDGE_WEIGHT_TYPE: EXPLICIT
NODE_SECTION
<node_id>,<delivery>,<pickup>,<start_time>,<end_time>,<service_time>
...
DISTANCETIME_SECTION
<from_node>,<to_node>,<distance>,<travel_time>
...
DEPOT_SECTION
<depot_node_id>
```

`DIMENSION` includes the depot, so the number of customers used by the code is `DIMENSION - 1`.

## PH-SHOWOA Configuration Example

```powershell
python -m src --problem data\Liu_Tang_Yao\200_1.vrpsdptw --pruning --time 60 --max_iter 500 --pop_size 64 --workers 0 --local_search_interval 25 --stagnation_interval 50 --diversify_ratio 0.40 --sho_mutation_prob 0.35 --init rcrs --O_1_eval --two_opt --two_opt_star --or_opt 2 --two_exchange 2 --elo 1 --related_removal --removal_lower 0.25 --removal_upper 0.40 --regret_insertion
```

Run ablations with the same settings by changing `--hybrid_mode`:

```powershell
python -m src --problem data\Liu_Tang_Yao\200_1.vrpsdptw --runs 1 --pop_size 64 --max_iter 500 --workers 1 --hybrid_mode sho
python -m src --problem data\Liu_Tang_Yao\200_1.vrpsdptw --runs 1 --pop_size 64 --max_iter 500 --workers 1 --hybrid_mode woa
```

## Paper Performance Test

Paper targets from Tables 3-5 are stored in `tests/paper_performance_targets.csv`. The performance test is gated because it runs stochastic optimization:

```powershell
$env:RUN_PAPER_PERF="1"
$env:PAPER_PERF_INSTANCES="RCdp1001"
$env:PAPER_PERF_POP_SIZE="64"
$env:PAPER_PERF_MAX_ITER="500"
python -m unittest tests.test_paper_performance
```

Use a comma-separated instance list such as `Rdp101,Cdp101,RCdp101`, or `all` for the complete target file. Optional tolerances are `PAPER_PERF_DISTANCE_TOLERANCE` and `PAPER_PERF_VEHICLE_SLACK`. Use `PAPER_PERF_EXTRA_ARGS` to pass additional CLI flags to every run.

For 100-customer instances, the full `64 x 500` serial run may exceed the default timeout. Either raise the timeout:

```powershell
$env:PAPER_PERF_TIMEOUT="3600"
```

or run a faster harness check first:

```powershell
$env:RUN_PAPER_PERF="1"
$env:PAPER_PERF_INSTANCES="Rdp101,Cdp101,RCdp101"
$env:PAPER_PERF_POP_SIZE="16"
$env:PAPER_PERF_MAX_ITER="50"
$env:PAPER_PERF_DISTANCE_TOLERANCE="0.50"
$env:PAPER_PERF_VEHICLE_SLACK="5"
$env:PAPER_PERF_EXTRA_ARGS="--pruning --O_1_eval --two_opt --two_opt_star --or_opt 2 --two_exchange 2 --related_removal --regret_insertion"
python -m unittest tests.test_paper_performance
```

## Batch Benchmarking

For repeated multi-instance comparisons with per-instance logs, summaries, and ETA output, use:

```powershell
python scripts\compare_with_paper_logged.py --compute_backend cuda
```

The script writes one result directory per instance and stores run-level logs, solution snapshots, and aggregate summaries.
