"""
Abstract base connector. All source connectors implement this interface.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from src.ekc.db.models import SourceType


@dataclass
class RawDocument:
    """Normalised document coming out of any connector."""
    title: str
    content: str
    source_type: SourceType
    source_path: str
    language: str = "en"
    last_modified: Optional[datetime] = None
    metadata: dict = field(default_factory=dict)
    # metadata keys used downstream:
    # heading_path, page_number, section_title, slide_number


class SourceConnector(ABC):

    @abstractmethod
    def can_handle(self, path: str) -> bool:
        """Return True if this connector handles the given file path."""

    @abstractmethod
    def extract(self, path: str) -> list[RawDocument]:
        """
        Extract one or more RawDocuments from the source.
        A single file may produce multiple RawDocuments
        (e.g. one per slide for PPTX, or one per row for CSV tickets).
        """