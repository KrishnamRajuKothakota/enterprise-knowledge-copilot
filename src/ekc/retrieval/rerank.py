"""
Cross-encoder reranker using ms-marco-MiniLM-L-6-v2.
Scores top-15 RRF candidates and returns top-5.
"""
import logging
from sentence_transformers import CrossEncoder
from sqlalchemy.orm import Session
from src.ekc.db.models import Chunk as ChunkModel

logger = logging.getLogger(__name__)

RERANK_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"


class CrossEncoderReranker:

    def __init__(self):
        logger.info(f"Loading cross-encoder: {RERANK_MODEL}")
        self.model = CrossEncoder(RERANK_MODEL)

    def rerank(
        self,
        query: str,
        candidate_chunk_ids: list[str],
        db: Session,
        top_k: int = 5,
    ) -> list[tuple[str, float]]:
        """
        Fetch chunk texts, score with cross-encoder, return top_k.
        Returns [(chunk_id, score), ...] sorted descending.
        """
        if not candidate_chunk_ids:
            return []

        # Fetch chunk texts in one query
        chunks = db.query(ChunkModel).filter(
            ChunkModel.chunk_id.in_(candidate_chunk_ids)
        ).all()

        if not chunks:
            return []

        chunk_map = {c.chunk_id: c.content for c in chunks}

        # Build (query, passage) pairs in candidate order
        pairs = [
            (query, chunk_map.get(cid, ""))
            for cid in candidate_chunk_ids
            if cid in chunk_map
        ]
        valid_ids = [
            cid for cid in candidate_chunk_ids
            if cid in chunk_map
        ]

        if not pairs:
            return []

        scores = self.model.predict(pairs)

        # Zip chunk_ids with scores and sort
        scored = sorted(
            zip(valid_ids, scores),
            key=lambda x: x[1],
            reverse=True,
        )

        logger.debug(
            f"Reranker: {len(pairs)} candidates -> top {top_k} | "
            f"top score: {scored[0][1]:.3f}" if scored else "no results"
        )
        return [(cid, float(score)) for cid, score in scored[:top_k]]


# ── Module-level singleton ────────────────────────────────────────────────────

_reranker = None


def get_reranker() -> CrossEncoderReranker:
    global _reranker
    if _reranker is None:
        _reranker = CrossEncoderReranker()
    return _reranker