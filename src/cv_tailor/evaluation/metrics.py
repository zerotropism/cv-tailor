"""Ranking metrics for binary relevance: a CV is relevant to a job or it is not.

Rank correlation is ill-suited here: with relevance in {0, 1}, almost every pair is tied.
"""

import math
from collections.abc import Collection, Sequence


def precision_at(ranked: Sequence[str], relevant: Collection[str], k: int) -> float:
    """Share of relevant CVs among the first k."""
    return sum(name in relevant for name in ranked[:k]) / k


def average_precision(ranked: Sequence[str], relevant: Collection[str]) -> float:
    """Mean of the precision at the rank of each relevant CV; 1.0 when they all come first."""
    if not relevant:
        raise ValueError("average precision needs at least one relevant CV")
    hits, total = 0, 0.0
    for position, name in enumerate(ranked, start=1):
        if name in relevant:
            hits += 1
            total += hits / position
    return total / len(relevant)


def ndcg_at(ranked: Sequence[str], relevant: Collection[str], k: int) -> float:
    """Discounted cumulative gain of the first k, divided by the best achievable."""
    gain = sum(
        1 / math.log2(position + 1)
        for position, name in enumerate(ranked[:k], 1)
        if name in relevant
    )
    ideal = sum(1 / math.log2(position + 1) for position in range(1, min(k, len(relevant)) + 1))
    return gain / ideal


def tied_with_top(scores: Sequence[float]) -> int:
    """How many CVs share the best score: beyond one, their order is the input order."""
    return sum(score == max(scores) for score in scores) if scores else 0
