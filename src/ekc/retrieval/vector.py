"""FAISS vector retrieval wrapper."""
import logging
import numpy as np
from src.ekc.ingestion.embed import get_embedder

logger = logging.getLogger(__name__)


class VectorRetriever:

    def __init__(self):
        self.embedder = get_embedder()

    def search(self, query: str, top_k: int = 5) -> list[tuple[str, float]]:
        """Returns (chunk_id, score) sorted descending."""
        if self.embedder.total_vectors == 0:
            logger.warning("FAISS index is empty")
            return []
        query_vec = self.embedder.embed_query(query)
        results = self.embedder.search(query_vec, top_k=top_k)
        logger.debug(f"Vector search: {len(results)} hits for '{query[:50]}'")
        return results