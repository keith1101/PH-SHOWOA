import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

from scripts.benchmark_java import (
    JAVA_PROJECT,
    Target,
    fingerprint,
    load_targets,
    resolve_instances,
)


class BenchmarkJavaIntegrityTest(unittest.TestCase):
    def test_rejects_case_insensitive_duplicates(self):
        with self.assertRaisesRegex(ValueError, "Duplicate benchmark instances"):
            resolve_instances(["RCdp205", "rcdp205"], load_targets())

    def test_default_instances_resolve_to_sixteen_unique_targets(self):
        from scripts.benchmark_java import DEFAULT_INSTANCES

        resolved = resolve_instances(DEFAULT_INSTANCES, load_targets())
        self.assertEqual(16, len(resolved))
        self.assertEqual(16, len({target.instance.lower() for target in resolved}))

    def test_fingerprint_changes_with_solver_configuration(self):
        target = Target("test", Path(__file__), -1, float("nan"))
        args = SimpleNamespace(
            iterations=100, population=30, workers=1, init_moves=20,
            init_temperature=1.0, init_cooling=0.9, init_min_temperature=0.01,
            construction_attempts=200, ls_interval=25, stagnation=50, epsilon=1e-4,
            mutation_probability=0.35, diversification_fraction=0.2,
            diversification_moves=5, java=sys.executable, xmx="1g",
        )
        original = fingerprint(target, 42, args, "source")
        args.workers = 2
        self.assertNotEqual(original, fingerprint(target, 42, args, "source"))
        args.workers = 1
        self.assertNotEqual(original, fingerprint(target, 43, args, "source"))
        self.assertNotEqual(original, fingerprint(target, 42, args, "other-source"))
        self.assertTrue(JAVA_PROJECT.is_dir())


if __name__ == "__main__":
    unittest.main()
