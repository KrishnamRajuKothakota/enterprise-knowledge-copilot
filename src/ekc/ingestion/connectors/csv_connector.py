"""
CSV connector for ticket/ITSM data.
Auto-detects column layout for SriniInfotech tickets and Jira-format CSVs.
"""
import logging
import os
import pandas as pd
from datetime import datetime
from src.ekc.ingestion.connectors.base import SourceConnector, RawDocument
from src.ekc.db.models import SourceType

logger = logging.getLogger(__name__)

# Column name mappings — covers both ticket formats in our corpus
SUMMARY_COLS   = ["summary", "title", "subject", "ticket_title", "short_description"]
DESC_COLS      = ["description", "body", "details", "issue_body", "long_description"]
RESOLVE_COLS   = ["resolution", "resolution_notes", "resolved_notes", "fix"]
CATEGORY_COLS  = ["category", "type", "issue_type", "ticket_type"]
PRIORITY_COLS  = ["priority", "severity"]
STATUS_COLS    = ["status", "state"]
ID_COLS        = ["ticket_id", "id", "issue_id", "key", "incident_id"]


def _find_col(df: pd.DataFrame, candidates: list[str]) -> str | None:
    lower_cols = {c.lower(): c for c in df.columns}
    for c in candidates:
        if c.lower() in lower_cols:
            return lower_cols[c.lower()]
    return None


class CSVConnector(SourceConnector):

    def can_handle(self, path: str) -> bool:
        return path.lower().endswith(".csv")

    def extract(self, path: str) -> list[RawDocument]:
        logger.info(f"Extracting CSV: {path}")
        try:
            df = pd.read_csv(path, dtype=str, keep_default_na=False)
            df = df.fillna("")
            logger.info(f"  {len(df)} rows, columns: {list(df.columns)}")

            # Detect column layout
            id_col       = _find_col(df, ID_COLS)
            summary_col  = _find_col(df, SUMMARY_COLS)
            desc_col     = _find_col(df, DESC_COLS)
            resolve_col  = _find_col(df, RESOLVE_COLS)
            priority_col = _find_col(df, PRIORITY_COLS)
            status_col   = _find_col(df, STATUS_COLS)
            category_col = _find_col(df, CATEGORY_COLS)

            if not summary_col and not desc_col:
                # Fallback: concatenate all columns as text
                logger.warning(f"No standard columns found in {path}, using all columns")
                return self._extract_raw(df, path)

            mtime = datetime.fromtimestamp(os.path.getmtime(path))
            docs = []

            for _, row in df.iterrows():
                parts = []
                ticket_id = row[id_col].strip() if id_col else ""
                if ticket_id:
                    parts.append(f"Ticket ID: {ticket_id}")
                if summary_col and row[summary_col].strip():
                    parts.append(f"Summary: {row[summary_col].strip()}")
                if category_col and row[category_col].strip():
                    parts.append(f"Category: {row[category_col].strip()}")
                if priority_col and row[priority_col].strip():
                    parts.append(f"Priority: {row[priority_col].strip()}")
                if status_col and row[status_col].strip():
                    parts.append(f"Status: {row[status_col].strip()}")
                if desc_col and row[desc_col].strip():
                    parts.append(f"Description: {row[desc_col].strip()}")
                if resolve_col and row[resolve_col].strip():
                    parts.append(f"Resolution: {row[resolve_col].strip()}")

                content = "\n".join(parts)
                if not content.strip():
                    continue

                title = row[summary_col].strip()[:120] if summary_col else f"ticket_{ticket_id}"

                docs.append(RawDocument(
                    title=title,
                    content=content,
                    source_type=SourceType.csv,
                    source_path=path,
                    last_modified=mtime,
                    metadata={
                        "ticket_id": ticket_id,
                        "priority": row[priority_col].strip() if priority_col else "",
                        "status": row[status_col].strip() if status_col else "",
                        "category": row[category_col].strip() if category_col else "",
                    },
                ))

            logger.info(f"  extracted {len(docs)} ticket documents")
            return docs

        except Exception as e:
            logger.error(f"CSV extraction failed for {path}: {e}")
            return []

    def _extract_raw(self, df: pd.DataFrame, path: str) -> list[RawDocument]:
        mtime = datetime.fromtimestamp(os.path.getmtime(path))
        docs = []
        for i, row in df.iterrows():
            content = " | ".join(f"{col}: {val}" for col, val in row.items() if val.strip())
            if content.strip():
                docs.append(RawDocument(
                    title=f"row_{i}",
                    content=content,
                    source_type=SourceType.csv,
                    source_path=path,
                    last_modified=mtime,
                ))
        return docs