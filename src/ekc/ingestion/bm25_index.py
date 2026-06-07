"""
BM25 keyword index using rank_bm25.
- BM25Okapi(k1=1.5, b=0.75) over all chunk texts
- NLTK word_tokenize for tokenisation
- Index serialised to disk (pickle) and reloaded at startup
- Rebuilt on each full ingestion run
"""
import os
import pickle
import logging
from typing import Optional
from rank_bm25 import BM25Okapi
from nltk.tokenize import word_tokenize
from src.ekc.core.config import settings

logger = logging.getLogger(__name__)


class BM25Index:

    K1 = 1.5
    B = 0.75

    def __init__(self):
        self._bm25: Optional[BM25Okapi] = None
        self._chunk_ids: list[str] = []
        self._corpus_texts: list[str] = []
        self._load_from_disk()

    def _tokenize(self, text: str) -> list[str]:
        return word_tokenize(text.lower())

    def _load_from_disk(self):
        path = settings.bm25_index_path
        if os.path.exists(path):
            logger.info(f"Loading BM25 index from {path}")
            with open(path, "rb") as f:
                data = pickle.load(f)
            self._bm25 = data["bm25"]
            self._chunk_ids = data["chunk_ids"]
            self._corpus_texts = data.get("corpus_texts", [])
            logger.info(f"  loaded {len(self._chunk_ids)} documents")

    def build(self, texts: list[str], chunk_ids: list[str]):
        """
        Build BM25 index from scratch over all chunks.
        Called at the end of each full ingestion run.
        """
        logger.info(f"Building BM25 index over {len(texts)} documents")
        tokenized = [self._tokenize(t) for t in texts]
        self._bm25 = BM25Okapi(tokenized, k1=self.K1, b=self.B)
        self._chunk_ids = chunk_ids
        self._corpus_texts = texts
        logger.info("BM25 index built")

    def add(self, texts: list[str], chunk_ids: list[str]):
        """
        Incremental add — rebuilds index including new texts.
        For the hackathon corpus size this is fast enough.
        """
        self._corpus_texts.extend(texts)
        self._chunk_ids.extend(chunk_ids)
        self.build(self._corpus_texts, self._chunk_ids)

    def search(self, query: str, top_k: int = 5) -> list[tuple[str, float]]:
        """
        Search BM25 index.
        Returns list of (chunk_id, score) sorted descending.
        """
        if self._bm25 is None or not self._chunk_ids:
            return []

        tokens = self._tokenize(query)
        scores = self._bm25.get_scores(tokens)

        # Get top-k indices
        top_indices = sorted(
            range(len(scores)),
            key=lambda i: scores[i],
            reverse=True,
        )[:top_k]

        return [
            (self._chunk_ids[i], float(scores[i]))
            for i in top_indices
            if scores[i] > 0
        ]

    def save(self):
        """Persist index to disk."""
        os.makedirs(os.path.dirname(settings.bm25_index_path), exist_ok=True)
        with open(settings.bm25_index_path, "wb") as f:
            pickle.dump({
                "bm25": self._bm25,
                "chunk_ids": self._chunk_ids,
                "corpus_texts": self._corpus_texts,
            }, f)
        logger.info(f"BM25 index saved: {len(self._chunk_ids)} docs "
                    f"-> {settings.bm25_index_path}")

    @property
    def total_documents(self) -> int:
        return len(self._chunk_ids)


# ── Module-level singleton ────────────────────────────────────────────────────

_bm25_index: Optional[BM25Index] = None


def get_bm25_index() -> BM25Index:
    global _bm25_index
    if _bm25_index is None:
        _bm25_index = BM25Index()
    return _bm25_index