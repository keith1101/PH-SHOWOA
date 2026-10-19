import tempfile
import unittest
from pathlib import Path

from src.argparse_util import ArgumentParser
from src.data import Data
from src.compute_backend import create_backend
from src.eval import _chk_route_list
from src.eval import eval_move
from src.move import Move, Seq
from src.operator import apply_move
from src.search_framework import _make_route, quick_check_feasibility, search_framework
from src.solution import Solution


INSTANCE = """NAME: regression
TYPE: VRPSPDTW
DIMENSION: 3
VEHICLES: 1
DISPATCHINGCOST: 300
UNITCOST: 0.014
CAPACITY: 10
EDGE_WEIGHT_TYPE: EXPLICIT
NODE_SECTION
0,0,0,0,100,0
1,1,1,0,100,0
2,1,1,0,100,0
DISTANCETIME_SECTION
0,0,0,0
0,1,6,6
0,2,1,1
1,0,6,6
1,1,0,0
1,2,1,1
2,0,1,1
2,1,1,1
2,2,0,0
DEPOT_SECTION
0
"""


def build_data(tmp_dir, *args):
    instance = Path(tmp_dir) / "regression.vrpsdptw"
    instance.write_text(INSTANCE, encoding="utf-8")
    parser = ArgumentParser()
    parser.add_argument("--problem", 1, False)
    parser.add_argument("--compute_backend", 1)
    parser.add_argument("--paper_flags")
    parser.add_argument("--pop_size", 1)
    parser.add_argument("--runs", 1)
    parser.add_argument("--max_iter", 1)
    parser.add_argument("--sa_itermax", 1)
    parser.add_argument("--sho")
    parser.parse(["test", "--problem", str(instance), "--compute_backend", "cpu", *args])
    return Data(parser)


class PHShowoaRegressionTest(unittest.TestCase):
    def test_paper_profile_accepts_population_thirty(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            data = build_data(tmp_dir, "--paper_flags")
            self.assertEqual(30, data.p_size)
            self.assertEqual(30, data.runs)
            self.assertEqual(1000, data.max_iter)
            self.assertEqual("sa", data.init)
            self.assertEqual(30, len(data.latin))

    def test_insertion_evaluates_return_to_depot_and_uses_fixed_fitness(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            data = build_data(tmp_dir)
            data.node[data.DC].end = 10.0
            data.backend = create_backend(data, "cpu")
            feasible, costs = data.backend.evaluate_insertions([0, 0], [1])
            self.assertEqual(0, feasible[1])
            self.assertFalse(_chk_route_list([0, 1, 0], data)[0])

            data.node[data.DC].end = 100.0
            feasible, costs = data.backend.evaluate_insertions([0, 0], [2])
            self.assertEqual(1, feasible[1])
            self.assertAlmostEqual(2002.0, costs[1])

    def test_fleet_limit_is_a_solution_constraint(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            data = build_data(tmp_dir)
            solution = Solution(data)
            solution.append(_make_route([1], data))
            solution.append(_make_route([2], data))
            solution.cal_cost(data)
            self.assertFalse(quick_check_feasibility(solution, data))
            self.assertFalse(solution.check(data))

    def test_reversed_sequence_is_scored_as_it_is_applied(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            data = build_data(tmp_dir)
            solution = Solution(data)
            solution.append(_make_route([1, 2], data))
            solution.cal_cost(data)
            before = solution.cost

            move = Move()
            move.r_indice[0] = 0
            move.r_indice[1] = -2
            move.len_1 = 3
            move.seqList_1[0] = Seq(0, 0, 0)
            move.seqList_1[1] = Seq(0, 2, 1)
            move.seqList_1[2] = Seq(0, 3, 3)
            move.len_2 = 0

            self.assertTrue(eval_move(solution, move, data))
            apply_move(solution, move, data)
            solution.cal_cost(data)
            self.assertEqual([0, 2, 1, 0], solution.get(0).node_list)
            self.assertAlmostEqual(solution.cost - before, move.delta_cost)

    def test_explicit_overrides_win_over_paper_defaults(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            data = build_data(tmp_dir, "--paper_flags", "--pop_size", "3", "--runs", "2", "--max_iter", "4")
            self.assertEqual(3, data.p_size)
            self.assertEqual(2, data.runs)
            self.assertEqual(4, data.max_iter)

    def test_paper_mode_smoke_run_returns_a_feasible_solution(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            data = build_data(
                tmp_dir, "--paper_flags", "--pop_size", "1", "--runs", "1",
                "--max_iter", "1", "--sa_itermax", "0",
            )
            data.parallel_workers = 1
            best = Solution(data)
            best.cost = float("inf")
            search_framework(data, best)
            self.assertTrue(quick_check_feasibility(best, data))

    def test_sho_flag_configures_sho_hybrid_mode(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            data = build_data(tmp_dir, "--sho")
            self.assertEqual("sho", data.hybrid_mode)

    def test_sho_mode_smoke_run_returns_a_feasible_solution(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            data = build_data(
                tmp_dir, "--sho", "--paper_flags", "--pop_size", "2", "--runs", "1",
                "--max_iter", "2", "--sa_itermax", "0",
            )
            data.parallel_workers = 1
            best = Solution(data)
            best.cost = float("inf")
            search_framework(data, best)
            self.assertTrue(quick_check_feasibility(best, data))


if __name__ == "__main__":
    unittest.main()
