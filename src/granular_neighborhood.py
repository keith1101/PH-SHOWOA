"""Spatio-Temporal Candidate Lists for Granular Local Search in VRPSPDTW."""

from typing import Dict, List, Set


class GranularNeighborhood:
    """Precomputed Spatio-Temporal Candidate Lists (Vidal 2012, 2022).
    
    Filters local search neighborhoods to the top-K most compatible customer pairs,
    reducing move evaluations by 75-90% and accelerating convergence.
    """

    def __init__(self, data, k: int = 25):
        self.k = k
        self.neighbors: Dict[int, List[int]] = {}
        self.neighbor_sets: Dict[int, Set[int]] = {}
        self._build_candidate_lists(data)

    def _build_candidate_lists(self, data) -> None:
        n = getattr(data, "customer_num", 0)
        if n <= self.k:
            all_cus = list(range(1, n + 1))
            for i in range(1, n + 1):
                neighs = [j for j in all_cus if j != i]
                self.neighbors[i] = neighs
                self.neighbor_sets[i] = set(neighs)
            return

        for i in range(1, n + 1):
            scores = []
            node_i = data.node[i]
            for j in range(1, n + 1):
                if i == j:
                    continue
                node_j = data.node[j]

                d_ij = data.dist[i][j]
                t_ij = data.time[i][j]

                arr_early = node_i.start + node_i.s_time + t_ij
                wait_time = max(0.0, node_j.start - arr_early)
                late_time = max(0.0, arr_early - node_j.end)

                score = d_ij + 0.5 * wait_time + 5.0 * late_time
                scores.append((score, j))

            scores.sort(key=lambda x: x[0])
            top_k = [j for _, j in scores[: self.k]]
            self.neighbors[i] = top_k
            self.neighbor_sets[i] = set(top_k)

    def is_candidate(self, i: int, j: int) -> bool:
        """Returns True if node j is a candidate neighbor of node i, or vice versa."""
        if i not in self.neighbor_sets or j not in self.neighbor_sets:
            return True
        return (j in self.neighbor_sets[i]) or (i in self.neighbor_sets[j])

    def get_neighbors(self, i: int) -> List[int]:
        return self.neighbors.get(i, [])
