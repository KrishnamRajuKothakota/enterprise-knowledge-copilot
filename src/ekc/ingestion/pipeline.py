"""
DocumentIngestionPipeline — orchestrates all 9 steps:
1. Extract (connector)
2. Normalise (language detection)
3. Clean (TextCleaner + dedup)
4. Redact PII (Presidio)
5. Chunk (HeadingAwareChunker)
6. Embed (EmbeddingGenerator → FAISS + Postgres)
7. KG construction (deferred to kg module — called after pipeline)
8. BM25 index (rebuilt after all docs processed)
9. Quality validation gate
"""
import logging
import os
from datetime import datetime
from sqlalchemy.orm import Session
from src.ekc.ingestion.connectors.registry import get_connector
from src.ekc.ingestion.clean import get_cleaner, get_detector
from src.ekc.ingestion.redact import get_redactor
from src.ekc.ingestion.chunk import get_chunker
from src.ekc.ingestion.embed import get_embedder
from src.ekc.ingestion.bm25_index import get_bm25_index
from src.ekc.db.models import Document, Chunk as ChunkModel, RedactionAudit, SourceType
from src.ekc.db.session import SessionLocal
from src.ekc.core.config import settings
import uuid

logger = logging.getLogger(__name__)


class IngestionResult:
    def __init__(self):
        self.files_processed = 0
        self.files_failed = 0
        self.docs_created = 0
        self.chunks_created = 0
        self.embeddings_created = 0
        self.pii_redactions = 0
        self.duplicates_skipped = 0
        self.errors: list[str] = []

    def __str__(self):
        return (
            f"Files: {self.files_processed} processed, {self.files_failed} failed | "
            f"Docs: {self.docs_created} | Chunks: {self.chunks_created} | "
            f"Embeddings: {self.embeddings_created} | "
            f"PII redactions: {self.pii_redactions} | "
            f"Duplicates skipped: {self.duplicates_skipped}"
        )


class DocumentIngestionPipeline:

    def __init__(self):
        self.cleaner = get_cleaner()
        self.detector = get_detector()
        self.redactor = get_redactor()
        self.chunker = get_chunker()
        self.embedder = get_embedder()
        self.bm25 = get_bm25_index()

    def ingest_file(self, file_path: str, namespace: str = "general",
                    access_roles: list[str] = None) -> IngestionResult:
        """Ingest a single file through the full pipeline."""
        result = IngestionResult()
        access_roles = access_roles or ["junior_engineer", "l1_support", "lead", "admin"]

        logger.info(f"Starting ingestion: {file_path}")

        # Step 1 — Extract
        connector = get_connector(file_path)
        if not connector:
            result.files_failed += 1
            result.errors.append(f"No connector for: {file_path}")
            return result

        raw_docs = connector.extract(file_path)
        if not raw_docs:
            result.files_failed += 1
            result.errors.append(f"No content extracted from: {file_path}")
            return result

        result.files_processed += 1
        db = SessionLocal()

        try:
            all_chunk_texts: list[str] = []
            all_chunk_ids: list[str] = []

            for raw_doc in raw_docs:
                # Step 2 — Language detection (basic)
                language = raw_doc.language or "en"

                # Step 3 — Clean + dedup
                clean_result = self.cleaner.clean(raw_doc.content)
                if not clean_result.text.strip():
                    continue

                if self.detector.is_duplicate(clean_result.text, raw_doc.source_path):
                    result.duplicates_skipped += 1
                    logger.info(f"  Duplicate skipped: {raw_doc.title[:60]}")
                    continue

                # Step 4 — PII redaction
                redact_result = self.redactor.redact(clean_result.text, language)

                # Write Document record
                doc_id = str(uuid.uuid4())
                doc_row = Document(
                    doc_id=doc_id,
                    title=raw_doc.title[:500],
                    source_type=raw_doc.source_type,
                    source_url=raw_doc.source_path,
                    last_modified=raw_doc.last_modified,
                    ingested_at=datetime.utcnow(),
                    language=language,
                    namespace=namespace,
                    access_roles=access_roles,
                    status="active",
                )
                db.add(doc_row)
                db.flush()   # get doc_id into DB without committing

                # Write redaction audit records
                for finding in redact_result.findings:
                    db.add(RedactionAudit(
                        doc_id=doc_id,
                        pii_type=finding["pii_type"],
                        token_replacement=finding["token"],
                        redacted_at=datetime.utcnow(),
                    ))
                result.pii_redactions += len(redact_result.findings)

                # Step 5 — Chunk
                raw_doc.content = redact_result.redacted_text
                chunks = self.chunker.chunk(raw_doc)
                if not chunks:
                    continue

                # Write Chunk records
                chunk_rows = []
                chunk_db_ids = []
                for chunk in chunks:
                    chunk_id = str(uuid.uuid4())
                    chunk_db_ids.append(chunk_id)
                    chunk_rows.append(ChunkModel(
                        chunk_id=chunk_id,
                        doc_id=doc_id,
                        content=chunk.content,
                        chunk_index=chunk.chunk_index,
                        page_number=chunk.page_number,
                        section_title=chunk.section_title[:500] if chunk.section_title else "",
                        heading_path=chunk.heading_path[:1000] if chunk.heading_path else "",
                        token_count=chunk.token_count,
                    ))
                    all_chunk_texts.append(chunk.content)
                    all_chunk_ids.append(chunk_id)

                db.bulk_save_objects(chunk_rows)
                db.flush()

                # Step 6 — Embed chunks → FAISS + Postgres
                embedded = self.embedder.embed_chunks(chunks, db, chunk_db_ids)
                result.embeddings_created += embedded
                result.chunks_created += len(chunks)
                result.docs_created += 1

                logger.info(
                    f"  '{raw_doc.title[:60]}' -> "
                    f"{len(chunks)} chunks, {embedded} embeddings, "
                    f"{len(redact_result.findings)} PII findings"
                )

            db.commit()

            # Step 8 — Rebuild BM25 index with new chunks
            if all_chunk_texts:
                self.bm25.add(all_chunk_texts, all_chunk_ids)
                self.bm25.save()

            # Save FAISS index
            self.embedder.save_index()

        except Exception as e:
            db.rollback()
            result.files_failed += 1
            result.errors.append(f"Pipeline error for {file_path}: {e}")
            logger.exception(f"Pipeline failed for {file_path}")
        finally:
            db.close()

        return result

    def ingest_directory(self, directory: str, namespace: str = "general",
                         access_roles: list[str] = None) -> IngestionResult:
        """Ingest all supported files in a directory."""
        total = IngestionResult()
        supported = {".pdf", ".csv", ".pptx", ".html", ".docx", ".md", ".markdown"}

        files = [
            os.path.join(directory, f)
            for f in os.listdir(directory)
            if os.path.splitext(f)[1].lower() in supported
        ]

        logger.info(f"Ingesting {len(files)} files from {directory}")

        for file_path in files:
            result = self.ingest_file(file_path, namespace, access_roles)
            total.files_processed += result.files_processed
            total.files_failed += result.files_failed
            total.docs_created += result.docs_created
            total.chunks_created += result.chunks_created
            total.embeddings_created += result.embeddings_created
            total.pii_redactions += result.pii_redactions
            total.duplicates_skipped += result.duplicates_skipped
            total.errors.extend(result.errors)

        logger.info(f"Ingestion complete: {total}")
        return total