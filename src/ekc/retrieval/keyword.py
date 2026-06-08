"""BM25 keyword retrieval wrapper."""
import logging
from src.ekc.ingestion.bm25_index import get_bm25_index

logger = logging.getLogger(__name__)


class KeywordRetriever:

    def __init__(self):
        self.index = get_bm25_index()

    def search(self, query: str, top_k: int = 5) -> list[tuple[str, float]]:
        """Returns (chunk_id, score) sorted descending."""
        if self.index.total_documents == 0:
            logger.warning("BM25 index is empty")
            return []
        results = self.index.search(query, top_k=top_k)
        logger.debug(f"BM25 search: {len(results)} hits for '{query[:50]}'")
        return results