"""Knowledge graph retrieval wrapper."""
import logging
from sqlalchemy.orm import Session
from src.ekc.kg.traverse import GraphTraverser

logger = logging.getLogger(__name__)


class GraphRetriever:

    def __init__(self, db: Session):
        self.traverser = GraphTraverser(db)

    def search(self, query: str, top_k: int = 5) -> list[tuple[str, float]]:
        """Returns (chunk_id, score) sorted descending."""
        results = self.traverser.retrieve(query, top_k=top_k)
        logger.debug(f"Graph search: {len(results)} hits for '{query[:50]}'")
        return results