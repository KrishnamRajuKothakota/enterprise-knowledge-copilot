"""
Reciprocal Rank Fusion.
score(d) = SUM 1 / (60 + rank_i(d))
Parameter-free, robust to score-scale differences between retrievers.
"""
import logging
from collections import defaultdict

logger = logging.getLogger(__name__)

RRF_K = 60


def reciprocal_rank_fusion(
    result_lists: list[list[tuple[str, float]]],
    top_k: int = 15,
) -> list[tuple[str, float]]:
    """
    Fuse multiple ranked lists via RRF.
    Each list is [(chunk_id, score), ...] sorted descending.
    Returns fused [(chunk_id, rrf_score), ...] sorted descending.
    """
    rrf_scores: dict[str, float] = defaultdict(float)

    for results in result_lists:
        for rank, (chunk_id, _) in enumerate(results, start=1):
            rrf_scores[chunk_id] += 1.0 / (RRF_K + rank)

    fused = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)
    logger.debug(f"RRF fusion: {len(fused)} unique candidates -> top {top_k}")
    return fused[:top_k]