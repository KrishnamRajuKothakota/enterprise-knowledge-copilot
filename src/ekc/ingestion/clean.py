"""
Text cleaning pipeline:
1. Unicode NFKC normalisation + encoding artifact fixes
2. Boilerplate removal (headers, footers, nav, copyright)
3. Near-duplicate detection via MinHash LSH (datasketch)
   Jaccard threshold = 0.85, shingle size = 5 tokens
"""
import re
import unicodedata
import logging
from dataclasses import dataclass
from typing import Optional
from datasketch import MinHash, MinHashLSH

logger = logging.getLogger(__name__)

# ── Boilerplate patterns ──────────────────────────────────────────────────────

BOILERPLATE_PATTERNS = [
    re.compile(r'page\s+\d+\s+of\s+\d+', re.IGNORECASE),
    re.compile(r'confidential\s*[-–]\s*internal\s+use\s+only', re.IGNORECASE),
    re.compile(r'©\s*\d{4}.*?(all rights reserved|srini\s*infotech)', re.IGNORECASE),
    re.compile(r'copyright\s+\d{4}', re.IGNORECASE),
    re.compile(r'nasscom[\s\-–]+idealabs[\s\-–]+talentfarm', re.IGNORECASE),
    re.compile(r'^\s*(table of contents|contents)\s*$', re.IGNORECASE | re.MULTILINE),
    re.compile(r'printed\s+on\s+\d{1,2}[/-]\d{1,2}[/-]\d{2,4}', re.IGNORECASE),
    re.compile(r'www\.[a-z0-9\-]+\.(com|in|org|net)\b', re.IGNORECASE),
]

ENCODING_FIXES = [
    ('\u2018', "'"),   # left single quote
    ('\u2019', "'"),   # right single quote
    ('\u201c', '"'),   # left double quote
    ('\u201d', '"'),   # right double quote
    ('\u2013', '-'),   # en dash
    ('\u2014', '-'),   # em dash
    ('\u2026', '...'), # ellipsis
    ('\u00a0', ' '),   # non-breaking space
    ('\ufeff', ''),    # BOM
]


# ── Cleaning result ───────────────────────────────────────────────────────────

@dataclass
class CleanResult:
    text: str
    boilerplate_removed: int = 0
    encoding_fixes: int = 0


# ── Text normaliser ───────────────────────────────────────────────────────────

class TextCleaner:

    def clean(self, text: str) -> CleanResult:
        if not text:
            return CleanResult(text="")

        fixes = 0

        # 1. NFKC unicode normalisation
        text = unicodedata.normalize("NFKC", text)

        # 2. Encoding artifact fixes
        for bad, good in ENCODING_FIXES:
            if bad in text:
                text = text.replace(bad, good)
                fixes += 1

        # 3. Boilerplate removal
        removed = 0
        for pattern in BOILERPLATE_PATTERNS:
            new_text = pattern.sub("", text)
            if new_text != text:
                removed += 1
                text = new_text

        # 4. Normalise whitespace — collapse multiple spaces/newlines
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = re.sub(r'[ \t]{2,}', ' ', text)
        text = text.strip()

        return CleanResult(
            text=text,
            boilerplate_removed=removed,
            encoding_fixes=fixes,
        )


# ── MinHash LSH deduplicator ──────────────────────────────────────────────────

class DuplicateDetector:
    """
    Near-duplicate detection using MinHash LSH.
    Jaccard similarity threshold = 0.85, shingle size = 5 tokens.
    Maintains an LSH index; call is_duplicate() before adding each document.
    """

    SHINGLE_SIZE = 5
    NUM_PERM = 128
    THRESHOLD = 0.85

    def __init__(self):
        self.lsh = MinHashLSH(
            threshold=self.THRESHOLD,
            num_perm=self.NUM_PERM,
        )
        self._index: dict[str, MinHash] = {}
        self._counter = 0

    def _shingle(self, text: str) -> set[str]:
        tokens = text.lower().split()
        if len(tokens) < self.SHINGLE_SIZE:
            return {text.lower()}
        return {
            " ".join(tokens[i:i + self.SHINGLE_SIZE])
            for i in range(len(tokens) - self.SHINGLE_SIZE + 1)
        }

    def _minhash(self, text: str) -> MinHash:
        m = MinHash(num_perm=self.NUM_PERM)
        for shingle in self._shingle(text):
            m.update(shingle.encode("utf-8"))
        return m

    def is_duplicate(self, text: str, doc_id: Optional[str] = None) -> bool:
        """
        Returns True if text is a near-duplicate of something already indexed.
        If not a duplicate, adds it to the index automatically.
        """
        if len(text.split()) < 20:
            # Too short to meaningfully deduplicate
            return False

        m = self._minhash(text)
        results = self.lsh.query(m)

        if results:
            logger.debug(f"Near-duplicate detected — matches: {results}")
            return True

        # Not a duplicate — add to index with guaranteed unique key
        self._counter += 1
        key = f"doc_{self._counter}"
        self.lsh.insert(key, m)
        self._index[key] = m
        return False

    def reset(self):
        """Clear the index — call between full ingestion runs."""
        self.lsh = MinHashLSH(threshold=self.THRESHOLD, num_perm=self.NUM_PERM)
        self._index.clear()
        self._counter = 0


# ── Module-level singletons ───────────────────────────────────────────────────

_cleaner: Optional[TextCleaner] = None
_detector: Optional[DuplicateDetector] = None


def get_cleaner() -> TextCleaner:
    global _cleaner
    if _cleaner is None:
        _cleaner = TextCleaner()
    return _cleaner


def get_detector() -> DuplicateDetector:
    global _detector
    if _detector is None:
        _detector = DuplicateDetector()
    return _detector