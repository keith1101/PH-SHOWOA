# Review and Port Plan for the GPU-Improved Python Solver

## Decision

**Update `src_python_gpu_SA_RCRS_GRASP`, but do not replace it with the current
workspace `src/` implementation.**

The current workspace contains correctness and experiment-protocol changes that
materially affect whether a reported solution is feasible and whether two runs
are solving the same problem. Those changes should be adapted into the
GPU-improved implementation before its solution quality is interpreted.

The GPU-improved implementation is a separate architecture, not a small patch
to the original Python solver. It adds tensor-resident population evolution,
GPU kernels, islands, and GPU-specific SA/RCRS/GRASP logic. Copying the current
CPU-oriented search loop into it would bypass or invalidate that design.

## Scope and reference points

This review compares three code bases:

| Label | Location / revision | Purpose |
| --- | --- | --- |
| Original Python | `Welkie/ph-showoa/src_python/src` | Pre-improvement reference implementation. |
| GPU-improved Python | `Welkie/ph-showoa/src_python_gpu_SA_RCRS_GRASP` at `d88da6e` | Tensor/GPU implementation under review. |
| Current workspace Python | `src/` at local commit `6488a56` | Paper-aligned correctness and protocol changes. |

The upstream review checkout is local-only under
`tmp/upstream-ph-showoa-audit/` and is ignored by Git.

## Why an update is necessary

The GPU-improved tree is a major rewrite of the original solver. Relative to
the original Python tree, it introduces roughly 6,468 insertions and 1,037
deletions, including `gpu_engine.py` and `gpu_kernels.py`. It adds GPU population
updates, six-island migration, GRASP/RCRS/SA initialization, tensor local search,
and stricter solution handling.

That work may be useful, but several remaining semantics differ from the current
workspace in ways that change feasibility, ranking, and experimental fairness.
These are not cosmetic changes or speed tuning:

1. The GPU-improved parser relaxes the declared vehicle limit by
   `V_NUM_RELAX`; its local-search path can temporarily increase the fleet
   limit as well. A solution using extra vehicles cannot be compared directly
   with a solution that obeys the instance fleet limit.
2. Route costs, tensor scores, SA decisions, and reports do not all use the
   same objective. The tensor backend uses a very large vehicle multiplier for
   strict lexicographic ranking, while other paths use instance dispatch and
   distance costs.
3. Some host and insertion checks do not consistently reject negative load or
   evaluate the final return to the depot. The full GPU route kernel is stricter
   in several of these cases, so CPU and GPU paths can disagree.
4. The GPU-improved branch does not provide the paper protocol selected in the
   workspace: population 30, 1,000 iterations, 30 runs, SA initialization, and
   configurable SA parameters.
5. The improved directory has no equivalent regression and benchmark suite for
   the original Python implementation. This makes an algorithmic regression
   difficult to detect.

## Mandatory port: correctness and ranking

These changes should be completed before interpreting solution-quality claims
from the GPU-improved branch.

### 1. Use one fixed ranking score everywhere

The selected experiment model uses:

```text
score = 2000 * number_of_vehicles + total_distance
```

This is a scalar ranking score. It should not be described as a mathematical
guarantee of strict lexicographic ordering for every possible distance range.

Apply this definition consistently in:

- `solution.py`: route and solution cost calculation;
- `eval.py`: move deltas and route evaluation;
- `compute_backend.py`: `BackendSnapshot`, CPU, Numba, CUDA, and Torch paths;
- `gpu_engine.py` and `gpu_kernels.py`: population ranking, SA deltas, and
  decoded-result reporting;
- all report calculations that derive total distance from cost.

The target behavior must remain unchanged when an input instance specifies
different `DISPATCHINGCOST` or `UNITCOST` values. Those values may still be
retained as input metadata, but must not silently alter search ranking.

### 2. Treat the declared fleet count as a hard constraint

Remove `+ V_NUM_RELAX` from the `VEHICLES` parser. Do not increase
`data.vehicle.max_num` during local search, repair, initialization, or tensor
evolution.

The GPU implementation must carry the declared maximum vehicle count into every
new-route decision and into final population validation. It currently allocates
route storage independently of the instance fleet count; storage capacity must
not imply permission to create more routes.

Every decoded winner must satisfy:

```text
number_of_routes <= declared_number_of_vehicles
```

### 3. Make route validation agree across all execution paths

All paths must reject a route if any of the following holds:

- it has fewer than two depot endpoints;
- it does not begin and end at the depot;
- it contains an internal depot where the route representation forbids one;
- initial delivery load exceeds capacity;
- load becomes negative or exceeds capacity after any customer;
- a customer or final depot time window is violated;
- the final return to the depot is not evaluated;
- a solution has duplicate, missing, or out-of-range customers.

Apply this parity rule to the host evaluator, CPU/Numba insertion kernels, CUDA
insertion kernels, Tensor/Torch route evaluation, repair, and final
`Solution.check()`.

The existing full-GPU route kernel already handles several of these cases. Keep
that behavior and make the other paths match it instead of weakening the GPU
kernel.

### 4. Reject invalid candidates before SA acceptance

Any candidate produced by SHO, WOA, crossover, mutation, repair, ruin/recreate,
or a local-search operator must pass the complete feasibility gate before it is
considered by simulated annealing. A rejected candidate leaves the current
solution unchanged.

This prevents a lower invalid score from being accepted simply because it looks
favorable to an incomplete evaluator.

## Adapt after correctness: paper protocol and reproducibility

These changes matter for paper-style runs, but require adaptation to the GPU
architecture rather than a direct copy from `src/search_framework.py`.

### Paper profile

When `--paper_flags` is present, use these defaults unless a numeric CLI option
explicitly overrides them:

| Setting | Value |
| --- | ---: |
| Population | 30 |
| Iterations | 1,000 |
| Independent runs | 30 |
| Initialization | SA |
| SA initial temperature | 100 |
| SA cooling factor | 0.95 |
| SA minimum temperature | 0.1 |
| SA iterations | 100 |

The Latin design must accept population 30; it must not require a perfect-square
population size. In the GPU branch, population 30 is divisible by the configured
six islands, whereas the current default population 64 silently falls back to a
single island. This activation of islands is a behavior change and must be
benchmarked explicitly.

### SA and scheduling

The workspace and GPU branches use different SA and scheduling implementations.
Map parameters deliberately instead of copying CPU code into tensor kernels.

- Define how `T0`, `alpha`, `Tmin`, and `itermax` map to GPU SA warm-up or
  acceptance kernels.
- Use a run-specific seed and retain a separate `run_best` before comparing it
  with the global best.
- Restore worker-local RNG state after a worker update.
- Decide and document whether paper local search starts at zero-based iteration
  0, then 25, 50, and so on.
- Trigger diversification after consecutive non-improving iterations, rather
  than unconditionally at a fixed generation number.

Changing GPU local-search cadence or diversification changes search budget. It
therefore needs its own A/B experiment after the mandatory correctness port.

## Do not port directly

The following workspace implementations should not be copied wholesale into the
GPU-improved branch before controlled evidence exists:

| Workspace change | Reason to defer |
| --- | --- |
| CPU discrete WOA route relinking and random intra-route operations | The GPU branch has independent tensor WOA operators and device-resident state. Direct copying would introduce Python loops and host/device transfers. |
| CPU `_combined_local_search()` | It clones and scores Python solutions repeatedly, which conflicts with GPU-resident population evolution. |
| CPU `ProcessPool` update flow | The GPU branch manages tensor ownership and uses a different concurrency model. |
| Full replacement of Algorithm 10 repair | The GPU branch already has a separate repair implementation. Port only validated feasibility semantics and tests. |
| CPU SA acceptance implementation | GPU SA uses a different parameter and data model; map semantics first, then compare quality. |

The existing GPU RCRS/GRASP, tensor population representation, and route kernels
should remain in place while the semantic boundary around them is corrected.

## Recommended implementation order

### P0 — required before quality claims

1. Add a single score helper and update every CPU/GPU/Torch score consumer.
2. Remove fleet relaxation and enforce the instance fleet limit in all route
   creation and final validation paths.
3. Align route and insertion feasibility checks, including negative load and
   depot return.
4. Gate SA acceptance on complete feasibility.
5. Add CPU/GPU parity tests for the above behavior.

### P1 — paper-compatible experiment profile

1. Add and validate the `--paper_flags` default profile and CLI precedence.
2. Implement compatible GPU SA parameter handling.
3. Make run seeds and run-best/global-best handling deterministic.
4. Decide, document, and test local-search and diversification timing.

### P2 — heuristic changes only after A/B evidence

1. Evaluate discrete WOA relinking against GPU WOA.
2. Evaluate ordered 2-opt/relocate/swap against tensor local search.
3. Evaluate any repair or diversification change independently.

Each P2 item must be isolated in a feature flag so that its effect can be
measured independently.

## Acceptance tests

P0 is complete only when the following tests pass:

| Test | Expected result |
| --- | --- |
| Instance with non-default dispatch/unit costs | CPU, Numba, CUDA, and Torch report and rank with `2000 * NV + TD`. |
| One-vehicle instance with a two-route candidate | Candidate is rejected in every path. |
| Intermediate pickup overload | Candidate is rejected. |
| Negative load after a delivery/pickup update | Candidate is rejected. |
| Late depot return | Candidate is rejected. |
| Reverse move evaluation | Evaluated sequence is exactly the sequence installed by `apply_move`. |
| Duplicate or missing customer | Final solution check fails. |
| CPU versus GPU route batch | Feasibility, vehicle count, distance, and score agree for the same routes. |
| Decoded GPU population winner | `Solution.check()` passes for every recorded run. |

## Benchmark gate

Do not call a heuristic improvement successful until both variants have passed
P0 and have been compared under the same protocol:

- the same parser and instance revision;
- the same score and feasibility checker;
- the same population, iterations/evaluation budget, run count, and seed list;
- at least 30 paired seeds per instance;
- a representative set of C, R, and RC instances across small, medium, and
  large sizes;
- CUDA warm-up before runtime measurement;
- per-run `NV`, `TD`, score, feasibility result, and wall-clock time;
- median and mean summaries plus a paired Wilcoxon signed-rank test.

Report feasibility rate separately. An infeasible result must never contribute
to a quality average or a claimed improvement over the paper.

## Expected outcome

After P0 and P1, the GPU-improved branch will still retain its GPU-specific
RCRS/GRASP and tensor execution design, but its results will be comparable to
the current workspace and to the intended paper model. Only then can P2
experiments answer whether the GPU-specific heuristics are actually better,
rather than merely optimizing a different objective or a relaxed problem.
