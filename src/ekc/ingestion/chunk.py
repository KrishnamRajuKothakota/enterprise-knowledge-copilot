"""
Heading-aware chunker.
- Detects section boundaries from heading patterns in SOP text
- Uses RecursiveCharacterTextSplitter (512 tokens, 50 overlap)
- Chunks never cross heading boundaries
- Each chunk carries full metadata for retrieval
"""
import re
import logging
from dataclasses import dataclass, field
from typing import Optional
from langchain.text_splitter import RecursiveCharacterTextSplitter
from src.ekc.ingestion.connectors.base import RawDocument

logger = logging.getLogger(__name__)

# Heading patterns — ordered most-specific to least
HEADING_PATTERNS = [
    re.compile(r'^(SOP-IT-\d{3}[:\s].+)$', re.MULTILINE),
    re.compile(r'^(\d+\.\d+\.?\d*\s+[A-Z][^\n]{3,80})$', re.MULTILINE),
    re.compile(r'^(\d+\.\s+[A-Z][^\n]{3,80})$', re.MULTILINE),
    re.compile(r'^(#{1,4}\s+.+)$', re.MULTILINE),
    re.compile(r'^([A-Z][A-Z\s]{4,50})$', re.MULTILINE),
]


@dataclass
class TextChunk:
    content: str
    chunk_index: int
    doc_title: str
    source_path: str
    page_number: int = 1
    section_title: str = ""
    heading_path: str = ""
    token_count: int = 0
    metadata: dict = field(default_factory=dict)


class HeadingAwareChunker:
    """
    Splits documents into chunks respecting heading boundaries.
    For SOP documents: splits at SOP-IT-XXX boundaries first,
    then applies recursive character splitting within each section.
    For ticket documents (short): one chunk per document.
    """

    CHUNK_SIZE = 512       # tokens (approximated as chars/4)
    CHUNK_OVERLAP = 50
    CHARS_PER_TOKEN = 4    # rough approximation

    def __init__(self):
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.CHUNK_SIZE * self.CHARS_PER_TOKEN,
            chunk_overlap=self.CHUNK_OVERLAP * self.CHARS_PER_TOKEN,
            separators=["\n\n", "\n", ". ", " ", ""],
            length_function=len,
        )

    def chunk(self, doc: RawDocument) -> list[TextChunk]:
        if not doc.content or not doc.content.strip():
            return []

        # Short documents (tickets, slides) — one chunk each
        estimated_tokens = len(doc.content) // self.CHARS_PER_TOKEN
        if estimated_tokens <= self.CHUNK_SIZE:
            return [TextChunk(
                content=doc.content.strip(),
                chunk_index=0,
                doc_title=doc.title,
                source_path=doc.source_path,
                page_number=doc.metadata.get("page_number", 1),
                section_title=doc.metadata.get("section_title", ""),
                heading_path=doc.metadata.get("heading_path", ""),
                token_count=estimated_tokens,
                metadata=doc.metadata,
            )]

        # Long documents (SOPs) — split by headings first
        sections = self._split_by_headings(doc.content)
        chunks = []
        chunk_index = 0

        for section_title, section_text, heading_path in sections:
            if not section_text.strip():
                continue

            # Apply recursive splitter within section
            sub_chunks = self.splitter.split_text(section_text)

            for sub in sub_chunks:
                if not sub.strip():
                    continue
                token_count = len(sub) // self.CHARS_PER_TOKEN
                chunks.append(TextChunk(
                    content=sub.strip(),
                    chunk_index=chunk_index,
                    doc_title=doc.title,
                    source_path=doc.source_path,
                    page_number=doc.metadata.get("page_number", 1),
                    section_title=section_title,
                    heading_path=heading_path,
                    token_count=token_count,
                    metadata={**doc.metadata, "section_title": section_title},
                ))
                chunk_index += 1

        logger.debug(f"Chunked '{doc.title}' into {len(chunks)} chunks")
        return chunks

    def _split_by_headings(
        self, text: str
    ) -> list[tuple[str, str, str]]:
        """
        Split text at heading boundaries.
        Returns list of (section_title, section_text, heading_path).
        """
        # Find all heading positions
        heading_positions: list[tuple[int, str]] = []

        for pattern in HEADING_PATTERNS:
            for match in pattern.finditer(text):
                heading_positions.append((match.start(), match.group(1).strip()))

        if not heading_positions:
            return [("", text, "")]

        # Sort by position and deduplicate overlapping matches
        heading_positions.sort(key=lambda x: x[0])
        deduped = [heading_positions[0]]
        for pos, title in heading_positions[1:]:
            if pos > deduped[-1][0] + 5:
                deduped.append((pos, title))

        # Build sections
        sections = []
        heading_stack: list[str] = []

        for i, (pos, title) in enumerate(deduped):
            end = deduped[i + 1][0] if i + 1 < len(deduped) else len(text)
            section_text = text[pos:end]

            # Maintain a heading breadcrumb
            if len(heading_stack) == 0:
                heading_stack.append(title)
            elif self._is_subsection(title, heading_stack[-1]):
                heading_stack.append(title)
            else:
                heading_stack = [title]

            heading_path = " > ".join(heading_stack)
            sections.append((title, section_text, heading_path))

        # Prepend any text before the first heading
        if deduped[0][0] > 0:
            preamble = text[:deduped[0][0]].strip()
            if preamble:
                sections.insert(0, ("Preamble", preamble, "Preamble"))

        return sections

    def _is_subsection(self, title: str, parent: str) -> bool:
        """Heuristic: numbered subsection like '1.2 ...' under '1. ...'"""
        sub = re.match(r'^(\d+)\.(\d+)', title)
        par = re.match(r'^(\d+)\.', parent)
        if sub and par:
            return sub.group(1) == par.group(1)
        return False


# ── Module-level singleton ────────────────────────────────────────────────────

_chunker: Optional[HeadingAwareChunker] = None


def get_chunker() -> HeadingAwareChunker:
    global _chunker
    if _chunker is None:
        _chunker = HeadingAwareChunker()
    return _chunker