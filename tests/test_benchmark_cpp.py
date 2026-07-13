import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

from scripts.benchmark_cpp import (
    BenchmarkConfig,
    build_run_fingerprint,
    load_targets,
    validate_requested_instances,
)


class BenchmarkIntegrityTest(unittest.TestCase):
    def test_instance_resolution_rejects_case_insensitive_duplicates(self):
        targets = load_targets()
        with self.assertRaisesRegex(ValueError, "Duplicate benchmark instances"):
            validate_requested_instances(["RCdp205", "rcdp205"], targets)

    def test_default_instance_set_resolves_to_sixteen_unique_targets(self):
        from scripts.benchmark_cpp import DEFAULT_INSTANCES

        resolved = validate_requested_instances(DEFAULT_INSTANCES, load_targets())
        self.assertEqual(len(resolved), 16)
        self.assertEqual(len({name.lower() for name in resolved}), 16)

    def test_liu_tang_yao_instances_are_discovered(self):
        targets = load_targets()
        resolved = validate_requested_instances(["1000_1", "1000_2"], targets)
        self.assertEqual(resolved, ["1000_1", "1000_2"])
        self.assertTrue(Path(targets["1000_1"]["path"]).is_file())

    def test_fingerprint_changes_when_architecture_changes(self):
        args = SimpleNamespace(
            max_iter=100,
            pop_size=30,
            architecture="legacy",
            objective="weighted",
            num_islands=1,
            migration_interval=50,
            migration_size=1,
            migration_mode="tournament",
            profile=False,
            gpu_serialize_workers=False,
            gpu_request_broker=False,
            execution_policy="legacy",
            gpu_solution_verify_interval=0,
        )
        config = BenchmarkConfig(
            workers=1,
            gpu_route_min_batch=128,
            gpu_route_min_work=0,
            gpu_insertion_min_batch=128,
            label="test",
            mode="manual",
            compute_backend="cpu",
            gpu_batched_insertion=False,
            no_gpu_solution_eval=True,
        )
        executable = Path(sys.executable)
        legacy = build_run_fingerprint("RCdp1001", "instance.vrpsdptw", 42, args, config, executable)
        args.architecture = "hybrid_v2"
        hybrid_v2 = build_run_fingerprint("RCdp1001", "instance.vrpsdptw", 42, args, config, executable)
        self.assertNotEqual(legacy, hybrid_v2)

        args.gpu_request_broker = True
        broker = build_run_fingerprint("RCdp1001", "instance.vrpsdptw", 42, args, config, executable)
        self.assertNotEqual(hybrid_v2, broker)

        args.gpu_request_broker = False
        args.execution_policy = "adaptive"
        adaptive = build_run_fingerprint("RCdp1001", "instance.vrpsdptw", 42, args, config, executable)
        self.assertNotEqual(hybrid_v2, adaptive)

        args.gpu_solution_verify_interval = 25
        verified = build_run_fingerprint("RCdp1001", "instance.vrpsdptw", 42, args, config, executable)
        self.assertNotEqual(adaptive, verified)

        args.k_init = 1
        one_construction = build_run_fingerprint("RCdp1001", "instance.vrpsdptw", 42, args, config, executable)
        args.k_init = 2
        two_constructions = build_run_fingerprint("RCdp1001", "instance.vrpsdptw", 42, args, config, executable)
        self.assertNotEqual(one_construction, two_constructions)


if __name__ == "__main__":
    unittest.main()
