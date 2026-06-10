"""
Reciprocal Rank Fusion.
score(d) = SUM weight_i / (60 + rank_i(d))
Weights allow feedback-driven rebalancing between retrieval streams.
Default weights = 1.0 (equal) — preserves original behaviour.
"""
import logging
from collections import defaultdict

logger = logging.getLogger(__name__)
RRF_K = 60


def reciprocal_rank_fusion(
    result_lists: list[list[tuple[str, float]]],
    top_k: int = 15,
    weights: list[float] | None = None,
) -> list[tuple[str, float]]:
    """
    Fuse multiple ranked lists via weighted RRF.
    Each list is [(chunk_id, score), ...] sorted descending.
    weights: per-stream multipliers (default 1.0 each).
    Returns fused [(chunk_id, rrf_score), ...] sorted descending.
    """
    if weights is None:
        weights = [1.0] * len(result_lists)

    # Pad weights if shorter than result_lists
    while len(weights) < len(result_lists):
        weights.append(1.0)

    rrf_scores: dict[str, float] = defaultdict(float)
    for results, weight in zip(result_lists, weights):
        for rank, (chunk_id, _) in enumerate(results, start=1):
            rrf_scores[chunk_id] += weight / (RRF_K + rank)

    fused = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)
    logger.debug(
        f"RRF fusion: {len(fused)} unique candidates -> top {top_k} "
        f"(weights={[round(w,2) for w in weights]})"
    )
    return fused[:top_k]
