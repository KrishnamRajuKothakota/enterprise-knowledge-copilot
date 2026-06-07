"""
Markdown connector for K8s and Docker documentation.
Extracts heading structure from # headers for heading-aware chunking.
"""
import logging
import os
import re
from datetime import datetime
from src.ekc.ingestion.connectors.base import SourceConnector, RawDocument
from src.ekc.db.models import SourceType

logger = logging.getLogger(__name__)

FRONTMATTER_RE = re.compile(r'^---\s*\n.*?\n---\s*\n', re.DOTALL)
HEADING_RE = re.compile(r'^#{1,4}\s+(.+)$', re.MULTILINE)


class MarkdownConnector(SourceConnector):

    def can_handle(self, path: str) -> bool:
        return path.lower().endswith((".md", ".markdown"))

    def extract(self, path: str) -> list[RawDocument]:
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                raw = f.read()

            # Strip YAML frontmatter
            content = FRONTMATTER_RE.sub("", raw).strip()
            if not content or len(content) < 100:
                return []

            # Extract first heading as title
            title_match = HEADING_RE.search(content)
            title = title_match.group(1).strip() if title_match else \
                    os.path.splitext(os.path.basename(path))[0]

            mtime = datetime.fromtimestamp(os.path.getmtime(path))

            return [RawDocument(
                title=title[:500],
                content=content,
                source_type=SourceType.html,   # reuse html type for docs
                source_path=path,
                last_modified=mtime,
                metadata={"heading_path": title, "section_title": title},
            )]
        except Exception as e:
            logger.error(f"Markdown extraction failed for {path}: {e}")
            return []