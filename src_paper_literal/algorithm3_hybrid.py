from __future__ import annotations

import random
from typing import List, Tuple
from .problem import Problem
from .solution import Solution
from .algorithm4_woa import based_on_woa_update
from .algorithm5_sho import based_on_sho_update


def update_position_hybrid(
    current: Solution,
    best_whale: Solution,
    population: List[Solution],
    p_hybrid: float,
    a: float,
    problem: Problem,
    rng: random.Random,
    mutation_prob: float = 0.35,
) -> Tuple[Solution, bool]:
    """
    Algorithm 3. UPDATE_POSITION_HYBRID (Exploration-Exploitation Control)
    If r < pHybrid: SHO-based diversification (exploration)
    Else: WOA-based intensification (exploitation)
    Returns: (candidate_solution, is_sho_branch)
    """
    r = rng.random()
    if r < p_hybrid:
        candidate = based_on_sho_update(
            hyena=current,
            best_hyena=best_whale,
            population=population,
            problem=problem,
            rng=rng,
            mutation_prob=mutation_prob,
        )
        return candidate, True
    else:
        candidate = based_on_woa_update(
            whale=current,
            best_whale=best_whale,
            a=a,
            problem=problem,
            rng=rng,
        )
        return candidate, False
