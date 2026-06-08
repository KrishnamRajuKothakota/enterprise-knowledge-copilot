"""
Hybrid retrieval engine — orchestrates triple fusion retrieval.

Flow:
  1. Check Redis cache
  2. Vector search (FAISS top-5)
  3. BM25 keyword search (top-5)
  4. Knowledge graph traversal (top-5)
  5. Reciprocal Rank Fusion -> top-15 candidates
  6. Cross-encoder reranking -> top-5
  7. RBAC filter
  8. Return ranked chunks with metadata
"""
import logging
from dataclasses import dataclass
from sqlalchemy.orm import Session
from src.ekc.retrieval.vector import VectorRetriever
from src.ekc.retrieval.keyword import KeywordRetriever
from src.ekc.retrieval.graph_retriever import GraphRetriever
from src.ekc.retrieval.fusion import reciprocal_rank_fusion
from src.ekc.retrieval.rerank import get_reranker
from src.ekc.retrieval.cache import get_cache
from src.ekc.retrieval.role_context import get_role_injector
from src.ekc.db.models import Chunk as ChunkModel, Document, UserRole
from src.ekc.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class RetrievedChunk:
    chunk_id: str
    content: str
    score: float
    doc_title: str
    section_title: str
    heading_path: str
    page_number: int
    source_type: str
    namespace: str


class HybridRetrievalEngine:

    def __init__(self, db: Session):
        self.db = db
        self.vector = VectorRetriever()
        self.keyword = KeywordRetriever()
        self.graph = GraphRetriever(db)
        self.reranker = get_reranker()
        self.cache = get_cache()
        self.role_injector = get_role_injector()

    def hybrid_search(
        self,
        query: str,
        user_role: UserRole = UserRole.junior_engineer,
        user_namespace: str | None = None,
        top_k: int = 5,
        use_cache: bool = True,
    ) -> tuple[list[RetrievedChunk], bool]:
        """
        Execute triple-fusion retrieval.
        Returns (chunks, cache_hit).
        """
        # 1. Check cache
        if use_cache:
            cached = self.cache.get(query)
            if cached:
                chunk_ids = [c[0] for c in cached]
                chunk_ids = self.role_injector.filter_by_role(
                    chunk_ids, user_role, user_namespace, self.db
                )
                chunks = self._fetch_chunks(chunk_ids, cached)
                return chunks, True

        # 2-4. Three retrieval streams
        vector_results  = self.vector.search(query, top_k=settings.vector_top_k)
        keyword_results = self.keyword.search(query, top_k=settings.bm25_top_k)
        graph_results   = self.graph.search(query, top_k=settings.graph_top_k)

        logger.info(
            f"Retrieval streams: vector={len(vector_results)}, "
            f"bm25={len(keyword_results)}, graph={len(graph_results)}"
        )

        # 5. Reciprocal Rank Fusion -> top-15 candidates
        fused = reciprocal_rank_fusion(
            [vector_results, keyword_results, graph_results],
            top_k=settings.rerank_top_n,
        )

        if not fused:
            logger.warning(f"No results from any retrieval stream for: {query[:60]}")
            return [], False

        # 6. Cross-encoder reranking -> top-5
        candidate_ids = [cid for cid, _ in fused]
        reranked = self.reranker.rerank(
            query, candidate_ids, self.db, top_k=top_k
        )

        # 7. RBAC filter
        reranked_ids = [cid for cid, _ in reranked]
        allowed_ids = self.role_injector.filter_by_role(
            reranked_ids, user_role, user_namespace, self.db
        )

        # Rebuild score map after RBAC
        score_map = {cid: score for cid, score in reranked}
        final_pairs = [(cid, score_map[cid]) for cid in allowed_ids]

        # 8. Cache the pre-RBAC results (so different roles share the cache)
        if use_cache and reranked:
            self.cache.set(query, reranked)

        # Fetch full chunk objects
        chunks = self._fetch_chunks(allowed_ids, final_pairs)
        return chunks, False

    def _fetch_chunks(
        self,
        chunk_ids: list[str],
        scored_pairs: list[tuple[str, float]],
    ) -> list[RetrievedChunk]:
        """Fetch chunk + document metadata from Postgres."""
        if not chunk_ids:
            return []

        score_map = {cid: score for cid, score in scored_pairs}

        rows = (
            self.db.query(ChunkModel, Document)
            .join(Document, ChunkModel.doc_id == Document.doc_id)
            .filter(ChunkModel.chunk_id.in_(chunk_ids))
            .all()
        )

        # Preserve ranking order
        row_map = {chunk.chunk_id: (chunk, doc) for chunk, doc in rows}
        result = []
        for cid in chunk_ids:
            if cid not in row_map:
                continue
            chunk, doc = row_map[cid]
            result.append(RetrievedChunk(
                chunk_id=cid,
                content=chunk.content,
                score=score_map.get(cid, 0.0),
                doc_title=doc.title,
                section_title=chunk.section_title or "",
                heading_path=chunk.heading_path or "",
                page_number=chunk.page_number or 1,
                source_type=doc.source_type.value,
                namespace=doc.namespace or "",
            ))

        return result


# ── Module-level factory ──────────────────────────────────────────────────────

def get_engine(db: Session) -> HybridRetrievalEngine:
    return HybridRetrievalEngine(db)