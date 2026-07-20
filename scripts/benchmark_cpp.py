import csv
import hashlib
import json
import re
import math
import subprocess
import time
from pathlib import Path
from statistics import mean
from dataclasses import asdict, dataclass
from functools import lru_cache

ROOT = Path(__file__).resolve().parents[1]
TARGETS_CSV = ROOT / "tests" / "paper_performance_targets.csv"
SOLVER_EXE = ROOT / "build_cuda" / "phshowoa_cpp.exe"
CPU_SOLVER_EXE = ROOT / "build_cpu" / "phshowoa_cpp.exe"

BENCHMARK_SCHEMA_VERSION = "7"

DEFAULT_INSTANCES = [
    "RCdp1001",
    "RCdp5001",
    "RCdp5007",
    "RCdp5004",
    "RCdp101",
    "Cdp103",
    "RCdp205",
    "Rdp210",
    "RCdp207",
    "RCdp202",
    "Rdp103",
    "Cdp104",
    "Cdp102",
    "RCdp203",
    "Rdp203",
    "RCdp104",
]

@dataclass
class BenchmarkConfig:
    workers: int
    gpu_route_min_batch: int
    gpu_route_min_work: int
    gpu_insertion_min_batch: int
    label: str
    mode: str
    compute_backend: str
    gpu_batched_insertion: bool
    no_gpu_solution_eval: bool

BENCHMARK_MODE_PRESETS = {
    "cpu": {
        "compute_backend": "cpu",
        "gpu_batched_insertion": False,
        "no_gpu_solution_eval": True,
    },
    "cuda_baseline": {
        "compute_backend": "cuda",
        "gpu_batched_insertion": False,
        "no_gpu_solution_eval": False,
    },
    "cuda_no_solution_eval": {
        "compute_backend": "cuda",
        "gpu_batched_insertion": False,
        "no_gpu_solution_eval": True,
    },
    "cuda_batched": {
        "compute_backend": "cuda",
        "gpu_batched_insertion": True,
        "no_gpu_solution_eval": False,
    },
    "full_gpu": {
        "compute_backend": "cuda",
        "gpu_batched_insertion": True,
        "no_gpu_solution_eval": False,
    },
}

def load_targets():
    targets = {}
    with open(TARGETS_CSV, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            inst_name = row["instance"].strip().lower()
            targets[inst_name] = {
                "instance": row["instance"].strip(),
                "path": str(ROOT / row["path"].strip()),
                "target_vehicles": int(row["target_vehicles"]),
                "target_distance": float(row["target_distance"]),
            }

    # Liu-Tang-Yao instances are useful scalability benchmarks even though the
    # repository does not currently carry paper reference objectives for them.
    lty_dir = ROOT / "data" / "Liu_Tang_Yao"
    if lty_dir.is_dir():
        for instance_path in sorted(lty_dir.glob("*.vrpsdptw")):
            instance_name = instance_path.stem
            targets.setdefault(instance_name.lower(), {
                "instance": instance_name,
                "path": str(instance_path),
                "target_vehicles": -1,
                "target_distance": math.nan,
            })
    return targets

def validate_requested_instances(requested_instances, targets):
    resolved = []
    seen = set()
    missing = []
    duplicates = []
    for requested in requested_instances:
        target = targets.get(requested.strip().lower())
        if target is None:
            missing.append(requested)
            continue
        canonical = target["instance"]
        canonical_key = canonical.lower()
        if canonical_key in seen:
            duplicates.append(canonical)
            continue
        seen.add(canonical_key)
        resolved.append(canonical)

    if missing:
        raise ValueError("Unknown benchmark instances: " + ", ".join(missing))
    if duplicates:
        raise ValueError("Duplicate benchmark instances after resolution: " + ", ".join(duplicates))
    if not resolved:
        raise ValueError("No benchmark instances were selected")
    return resolved

@lru_cache(maxsize=4)
def _file_sha256(path_string):
    digest = hashlib.sha256()
    with open(path_string, "rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

def build_run_fingerprint(instance_name, instance_path, seed, args, config, solver_exe):
    effective_architecture = "full_gpu" if config.mode == "full_gpu" else args.architecture
    payload = {
        "benchmark_schema_version": BENCHMARK_SCHEMA_VERSION,
        "solver_sha256": _file_sha256(str(solver_exe.resolve())),
        "instance": instance_name,
        "instance_path": str(Path(instance_path).resolve()),
        "seed": seed,
        "max_iter": args.max_iter,
        "pop_size": args.pop_size,
        "k_init": getattr(args, "k_init", None),
        "architecture": effective_architecture,
        "objective": args.objective,
        "num_islands": args.num_islands,
        "migration_interval": args.migration_interval,
        "migration_size": args.migration_size,
        "migration_mode": args.migration_mode,
        "profile": args.profile,
        "gpu_serialize_workers": args.gpu_serialize_workers,
        "gpu_request_broker": args.gpu_request_broker,
        "execution_policy": getattr(args, "execution_policy", "adaptive"),
        "gpu_solution_verify_interval": getattr(args, "gpu_solution_verify_interval", 0),
        "config": asdict(config),
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

PROFILE_LINE_RE = re.compile(
    r"^(?P<name>\S+)\s+calls=\s*(?P<calls>\d+)"
    r"(?:\s+units=\s*(?P<units>\d+)\s+avg_units=\s*(?P<avg_units>[-+\d.]+)\s+max_units=\s*(?P<max_units>\d+))?"
    r"\s+total_ms=\s*(?P<total_ms>[-+\d.]+)\s+avg_ms=\s*(?P<avg_ms>[-+\d.]+)"
)

def parse_profile(stdout):
    profile = {}
    for raw_line in stdout.splitlines():
        line = raw_line.strip()
        match = PROFILE_LINE_RE.match(line)
        if not match:
            continue
        item = {
            "calls": int(match.group("calls")),
            "total_ms": float(match.group("total_ms")),
            "avg_ms": float(match.group("avg_ms")),
        }
        if match.group("units") is not None:
            item["units"] = int(match.group("units"))
            item["avg_units"] = float(match.group("avg_units"))
            item["max_units"] = int(match.group("max_units"))
        profile[match.group("name")] = item
    return profile

def profile_value(profile, counter, key, default=0.0):
    return profile.get(counter, {}).get(key, default)

def csv_value(value):
    if isinstance(value, float) and math.isnan(value):
        return ""
    return value

CHECK_RE = re.compile(
    r"This cost\s+(?P<cost>[-+\d.eE]+),\s+check total cost\s+(?P<check_cost>[-+\d.eE]+),\s+diff\s+(?P<diff>[-+\d.eE]+)"
)
FEASIBILITY_FAILURE_MARKERS = [
    "Not starting/ending at DC",
    "Capacity violation",
    "Time window violation",
    "Duplicate node:",
    "Missing customer:",
]

def parse_feasibility(stdout):
    check_match = CHECK_RE.search(stdout)
    failure_marker = next((marker for marker in FEASIBILITY_FAILURE_MARKERS if marker in stdout), None)
    if check_match:
        diff = float(check_match.group("diff"))
        return {
            "feasible": failure_marker is None and abs(diff) <= 1e-3,
            "check_cost": float(check_match.group("check_cost")),
            "check_diff": diff,
            "failure_marker": failure_marker,
        }
    return {
        "feasible": False,
        "check_cost": None,
        "check_diff": None,
        "failure_marker": failure_marker or "missing_final_check",
    }

def _resolve_solver_exe(config):
    """Pick the right solver binary: build_cpu for cpu backend, build_cuda otherwise."""
    if config.compute_backend == "cpu" and CPU_SOLVER_EXE.exists():
        return CPU_SOLVER_EXE
    return SOLVER_EXE

def run_solver(instance_name, instance_path, seed, repeat, args, config):
    # Create directory structure
    run_dir = ROOT / "batch_results" / args.output_tag / config.label / instance_name / "runs" / f"run_{repeat+1:02d}_seed_{seed}"
    run_dir.mkdir(parents=True, exist_ok=True)
    
    solution_path = run_dir / "solution.txt"
    log_path = run_dir / "log.txt"
    summary_path = run_dir / "summary.json"
    solver_exe = _resolve_solver_exe(config)
    fingerprint = build_run_fingerprint(instance_name, instance_path, seed, args, config, solver_exe)

    # --- Resume logic ---
    if summary_path.exists():
        try:
            with open(summary_path, "r", encoding="utf-8") as f:
                cached = json.load(f)
            if cached.get("status") == "success" and cached.get("fingerprint") == fingerprint:
                # Return cached results
                return (
                    cached["vehicles"],
                    cached["distance"],
                    cached["total_cost"],
                    cached["duration_sec"],
                    cached.get("profile", {}),
                    {
                        "feasible": cached.get("feasible", False),
                        "failure_marker": cached.get("failure_marker", ""),
                        "check_cost": cached.get("check_cost"),
                        "check_diff": cached.get("check_diff"),
                    }
                )
        except Exception:
            pass
    # --------------------

    cmd = [
        str(solver_exe),
        instance_path,
        "--max_iter", str(args.max_iter),
        "--pop_size", str(args.pop_size),
        "--random_seed", str(seed),
        "--runs", "1",
        "--output", str(solution_path),
        "--paper_flags",
        "--compute_backend", config.compute_backend,
        "--workers", str(config.workers),
        "--gpu_route_min_batch", str(config.gpu_route_min_batch),
        "--gpu_route_min_work", str(config.gpu_route_min_work),
        "--gpu_insertion_min_batch", str(config.gpu_insertion_min_batch),
    ]
    if getattr(args, "k_init", None) is not None:
        cmd.extend(["--k_init", str(args.k_init)])
    effective_architecture = "full_gpu" if config.mode == "full_gpu" else args.architecture
    if effective_architecture != "legacy":
        cmd.extend(["--architecture", effective_architecture])
    if config.gpu_batched_insertion:
        cmd.append("--gpu_batched_insertion")
    if config.no_gpu_solution_eval:
        cmd.append("--no_gpu_solution_eval")
    if args.gpu_serialize_workers:
        cmd.append("--gpu_serialize_workers")
    if args.gpu_request_broker:
        cmd.append("--gpu_request_broker")
    cmd.extend(["--execution_policy", args.execution_policy])
    cmd.extend(["--gpu_solution_verify_interval", str(args.gpu_solution_verify_interval)])
    if args.profile:
        cmd.append("--profile")
    if getattr(args, "objective", "weighted") != "weighted":
        cmd.extend(["--objective", args.objective])
    if getattr(args, "num_islands", 1) > 1:
        cmd.extend(["--num_islands", str(args.num_islands)])
        cmd.extend(["--migration_interval", str(args.migration_interval)])
        cmd.extend(["--migration_size", str(args.migration_size)])
        cmd.extend(["--migration_mode", args.migration_mode])
    
    start_t = time.perf_counter()
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    duration = time.perf_counter() - start_t

    stdout = result.stdout or ""
    stderr = result.stderr or ""
    with open(log_path, "w", encoding="utf-8") as f:
        f.write(stdout)
        if stderr:
            f.write("\n--- STDERR ---\n")
            f.write(stderr)

    if result.returncode != 0:
        failure_summary = {
            "benchmark_schema_version": BENCHMARK_SCHEMA_VERSION,
            "fingerprint": fingerprint,
            "seed": seed,
            "duration_sec": duration,
            "status": "failed",
            "return_code": result.returncode,
            "solver_exe": str(solver_exe),
            "command": " ".join(cmd),
            "run_dir": str(run_dir),
            "solution_path": str(solution_path),
            "log_path": str(log_path),
        }
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(failure_summary, f, indent=4)
        diagnostic = (stderr or stdout).strip()
        if len(diagnostic) > 4000:
            diagnostic = diagnostic[-4000:]
        raise RuntimeError(
            f"Solver failed for {instance_name}, seed {seed}, exit code "
            f"{result.returncode}. See {log_path}.\n{diagnostic}"
        )

    profile = parse_profile(stdout)
    feasibility = parse_feasibility(stdout)
        
    nv_match = None
    td_match = None
    tc_match = None
    if solution_path.exists():
        with open(solution_path, "r", encoding="utf-8") as f:
            sol_content = f.read()
        nv_match = re.search(r"vehicle \(route\) number:\s*(\d+)", sol_content)
        td_match = re.search(r"Total distance:\s*([\d.]+)", sol_content)
        tc_match = re.search(r"Total cost:\s*([\d.]+)", sol_content)
    
    if not nv_match or not tc_match:
        print("STDOUT:", stdout)
        if solution_path.exists():
            with open(solution_path, "r", encoding="utf-8") as f:
                print("SOLUTION FILE:", f.read())
        raise RuntimeError(f"Failed to parse output for seed {seed}")
        
    nv = int(nv_match.group(1))
    tc = float(tc_match.group(1))
    td = float(td_match.group(1)) if td_match else tc - nv * 2000.0
    
    # Save summary.json
    summary_data = {
        "benchmark_schema_version": BENCHMARK_SCHEMA_VERSION,
        "fingerprint": fingerprint,
        "seed": seed,
        "vehicles": nv,
        "distance": td,
        "total_cost": tc,
        "duration_sec": duration,
        "status": "success",
        "solver_exe": str(solver_exe),
        "command": " ".join(cmd),
        "objective": getattr(args, "objective", "weighted"),
        "architecture": effective_architecture,
        "benchmark_mode": config.mode,
        "compute_backend": config.compute_backend,
        "workers": config.workers,
        "gpu_route_min_batch": config.gpu_route_min_batch,
        "gpu_route_min_work": config.gpu_route_min_work,
        "gpu_insertion_min_batch": config.gpu_insertion_min_batch,
        "gpu_batched_insertion": config.gpu_batched_insertion,
        "gpu_solution_eval": not config.no_gpu_solution_eval,
        "gpu_serialize_workers": args.gpu_serialize_workers,
        "gpu_request_broker": args.gpu_request_broker,
        "execution_policy": args.execution_policy,
        "gpu_solution_verify_interval": args.gpu_solution_verify_interval,
        "config_label": config.label,
        "feasible": feasibility["feasible"],
        "check_cost": feasibility["check_cost"],
        "check_diff": feasibility["check_diff"],
        "failure_marker": feasibility["failure_marker"],
        "profile": profile,
        "run_dir": str(run_dir),
        "solution_path": str(solution_path),
        "log_path": str(log_path)
    }
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary_data, f, indent=4)
        
    return nv, td, tc, duration, profile, feasibility

def build_configs(args):
    worker_values = args.worker_values if args.worker_values else [args.workers]
    route_threshold_values = args.gpu_route_min_batches if args.gpu_route_min_batches else [args.gpu_route_min_batch]
    route_work_values = args.gpu_route_min_works if args.gpu_route_min_works else [args.gpu_route_min_work]
    threshold_values = args.gpu_insertion_min_batches if args.gpu_insertion_min_batches else [args.gpu_insertion_min_batch]
    mode_values = args.benchmark_modes if args.benchmark_modes else ["manual"]

    configs = []
    for mode in mode_values:
        if mode == "manual":
            preset = {
                "compute_backend": args.compute_backend,
                "gpu_batched_insertion": args.gpu_batched_insertion,
                "no_gpu_solution_eval": args.no_gpu_solution_eval,
            }
        else:
            preset = BENCHMARK_MODE_PRESETS[mode]

        effective_route_threshold_values = route_threshold_values
        effective_route_work_values = route_work_values
        effective_threshold_values = threshold_values
        if preset["compute_backend"] == "cpu":
            if len(route_threshold_values) > 1:
                effective_route_threshold_values = [route_threshold_values[0]]
            if len(route_work_values) > 1:
                effective_route_work_values = [route_work_values[0]]
            if len(threshold_values) > 1:
                effective_threshold_values = [threshold_values[0]]

        for workers in worker_values:
            for route_threshold in effective_route_threshold_values:
                for route_work in effective_route_work_values:
                    for threshold in effective_threshold_values:
                        effective_batched_insertion = (
                            preset["gpu_batched_insertion"] or args.architecture == "hybrid_v2"
                        )
                        label_parts = []
                        if mode != "manual":
                            label_parts.append(mode)
                        label_parts.append(f"workers_{workers}")
                        label_parts.append(f"routemin_{route_threshold}")
                        label_parts.append(f"routework_{route_work}")
                        label_parts.append(f"insertmin_{threshold}")
                        if args.gpu_serialize_workers:
                            label_parts.append("serialized")
                        if args.gpu_request_broker:
                            label_parts.append("broker")
                        effective_architecture = "full_gpu" if mode == "full_gpu" else args.architecture
                        if effective_architecture != "legacy" and effective_architecture not in label_parts:
                            label_parts.append(effective_architecture)
                        label = "_".join(label_parts)
                        configs.append(BenchmarkConfig(
                            workers=workers,
                            gpu_route_min_batch=route_threshold,
                            gpu_route_min_work=route_work,
                            gpu_insertion_min_batch=threshold,
                            label=label,
                            mode=mode,
                            compute_backend=preset["compute_backend"],
                            gpu_batched_insertion=effective_batched_insertion,
                            no_gpu_solution_eval=preset["no_gpu_solution_eval"],
                        ))
    return configs

def run_benchmark_config(args, config, targets):
    print(
        f"\n=== Config: {config.label} "
        f"(workers={config.workers}, gpu_route_min_batch={config.gpu_route_min_batch}, "
        f"gpu_route_min_work={config.gpu_route_min_work}, "
        f"gpu_insertion_min_batch={config.gpu_insertion_min_batch}) ===",
        flush=True
    )

    results = []

    for idx, inst in enumerate(args.instances, 1):
        target = targets.get(inst.lower())
        if not target:
            print(f"Warning: target not found for {inst}", flush=True)
            continue

        print(f"[{idx}/{len(args.instances)}] Running {target['instance']}...", flush=True)

        runs_nv = []
        runs_td = []
        runs_tc = []
        runs_time = []
        run_profiles = []
        run_feasibility = []

        for repeat in range(args.repeats):
            seed = 42 + repeat
            nv, td, tc, duration, profile, feasibility = run_solver(target["instance"], target["path"], seed, repeat, args, config)
            runs_nv.append(nv)
            runs_td.append(td)
            runs_tc.append(tc)
            runs_time.append(duration)
            run_profiles.append(profile)
            run_feasibility.append(feasibility)
            feasibility_label = "yes" if feasibility["feasible"] else f"no:{feasibility['failure_marker']}"
            print(f"      run {repeat+1:02d}/{args.repeats} seed={seed} -> NV={nv} TD={td:.2f} cost={tc:.2f} feasible={feasibility_label} ({duration:.3f}s)", flush=True)

        avg_nv = mean(runs_nv)
        avg_td = mean(runs_td)
        avg_tc = mean(runs_tc)
        avg_time = mean(runs_time)
        avg_profile = {
            "feasibility_batch_calls": mean([profile_value(p, "feasibility_route_batch", "calls") for p in run_profiles]),
            "feasibility_batch_units": mean([profile_value(p, "feasibility_route_batch", "units") for p in run_profiles]),
            "feasibility_batch_avg_size": mean([profile_value(p, "feasibility_route_batch", "avg_units") for p in run_profiles]),
            "insertion_batch_calls": mean([profile_value(p, "insertion_batch_scoring", "calls") for p in run_profiles]),
            "insertion_batch_requests": mean([profile_value(p, "insertion_batch_scoring", "units") for p in run_profiles]),
            "insertion_batch_avg_size": mean([profile_value(p, "insertion_batch_scoring", "avg_units") for p in run_profiles]),
            "insertion_broker_submissions": mean([profile_value(p, "insertion_broker_submission", "calls") for p in run_profiles]),
            "insertion_broker_requests": mean([profile_value(p, "insertion_broker_submission", "units") for p in run_profiles]),
            "cuda_insertion_cpu_fallback_calls": mean([profile_value(p, "cuda_insertion_cpu_fallback", "calls") for p in run_profiles]),
            "cuda_insertion_cpu_fallback_requests": mean([profile_value(p, "cuda_insertion_cpu_fallback", "units") for p in run_profiles]),
            "cuda_eval_alloc_ms": mean([profile_value(p, "cuda_allocation", "total_ms") for p in run_profiles]),
            "cuda_eval_h2d_calls": mean([profile_value(p, "cuda_copy_h2d", "calls") for p in run_profiles]),
            "cuda_eval_h2d_bytes": mean([profile_value(p, "cuda_copy_h2d", "units") for p in run_profiles]),
            "cuda_eval_h2d_ms": mean([profile_value(p, "cuda_copy_h2d", "total_ms") for p in run_profiles]),
            "cuda_eval_kernel_calls": mean([profile_value(p, "cuda_kernel", "calls") for p in run_profiles]),
            "cuda_eval_kernel_ms": mean([profile_value(p, "cuda_kernel", "total_ms") for p in run_profiles]),
            "cuda_eval_d2h_bytes": mean([profile_value(p, "cuda_copy_d2h", "units") for p in run_profiles]),
            "cuda_eval_d2h_ms": mean([profile_value(p, "cuda_copy_d2h", "total_ms") for p in run_profiles]),
            "cuda_route_cpu_fallback_calls": mean([profile_value(p, "cuda_route_cpu_fallback", "calls") for p in run_profiles]),
            "cuda_route_cpu_fallback_work": mean([profile_value(p, "cuda_route_cpu_fallback", "units") for p in run_profiles]),
            "cuda_insertion_alloc_ms": mean([profile_value(p, "cuda_insertion_allocation", "total_ms") for p in run_profiles]),
            "cuda_insertion_h2d_calls": mean([profile_value(p, "cuda_insertion_copy_h2d", "calls") for p in run_profiles]),
            "cuda_insertion_h2d_bytes": mean([profile_value(p, "cuda_insertion_copy_h2d", "units") for p in run_profiles]),
            "cuda_insertion_h2d_ms": mean([profile_value(p, "cuda_insertion_copy_h2d", "total_ms") for p in run_profiles]),
            "cuda_insertion_kernel_calls": mean([profile_value(p, "cuda_insertion_kernel", "calls") for p in run_profiles]),
            "cuda_insertion_kernel_ms": mean([profile_value(p, "cuda_insertion_kernel", "total_ms") for p in run_profiles]),
            "cuda_insertion_d2h_bytes": mean([profile_value(p, "cuda_insertion_copy_d2h", "units") for p in run_profiles]),
            "cuda_insertion_d2h_ms": mean([profile_value(p, "cuda_insertion_copy_d2h", "total_ms") for p in run_profiles]),
            "insertion_scheduler_cpu_calls": mean([profile_value(p, "insertion_scheduler_cpu", "calls") for p in run_profiles]),
            "insertion_scheduler_cpu_requests": mean([profile_value(p, "insertion_scheduler_cpu", "units") for p in run_profiles]),
            "insertion_scheduler_cpu_ms": mean([profile_value(p, "insertion_scheduler_cpu", "total_ms") for p in run_profiles]),
            "route_scheduler_cpu_calls": mean([profile_value(p, "route_scheduler_cpu", "calls") for p in run_profiles]),
            "route_scheduler_cpu_work": mean([profile_value(p, "route_scheduler_cpu", "units") for p in run_profiles]),
            "route_scheduler_cpu_ms": mean([profile_value(p, "route_scheduler_cpu", "total_ms") for p in run_profiles]),
            "population_update_ms": mean([profile_value(p, "population_update", "total_ms") for p in run_profiles]),
            "selection_init_ms": mean([profile_value(p, "insertion_selection_initialization", "total_ms") for p in run_profiles]),
            "selection_repair_ms": mean([profile_value(p, "insertion_selection_repair", "total_ms") for p in run_profiles]),
            "selection_local_search_ms": mean([profile_value(p, "insertion_selection_local_search", "total_ms") for p in run_profiles]),
            "dispatch_cpu_incremental_calls": mean([profile_value(p, "dispatch_cpu_incremental", "calls") for p in run_profiles]),
            "dispatch_cpu_batch_calls": mean([profile_value(p, "dispatch_cpu_batch", "calls") for p in run_profiles]),
            "dispatch_cuda_batch_calls": mean([profile_value(p, "dispatch_cuda_batch", "calls") for p in run_profiles]),
        }

        best_nv = min(runs_nv)
        best_td = min(runs_td)
        best_tc = min(runs_tc)
        # Best NV = fewest vehicles run; best TD at that NV for lexicographic context
        best_nv_indices = [i for i, nv in enumerate(runs_nv) if nv == best_nv]
        best_td_at_best_nv = min(runs_td[i] for i in best_nv_indices)
        
        feasible_runs = sum(1 for item in run_feasibility if item["feasible"])
        max_check_abs_diff = max(
            abs(item["check_diff"]) for item in run_feasibility if item["check_diff"] is not None
        ) if any(item["check_diff"] is not None for item in run_feasibility) else math.nan

        paper_td = target["target_distance"]
        paper_nv = target["target_vehicles"]
        has_paper_target = paper_nv >= 0 and math.isfinite(paper_td) and paper_td > 0
        paper_nv_indices = [i for i, nv in enumerate(runs_nv) if has_paper_target and nv == paper_nv]
        best_td_at_paper_nv = (
            min(runs_td[i] for i in paper_nv_indices)
            if paper_nv_indices else math.nan
        )
        same_vehicle_gap_pct = (
            ((best_td_at_paper_nv - paper_td) / paper_td) * 100.0
            if paper_nv_indices and paper_td > 0 else math.nan
        )
        gap_avg_pct = ((avg_td - paper_td) / paper_td) * 100.0 if has_paper_target else math.nan
        gap_best_pct = ((best_td - paper_td) / paper_td) * 100.0 if has_paper_target else math.nan

        # Vehicle gap vs paper (positive = more vehicles than paper)
        avg_nv_gap = avg_nv - paper_nv if has_paper_target else math.nan
        best_nv_gap = best_nv - paper_nv if has_paper_target else math.nan

        # Distance gap at same/best NV context
        gap_best_nv_td_pct = ((best_td_at_best_nv - paper_td) / paper_td) * 100.0 if paper_td > 0 else math.nan

        results.append({
            "benchmark_schema_version": BENCHMARK_SCHEMA_VERSION,
            "architecture": "full_gpu" if config.mode == "full_gpu" else args.architecture,
            "objective": getattr(args, "objective", "weighted"),
            "config": config.label,
            "benchmark_mode": config.mode,
            "compute_backend": config.compute_backend,
            "solver_exe": str(_resolve_solver_exe(config).name),
            "workers": config.workers,
            "gpu_route_min_batch": config.gpu_route_min_batch,
            "gpu_route_min_work": config.gpu_route_min_work,
            "gpu_insertion_min_batch": config.gpu_insertion_min_batch,
            "gpu_batched_insertion": config.gpu_batched_insertion,
            "gpu_solution_eval": not config.no_gpu_solution_eval,
            "gpu_serialize_workers": args.gpu_serialize_workers,
            "gpu_request_broker": args.gpu_request_broker,
            "execution_policy": args.execution_policy,
            "gpu_solution_verify_interval": args.gpu_solution_verify_interval,
            "instance": target["instance"],
            "paper_nv": paper_nv,
            "paper_td": paper_td,
            "avg_nv": avg_nv,
            "avg_td": avg_td,
            "avg_tc": avg_tc,
            "best_nv": best_nv,
            "best_td": best_td,
            "best_tc": best_tc,
            "best_td_at_best_nv": best_td_at_best_nv,
            "best_td_at_paper_nv": best_td_at_paper_nv,
            "same_vehicle_runs": len(paper_nv_indices),
            "same_vehicle_gap_pct": same_vehicle_gap_pct,
            "avg_nv_gap": avg_nv_gap,
            "best_nv_gap": best_nv_gap,
            "gap_avg_pct": gap_avg_pct,
            "gap_best_pct": gap_best_pct,
            "gap_best_nv_td_pct": gap_best_nv_td_pct,
            "avg_time": avg_time,
            "feasible_runs": feasible_runs,
            "total_runs": len(run_feasibility),
            "all_feasible": feasible_runs == len(run_feasibility),
            "max_check_abs_diff": max_check_abs_diff,
            **avg_profile,
        })

        nv_gap_str = f"{avg_nv_gap:+.1f}NV" if not math.isnan(avg_nv_gap) else "n/a"
        print(
            f"   Done in {sum(runs_time):.2f}s | Avg NV={avg_nv:.1f}({nv_gap_str}) "
            f"TD={avg_td:.2f} (Gap {format_optional_float(gap_avg_pct, '%', 2)}) | "
            f"Best TD={best_td:.2f} (Gap {format_optional_float(gap_best_pct, '%', 2)})\n",
            flush=True,
        )

    return results

def write_csv_report(path, args, results):
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "benchmark_schema_version",
        "output_tag",
        "architecture",
        "objective",
        "benchmark_mode",
        "compute_backend",
        "solver_exe",
        "gpu_batched_insertion",
        "gpu_solution_eval",
        "gpu_serialize_workers",
        "gpu_request_broker",
        "execution_policy",
        "gpu_solution_verify_interval",
        "repeats",
        "max_iter",
        "pop_size",
        "config",
        "workers",
        "gpu_route_min_batch",
        "gpu_route_min_work",
        "gpu_insertion_min_batch",
        "instance",
        "paper_nv",
        "paper_td",
        "avg_nv",
        "avg_td",
        "avg_tc",
        "best_nv",
        "best_td",
        "best_tc",
        "best_td_at_best_nv",
        "best_td_at_paper_nv",
        "same_vehicle_runs",
        "same_vehicle_gap_pct",
        "avg_nv_gap",
        "best_nv_gap",
        "feasible_runs",
        "total_runs",
        "all_feasible",
        "max_check_abs_diff",
        "gap_avg_pct",
        "gap_best_pct",
        "gap_best_nv_td_pct",
        "avg_time",
        "cpu_baseline_time",
        "speedup_vs_cpu",
        "time_delta_vs_cpu_pct",
        "td_delta_vs_cpu",
        "feasibility_batch_calls",
        "feasibility_batch_units",
        "feasibility_batch_avg_size",
        "insertion_batch_calls",
        "insertion_batch_requests",
        "insertion_batch_avg_size",
        "insertion_broker_submissions",
        "insertion_broker_requests",
        "cuda_insertion_cpu_fallback_calls",
        "cuda_insertion_cpu_fallback_requests",
        "cuda_eval_alloc_ms",
        "cuda_eval_h2d_calls",
        "cuda_eval_h2d_bytes",
        "cuda_eval_h2d_ms",
        "cuda_eval_kernel_calls",
        "cuda_eval_kernel_ms",
        "cuda_eval_d2h_bytes",
        "cuda_eval_d2h_ms",
        "cuda_route_cpu_fallback_calls",
        "cuda_route_cpu_fallback_work",
        "cuda_insertion_alloc_ms",
        "cuda_insertion_h2d_calls",
        "cuda_insertion_h2d_bytes",
        "cuda_insertion_h2d_ms",
        "cuda_insertion_kernel_calls",
        "cuda_insertion_kernel_ms",
        "cuda_insertion_d2h_bytes",
        "cuda_insertion_d2h_ms",
        "insertion_scheduler_cpu_calls",
        "insertion_scheduler_cpu_requests",
        "insertion_scheduler_cpu_ms",
        "route_scheduler_cpu_calls",
        "route_scheduler_cpu_work",
        "route_scheduler_cpu_ms",
        "population_update_ms",
        "selection_init_ms",
        "selection_repair_ms",
        "selection_local_search_ms",
        "dispatch_cpu_incremental_calls",
        "dispatch_cpu_batch_calls",
        "dispatch_cuda_batch_calls",
    ]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for result in results:
            row = {
                "output_tag": args.output_tag,
                "repeats": args.repeats,
                "max_iter": args.max_iter,
                "pop_size": args.pop_size,
                **result,
            }
            writer.writerow({name: csv_value(row.get(name, "")) for name in fieldnames})

def comparison_config_keys(configs):
    mode_counts = {}
    for config in configs:
        mode_counts[config.mode] = mode_counts.get(config.mode, 0) + 1

    mode_indices = {}
    keys = []
    for config in configs:
        mode_indices[config.mode] = mode_indices.get(config.mode, 0) + 1
        if mode_counts[config.mode] == 1:
            key = config.mode
        else:
            key = f"{config.mode}_{mode_indices[config.mode]}"
        keys.append((config, key))
    return keys

def write_comparison_csv(path, configs, results):
    path.parent.mkdir(parents=True, exist_ok=True)
    keyed_configs = comparison_config_keys(configs)
    result_lookup = {(r["config"], r["instance"].lower()): r for r in results}
    instance_order = list(dict.fromkeys(r["instance"] for r in results))

    fieldnames = ["instance", "paper_nv", "paper_td"]
    for _, key in keyed_configs:
        fieldnames.extend([
            f"{key}_nv",
            f"{key}_td",
            f"{key}_td_gap_pct",
            f"{key}_time_sec",
            f"{key}_feasible_runs",
            f"{key}_max_check_diff",
            f"{key}_speedup_vs_cpu",
        ])

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for instance in instance_order:
            instance_key = instance.lower()
            first = next(r for r in results if r["instance"].lower() == instance_key)
            row = {
                "instance": first["instance"],
                "paper_nv": first["paper_nv"],
                "paper_td": first["paper_td"],
            }
            for config, key in keyed_configs:
                result = result_lookup.get((config.label, instance_key))
                if result is None:
                    continue
                row.update({
                    f"{key}_nv": result["best_nv"],
                    f"{key}_td": result["best_td"],
                    f"{key}_td_gap_pct": result["gap_best_pct"],
                    f"{key}_time_sec": result["avg_time"],
                    f"{key}_feasible_runs": f"{result['feasible_runs']}/{result['total_runs']}",
                    f"{key}_max_check_diff": result["max_check_abs_diff"],
                    f"{key}_speedup_vs_cpu": result["speedup_vs_cpu"],
                })
            writer.writerow({name: csv_value(row.get(name, "")) for name in fieldnames})

def annotate_cpu_relative_metrics(results):
    cpu_by_instance_workers = {}
    cpu_by_instance = {}

    for result in results:
        if result["compute_backend"] != "cpu":
            continue
        instance_key = result["instance"].lower()
        worker_key = (instance_key, result["workers"])
        cpu_by_instance_workers.setdefault(worker_key, result)
        cpu_by_instance.setdefault(instance_key, result)

    for result in results:
        instance_key = result["instance"].lower()
        baseline = cpu_by_instance_workers.get((instance_key, result["workers"]))
        if baseline is None:
            baseline = cpu_by_instance.get(instance_key)

        if baseline is None or baseline["avg_time"] <= 0.0:
            result["cpu_baseline_time"] = math.nan
            result["speedup_vs_cpu"] = math.nan
            result["time_delta_vs_cpu_pct"] = math.nan
            result["td_delta_vs_cpu"] = math.nan
            continue

        cpu_time = baseline["avg_time"]
        result["cpu_baseline_time"] = cpu_time
        result["speedup_vs_cpu"] = cpu_time / result["avg_time"] if result["avg_time"] > 0.0 else math.nan
        result["time_delta_vs_cpu_pct"] = ((result["avg_time"] - cpu_time) / cpu_time) * 100.0
        result["td_delta_vs_cpu"] = result["avg_td"] - baseline["avg_td"]

def format_optional_float(value, suffix="", precision=3):
    if isinstance(value, float) and math.isnan(value):
        return "n/a"
    return f"{value:.{precision}f}{suffix}"

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Run C++ solver benchmarks.")
    parser.add_argument("--instances", type=str, nargs="+", default=DEFAULT_INSTANCES, help="Instances to benchmark.")
    parser.add_argument("--repeats", type=int, default=30, help="Number of repeats per instance.")
    parser.add_argument("--max_iter", type=int, default=1000, help="PH-SHOWOA iterations per solver run.")
    parser.add_argument("--pop_size", type=int, default=30, help="Population size per solver run.")
    parser.add_argument("--k_init", type=int, default=None, help="Construction candidate count passed to the C++ solver; omit to use the instance-size default.")
    parser.add_argument("--compute_backend", type=str, default="auto", choices=["auto", "cpu", "cuda"], help="C++ compute backend.")
    parser.add_argument("--architecture", type=str, default="legacy", choices=["legacy", "hybrid_v2", "full_gpu"], help="Solver architecture mode.")
    parser.add_argument("--workers", type=int, default=0, help="OpenMP worker setting passed to the C++ solver.")
    parser.add_argument("--worker_values", type=int, nargs="+", default=None, help="Optional sweep of OpenMP worker values.")
    parser.add_argument("--gpu_batched_insertion", action="store_true", help="Enable the C++ batched insertion scoring path.")
    parser.add_argument("--gpu_route_min_batch", type=int, default=128, help="Minimum route/eval batch size before CUDA route-batch evaluation is used.")
    parser.add_argument("--gpu_route_min_batches", type=int, nargs="+", default=None, help="Optional sweep of route-batch CUDA threshold values.")
    parser.add_argument("--gpu_route_min_work", type=int, default=0, help="Route-work threshold (routes * max route length) that may independently trigger CUDA evaluation. Use 0 to disable this work-based override.")
    parser.add_argument("--gpu_route_min_works", type=int, nargs="+", default=None, help="Optional sweep of route-batch CUDA work thresholds.")
    parser.add_argument("--gpu_insertion_min_batch", type=int, default=128, help="Minimum insertion batch size before CUDA is used.")
    parser.add_argument("--gpu_insertion_min_batches", type=int, nargs="+", default=None, help="Optional sweep of insertion CUDA threshold values.")
    parser.add_argument("--gpu_serialize_workers", action="store_true", help="Force CUDA backend worker serialization.")
    parser.add_argument("--gpu_request_broker", action="store_true", help="Enable the experimental cross-worker CUDA request broker (off by default).")
    parser.add_argument("--execution_policy", choices=["legacy", "adaptive", "cuda_force"], default="adaptive", help="Hybrid execution policy passed to the solver.")
    parser.add_argument("--gpu_solution_verify_interval", type=int, default=0, help="Periodically verify the full population on CUDA; zero disables verification.")
    parser.add_argument("--no_gpu_solution_eval", action="store_true", help="Disable C++ whole-solution CUDA evaluation.")
    parser.add_argument(
        "--benchmark_modes",
        type=str,
        nargs="+",
        choices=sorted(BENCHMARK_MODE_PRESETS.keys()),
        default=None,
        help=(
            "Optional backend mode sweep. Modes: cpu, cuda_baseline, "
            "cuda_no_solution_eval, cuda_batched, full_gpu. When omitted, the explicit "
            "--compute_backend/--gpu_batched_insertion/--no_gpu_solution_eval flags are used."
        ),
    )
    parser.add_argument("--profile", action="store_true", help="Enable solver profiling and parse profile counters into the report.")
    parser.add_argument("--output_tag", type=str, default=None, help="Directory name under batch_results.")
    parser.add_argument(
        "--objective",
        type=str,
        default="weighted",
        choices=["weighted", "lexicographic"],
        help="Objective mode passed to the C++ solver: weighted (default) uses d_cost + unit*dist; lexicographic minimizes (NV, distance) in priority order.",
    )
    parser.add_argument("--num_islands", type=int, default=1, help="Number of islands for the Island Model (C++).")
    parser.add_argument("--migration_interval", type=int, default=50, help="Migration interval between islands.")
    parser.add_argument("--migration_size", type=int, default=1, help="Number of individuals migrating per step.")
    parser.add_argument("--migration_mode", type=str, default="tournament", choices=["ring", "broadcast", "tournament"], help="Island migration mode.")
    args = parser.parse_args()
    if args.architecture in {"hybrid_v2", "full_gpu"} or (
        args.benchmark_modes and "full_gpu" in args.benchmark_modes
    ):
        args.objective = "lexicographic"
    if args.output_tag is None:
        backend_tag = args.compute_backend
        batch_tag = "_batched_insert" if args.gpu_batched_insertion else ""
        sweep_tag = ""
        if args.worker_values or args.gpu_route_min_batches or args.gpu_route_min_works or args.gpu_insertion_min_batches or args.benchmark_modes:
            sweep_tag = "_sweep"
        args.output_tag = f"cpp_paper_run_{args.repeats}r_{args.max_iter}it_{backend_tag}_{args.architecture}{batch_tag}{sweep_tag}"

    print(
        f"Starting C++ Benchmark Suite (repeats={args.repeats}, max_iter={args.max_iter}, "
        f"pop_size={args.pop_size}, backend={args.compute_backend})...",
        flush=True
    )
    targets = load_targets()
    try:
        args.instances = validate_requested_instances(args.instances, targets)
    except ValueError as exc:
        parser.error(str(exc))
    configs = build_configs(args)
    results = []
    for config in configs:
        results.extend(run_benchmark_config(args, config, targets))
    annotate_cpu_relative_metrics(results)

    csv_path = ROOT / "C++_paper_benchmark_results.csv"
    artifact_csv_path = ROOT / "batch_results" / args.output_tag / "summary.csv"
    comparison_csv_path = ROOT / "C++_paper_benchmark_comparison.csv"
    artifact_comparison_csv_path = ROOT / "batch_results" / args.output_tag / "comparison.csv"
    write_csv_report(csv_path, args, results)
    try:
        write_csv_report(artifact_csv_path, args, results)
    except PermissionError:
        artifact_csv_path = artifact_csv_path.with_name("summary_latest.csv")
        print(
            "Warning: summary.csv is locked; writing the current long-form results "
            f"to {artifact_csv_path.name} instead.",
            flush=True,
        )
        write_csv_report(artifact_csv_path, args, results)
    write_comparison_csv(comparison_csv_path, configs, results)
    write_comparison_csv(artifact_comparison_csv_path, configs, results)
        
    # Write Markdown Report
    report_path = ROOT / "C++_paper_benchmark_results.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(f"# C++ PH-SHOWOA Benchmark Results with Paper Flags ({args.repeats} repeats, pop_size={args.pop_size}, max_iter={args.max_iter})\n\n")
        f.write("Below are the performance and quality targets compared against the paper benchmarks.\n\n")
        f.write(f"- Compute backend: `{args.compute_backend}`\n")
        f.write(f"- Architecture: `{args.architecture}`\n")
        f.write(f"- Objective: `{args.objective}`\n")
        f.write(f"- Benchmark modes: `{args.benchmark_modes or ['manual']}`\n")
        f.write(f"- Worker values: `{[c.workers for c in configs]}`\n")
        f.write(f"- Manual GPU batched insertion flag: `{'on' if args.gpu_batched_insertion else 'off'}`\n")
        f.write(f"- GPU route min batches: `{[c.gpu_route_min_batch for c in configs]}`\n")
        f.write(f"- GPU route min work: `{[c.gpu_route_min_work for c in configs]}`\n")
        f.write(f"- GPU insertion min batches: `{[c.gpu_insertion_min_batch for c in configs]}`\n")
        f.write(f"- GPU serialize workers: `{'on' if args.gpu_serialize_workers else 'off'}`\n")
        f.write(f"- GPU request broker: `{'on' if args.gpu_request_broker else 'off'}`\n")
        f.write(f"- Execution policy: `{args.execution_policy}`\n")
        f.write(f"- GPU solution verify interval: `{args.gpu_solution_verify_interval}`\n")
        f.write(f"- Manual GPU solution evaluation flag: `{'off' if args.no_gpu_solution_eval else 'on'}`\n")
        f.write(f"- Profiling: `{'on' if args.profile else 'off'}`\n")
        f.write(f"- Output tag: `{args.output_tag}`\n")
        if getattr(args, "num_islands", 1) > 1:
            f.write(f"- Island Model: `{args.num_islands}` islands (interval: {args.migration_interval}, size: {args.migration_size}, mode: {args.migration_mode})\n")
        f.write("\n")
        f.write(f"- CSV summary: `{csv_path.name}`\n")
        f.write(f"- Artifact CSV summary: `{artifact_csv_path.relative_to(ROOT)}`\n\n")
        f.write(f"- Deduplicated comparison CSV: `{comparison_csv_path.name}`\n")
        f.write(f"- Artifact comparison CSV: `{artifact_comparison_csv_path.relative_to(ROOT)}`\n\n")
        f.write("## Benchmark Configurations\n\n")
        f.write("| Config | Mode | Backend | Batched Insertion | Solution Eval | Request Broker | Workers | Route Min Batch | Route Min Work | Insertion Min Batch |\n")
        f.write("| :--- | :--- | :---: | :---: | :---: | :---: | ---: | ---: | ---: | ---: |\n")
        for c in configs:
            f.write(
                f"| `{c.label}` | `{c.mode}` | `{c.compute_backend}` | "
                f"{'on' if c.gpu_batched_insertion else 'off'} | "
                f"{'on' if not c.no_gpu_solution_eval else 'off'} | "
                f"{'on' if args.gpu_request_broker else 'off'} | "
                f"{c.workers} | {c.gpu_route_min_batch} | {c.gpu_route_min_work} | {c.gpu_insertion_min_batch} |\n"
            )
        f.write("\n## Quality Summary\n\n")
        keyed_configs = comparison_config_keys(configs)
        result_lookup = {(r["config"], r["instance"].lower()): r for r in results}
        instance_order = list(dict.fromkeys(r["instance"] for r in results))
        header = "| Instance | Paper NV | Paper TD |"
        alignment = "| :--- | ---: | ---: |"
        for _, key in keyed_configs:
            header += f" {key} Best NV | {key} TD@BestNV | {key} Same-NV Gap | {key} Time | {key} Feasible | {key} Speedup |"
            alignment += " ---: | ---: | ---: | ---: | :---: | ---: |"
        f.write(header + "\n")
        f.write(alignment + "\n")

        for instance in instance_order:
            instance_key = instance.lower()
            first = next(r for r in results if r["instance"].lower() == instance_key)
            paper_nv_text = str(first["paper_nv"]) if first["paper_nv"] >= 0 else "n/a"
            paper_td_text = format_optional_float(first["paper_td"], precision=2)
            row = f"| **{first['instance']}** | {paper_nv_text} | {paper_td_text} |"
            for config, _ in keyed_configs:
                result = result_lookup.get((config.label, instance_key))
                if result is None:
                    row += " n/a | n/a | n/a | n/a | n/a | n/a |"
                    continue
                same_nv_gap = (
                    f"{result['same_vehicle_gap_pct']:+.2f}% ({result['same_vehicle_runs']} runs)"
                    if not math.isnan(result['same_vehicle_gap_pct'])
                    else "n/a (NV mismatch)"
                )
                row += (
                    f" {result['best_nv']} | {result['best_td_at_best_nv']:.2f} | {same_nv_gap} | "
                    f"{result['avg_time']:.3f}s | {result['feasible_runs']}/{result['total_runs']} | "
                    f"{format_optional_float(result['speedup_vs_cpu'], 'x', 3)} |"
                )
            f.write(row + "\n")
        if args.profile:
            f.write("\n## Profile Summary\n\n")
            for config in configs:
                f.write(f"### `{config.label}`\n\n")
                f.write("| Instance | Route/Eval Batch Calls | Route/Eval Units | Route/Eval Avg Batch | CUDA Dispatch Calls | Route CPU Fallback Calls | Route CPU Fallback Work | Route Scheduler CPU Calls | Route Scheduler CPU Work | Route Scheduler CPU ms | Broker Submissions | Broker Requests | Insert Batch Calls | Insert Requests | Avg Insert Batch | CPU Fallback Calls | CPU Fallback Requests | Eval Alloc ms | Eval H2D ms | Eval Kernel Calls | Eval Kernel ms | Eval D2H ms | Insert Alloc ms | Insert H2D ms | Insert Kernel Calls | Insert Kernel ms | Insert D2H ms | Population Update ms |\n")
                f.write("| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |\n")
                for r in results:
                    if r["config"] != config.label:
                        continue
                    f.write(
                        f"| **{r['instance']}** | "
                        f"{r['feasibility_batch_calls']:.0f} | {r['feasibility_batch_units']:.0f} | {r['feasibility_batch_avg_size']:.2f} | "
                        f"{r['dispatch_cuda_batch_calls']:.0f} | "
                        f"{r['cuda_route_cpu_fallback_calls']:.0f} | {r['cuda_route_cpu_fallback_work']:.0f} | "
                        f"{r['route_scheduler_cpu_calls']:.0f} | {r['route_scheduler_cpu_work']:.0f} | {r['route_scheduler_cpu_ms']:.3f} | "
                        f"{r['insertion_broker_submissions']:.0f} | {r['insertion_broker_requests']:.0f} | "
                        f"{r['insertion_batch_calls']:.0f} | {r['insertion_batch_requests']:.0f} | {r['insertion_batch_avg_size']:.2f} | "
                        f"{r['cuda_insertion_cpu_fallback_calls']:.0f} | {r['cuda_insertion_cpu_fallback_requests']:.0f} | "
                        f"{r['cuda_eval_alloc_ms']:.3f} | {r['cuda_eval_h2d_ms']:.3f} | {r['cuda_eval_kernel_calls']:.0f} | {r['cuda_eval_kernel_ms']:.3f} | {r['cuda_eval_d2h_ms']:.3f} | "
                        f"{r['cuda_insertion_alloc_ms']:.3f} | "
                        f"{r['cuda_insertion_h2d_ms']:.3f} | {r['cuda_insertion_kernel_calls']:.0f} | {r['cuda_insertion_kernel_ms']:.3f} | {r['cuda_insertion_d2h_ms']:.3f} | "
                        f"{r['population_update_ms']:.3f} |\n"
                    )
                f.write("\n")
            
    print(f"\nAll instances completed! Report written to: {report_path}", flush=True)
    print(f"CSV summaries written to: {csv_path} and {artifact_csv_path}", flush=True)
    print(f"Deduplicated comparison CSVs written to: {comparison_csv_path} and {artifact_comparison_csv_path}", flush=True)

if __name__ == "__main__":
    main()
