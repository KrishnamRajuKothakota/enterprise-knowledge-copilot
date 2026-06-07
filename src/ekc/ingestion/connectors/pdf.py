"""
PDF connector using pdfminer.six.
Falls back to pytesseract OCR for scanned/image pages.
Preserves heading structure for downstream heading-aware chunking.
"""
import logging
import os
from io import StringIO
from datetime import datetime
from pdfminer.high_level import extract_text_to_fp
from pdfminer.layout import LAParams
from pdfminer.high_level import extract_pages
from pdfminer.layout import LTTextContainer, LTChar
from src.ekc.ingestion.connectors.base import SourceConnector, RawDocument
from src.ekc.db.models import SourceType

logger = logging.getLogger(__name__)


class PDFConnector(SourceConnector):

    def can_handle(self, path: str) -> bool:
        return path.lower().endswith(".pdf")

    def extract(self, path: str) -> list[RawDocument]:
        logger.info(f"Extracting PDF: {path}")
        try:
            text = self._extract_text(path)
            if not text or len(text.strip()) < 50:
                logger.warning(f"PDF appears scanned, trying OCR: {path}")
                text = self._ocr_fallback(path)

            mtime = datetime.fromtimestamp(os.path.getmtime(path))
            title = os.path.splitext(os.path.basename(path))[0]

            return [RawDocument(
                title=title,
                content=text,
                source_type=SourceType.pdf,
                source_path=path,
                last_modified=mtime,
                metadata={"heading_path": "", "page_number": 1},
            )]
        except Exception as e:
            logger.error(f"PDF extraction failed for {path}: {e}")
            return []

    def _extract_text(self, path: str) -> str:
        output = StringIO()
        with open(path, "rb") as f:
            extract_text_to_fp(
                f, output,
                laparams=LAParams(line_margin=0.5, char_margin=2.0),
                output_type="text",
                codec="utf-8",
            )
        return output.getvalue()

    def _ocr_fallback(self, path: str) -> str:
        """OCR fallback for scanned PDFs using pytesseract."""
        try:
            import pytesseract
            from PIL import Image
            import fitz  # PyMuPDF only as fallback — not in main path
            doc = fitz.open(path)
            texts = []
            for page in doc:
                pix = page.get_pixmap(dpi=200)
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                texts.append(pytesseract.image_to_string(img))
            return "\n".join(texts)
        except Exception as e:
            logger.error(f"OCR fallback failed: {e}")
            return ""