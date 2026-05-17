# VRPenstein Python

VRPenstein Python is a port of the original C++ VRPenstein implementation, a parameterized meta-heuristic for Vehicle Routing Problems (VRP). The current codebase focuses on VRPSDPTW: Vehicle Routing Problem with Simultaneous Delivery and Pick-up and Time Windows.

The main algorithm implemented here is a Memetic Algorithm: initialize a population, improve solutions with local search, recombine routes through crossover, repair incomplete solutions with insertion heuristics, and iterate until the stopping criteria are met.

## Features

- Solution initialization with `rcrs`, `rcrs_random`, or `td`.
- Route-based crossover, with an option to disable crossover via `--no_crossover`.
- Post-crossover repair with `rcrs`, `td`, or `regret`.
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
`-- src/
    |-- __main__.py
    |-- main.py
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

`src/main.py` is the CLI entrypoint. `src/data.py` loads instances and runtime parameters. `src/search_framework.py` contains the memetic algorithm loop. `src/operator.py`, `src/eval.py`, and `src/solution.py` implement route and solution operations.

## Requirements

- Python 3.9 or newer.
- No external Python dependencies are required by the current codebase.

## Prepare Benchmark Data

Benchmarks are bundled in `data/data.tar.gz`. Extract them into the `data` directory:

```powershell
tar -xzf data\data.tar.gz -C data
```

After extraction, the repository contains benchmark sets such as `data\Liu_Tang_Yao\*.vrpsdptw` and `data\Wang_Chen\explicit_*.vrpsdptw`.

## Run

With the current layout, run the project directly from source with the `src` module:

```powershell
python -m src --problem data\Liu_Tang_Yao\200_1.vrpsdptw --runs 1 --pop_size 64
```

Write the best solution to a file:

```powershell
python -m src --problem data\Liu_Tang_Yao\200_1.vrpsdptw --runs 1 --pop_size 64 --output result.txt
```

Set a time limit, enable pruning, and enable local-search operators:

```powershell
python -m src --problem data\Liu_Tang_Yao\200_1.vrpsdptw --time 60 --pruning --two_opt --two_opt_star --or_opt 2 --two_exchange 2
```

Show all CLI options:

```powershell
python -m src --help
```

Note: `pyproject.toml` currently declares the console script `vrpenstein = "vrpenstein.__main__:main"`, but the package in this repository currently lives directly under `src`. Therefore `python -m vrpenstein`/`vrpenstein` will not work until the package layout or packaging configuration is updated.

## Usage

```text
python -m src --problem PROBLEM [--pruning] [--output OUTPUT] [--time TIME]
              [--runs RUNS] [--g_1 G_1] [--pop_size POP_SIZE]
              [--init INIT] [--k_init K_INIT] [--no_crossover]
              [--cross_repair CROSS_REPAIR] [--k_crossover K_CROSSOVER]
              [--parent_selection PARENT_SELECTION] [--replacement REPLACEMENT]
              [--ls_prob LS_PROB] [--skip_finding_lo] [--O_1_eval]
              [--two_opt] [--two_opt_star] [--or_opt OR_OPT]
              [--two_exchange TWO_EXCHANGE] [--elo ELO]
              [--random_removal] [--related_removal] [--alpha ALPHA]
              [--removal_lower REMOVAL_LOWER] [--removal_upper REMOVAL_UPPER]
              [--regret_insertion] [--greedy_insertion]
              [--rd_removal_insertion] [--bks BKS]
              [--random_seed RANDOM_SEED]
```

### Main Parameters

- `--problem`: path to the input instance. Required.
- `--time`: time limit in seconds. Defaults to no limit.
- `--runs`: number of independent runs. Default: `10`.
- `--g_1`: number of generations without improvement before a run stops. Default: `500`.
- `--pop_size`: population size. This must be a perfect square because the code uses a Latin grid for `(lambda, gamma)` pairs. Default: `64`.
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

## MATE-like Configuration Example

```powershell
python -m src --problem data\Liu_Tang_Yao\200_1.vrpsdptw --pruning --time 60 --g_1 50 --pop_size 64 --init rcrs --cross_repair regret --parent_selection circle --replacement one_on_one --O_1_eval --two_opt --two_opt_star --or_opt 2 --two_exchange 2 --elo 1 --related_removal --removal_lower 0.25 --removal_upper 0.40 --regret_insertion
```

## License

The original C++ implementation was released under the MIT license. This Python repository currently does not include a separate `LICENSE` file.
