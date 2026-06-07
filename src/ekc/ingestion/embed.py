"""
Embedding generator using sentence-transformers/all-MiniLM-L6-v2.
- 384-dimensional vectors, L2-normalised (enables cosine via dot product)
- Batch size 64 on CPU
- Writes to FAISS IndexFlatIP + Postgres EMBEDDING table in one transaction
- FAISS index persisted to disk after each ingestion run
"""
import os
import pickle
import logging
import numpy as np
import faiss
from typing import Optional
from sentence_transformers import SentenceTransformer
from sqlalchemy.orm import Session
from src.ekc.ingestion.chunk import TextChunk
from src.ekc.db.models import Embedding, Chunk as ChunkModel
from src.ekc.core.config import settings

logger = logging.getLogger(__name__)

EMBEDDING_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
BATCH_SIZE = 64


class EmbeddingGenerator:

    def __init__(self):
        logger.info(f"Loading embedding model: {EMBEDDING_MODEL_NAME}")
        self.model = SentenceTransformer(EMBEDDING_MODEL_NAME)
        self.dim = 384
        self._faiss_index: Optional[faiss.IndexFlatIP] = None
        self._chunk_id_map: list[str] = []   # faiss position -> chunk_id
        self._load_or_create_index()

    def _load_or_create_index(self):
        index_path = settings.faiss_index_path
        map_path = index_path + ".map"

        if os.path.exists(index_path) and os.path.exists(map_path):
            logger.info(f"Loading existing FAISS index from {index_path}")
            self._faiss_index = faiss.read_index(index_path)
            with open(map_path, "rb") as f:
                self._chunk_id_map = pickle.load(f)
            logger.info(f"  loaded {self._faiss_index.ntotal} vectors")
        else:
            logger.info("Creating new FAISS IndexFlatIP")
            self._faiss_index = faiss.IndexFlatIP(self.dim)
            self._chunk_id_map = []

    def embed_chunks(
        self,
        chunks: list[TextChunk],
        db: Session,
        chunk_db_ids: list[str],
    ) -> int:
        """
        Embed a list of TextChunks and write to FAISS + Postgres.
        chunk_db_ids: the UUID primary keys of the already-inserted Chunk rows.
        Returns number of embeddings written.
        """
        if not chunks:
            return 0

        texts = [c.content for c in chunks]
        logger.info(f"Embedding {len(texts)} chunks in batches of {BATCH_SIZE}")

        # Generate embeddings
        vectors = self.model.encode(
            texts,
            batch_size=BATCH_SIZE,
            show_progress_bar=len(texts) > 100,
            normalize_embeddings=True,   # L2-normalise → cosine via dot product
            convert_to_numpy=True,
        )

        vectors = vectors.astype(np.float32)

        # Write to FAISS
        start_idx = self._faiss_index.ntotal
        self._faiss_index.add(vectors)

        # Write to Postgres
        embedding_rows = []
        for i, (chunk_id, vec) in enumerate(zip(chunk_db_ids, vectors)):
            faiss_idx = start_idx + i
            self._chunk_id_map.append(chunk_id)
            embedding_rows.append(Embedding(
                chunk_id=chunk_id,
                model_name=EMBEDDING_MODEL_NAME,
                vector=vec.tolist(),
                faiss_index_id=faiss_idx,
            ))

        db.bulk_save_objects(embedding_rows)
        db.commit()

        logger.info(f"  wrote {len(embedding_rows)} embeddings, "
                    f"FAISS total: {self._faiss_index.ntotal}")
        return len(embedding_rows)

    def save_index(self):
        """Persist FAISS index and chunk_id map to disk."""
        os.makedirs(os.path.dirname(settings.faiss_index_path), exist_ok=True)
        faiss.write_index(self._faiss_index, settings.faiss_index_path)
        map_path = settings.faiss_index_path + ".map"
        with open(map_path, "wb") as f:
            pickle.dump(self._chunk_id_map, f)
        logger.info(f"FAISS index saved: {self._faiss_index.ntotal} vectors "
                    f"-> {settings.faiss_index_path}")

    def search(self, query_vector: np.ndarray, top_k: int = 5) -> list[tuple[str, float]]:
        """
        Search FAISS index.
        Returns list of (chunk_id, score) sorted by descending score.
        """
        if self._faiss_index.ntotal == 0:
            return []

        q = query_vector.astype(np.float32).reshape(1, -1)
        # Normalise query for cosine similarity
        faiss.normalize_L2(q)
        scores, indices = self._faiss_index.search(q, top_k)

        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx == -1:
                continue
            chunk_id = self._chunk_id_map[idx]
            results.append((chunk_id, float(score)))
        return results

    def embed_query(self, text: str) -> np.ndarray:
        """Embed a single query string. Used at retrieval time."""
        vec = self.model.encode(
            [text],
            normalize_embeddings=True,
            convert_to_numpy=True,
        )
        return vec[0].astype(np.float32)

    @property
    def total_vectors(self) -> int:
        return self._faiss_index.ntotal


# ── Module-level singleton ────────────────────────────────────────────────────

_generator: Optional[EmbeddingGenerator] = None


def get_embedder() -> EmbeddingGenerator:
    global _generator
    if _generator is None:
        _generator = EmbeddingGenerator()
    return _generator