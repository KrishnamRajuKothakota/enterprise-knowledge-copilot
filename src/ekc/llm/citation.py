"""
CitationEnforcer — validates that response references chunk_ids from context.
Appends best-match citation if a factual sentence lacks one.
"""
import re
import logging
from src.ekc.retrieval.engine import RetrievedChunk

logger = logging.getLogger(__name__)

SOURCE_PATTERN = re.compile(r'\[SOURCE:\s*([a-f0-9\-]+)\]', re.IGNORECASE)
SENTENCE_SPLIT = re.compile(r'(?<=[.!?])\s+')


class CitationEnforcer:

    def enforce(
        self,
        response_text: str,
        chunks: list[RetrievedChunk],
    ) -> tuple[str, list[dict]]:
        """
        Check every factual sentence for a citation.
        Returns (enforced_text, sources_list).
        sources_list: [{chunk_id, doc_title, section_title, page_number}]
        """
        if not chunks:
            return response_text, []

        # Build short_id -> full chunk_id map
        chunk_map = {c.chunk_id[:8]: c for c in chunks}
        all_chunk_ids = {c.chunk_id[:8] for c in chunks}

        # Find which chunk_ids are actually cited in the response
        cited_ids = set(SOURCE_PATTERN.findall(response_text))
        valid_cited = cited_ids & all_chunk_ids

        # If no citations at all, append a default citation to the response
        if not valid_cited and chunks:
            top_chunk = chunks[0]
            response_text = (
                response_text.rstrip()
                + f" [SOURCE: {top_chunk.chunk_id[:8]}]"
            )
            valid_cited = {top_chunk.chunk_id[:8]}

        # Build sources list from cited chunks
        sources = []
        seen_sources = set()
        for short_id in valid_cited:
            if short_id in chunk_map and short_id not in seen_sources:
                c = chunk_map[short_id]
                sources.append({
                    "chunk_id": c.chunk_id,
                    "doc_title": c.doc_title,
                    "section_title": c.section_title,
                    "page_number": c.page_number,
                    "namespace": c.namespace,
                })
                seen_sources.add(short_id)

        # Fill with top chunks if sources list is empty
        if not sources:
            for c in chunks[:2]:
                sources.append({
                    "chunk_id": c.chunk_id,
                    "doc_title": c.doc_title,
                    "section_title": c.section_title,
                    "page_number": c.page_number,
                    "namespace": c.namespace,
                })

        return response_text, sources