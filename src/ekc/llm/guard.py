"""
Lightweight HallucinationGuard.
Checks that key phrases in the response can be grounded in retrieved chunks.
Avoids the latency cost of running full RAGAS per query.
Full RAGAS evaluation runs in the weekly batch job only.
"""
import re
import logging
from src.ekc.retrieval.engine import RetrievedChunk

logger = logging.getLogger(__name__)

# Phrases that signal the LLM is making up specific facts
HALLUCINATION_SIGNALS = [
    r'\b\d+\s*(minutes?|hours?|days?)\b',    # specific time values
    r'\bSLA\s+(?:is|of|:)\s*\d+',           # specific SLA claims
    r'\bSOP-IT-\d{3}\b',                     # specific SOP references
    r'\bJRA-\d+\b',                          # specific ticket references
    r'\bstep\s+\d+\b',                       # numbered steps
]


class HallucinationGuard:

    def __init__(self, grounding_threshold: float = 0.3):
        self.threshold = grounding_threshold

    def check(
        self,
        response_text: str,
        chunks: list[RetrievedChunk],
    ) -> tuple[bool, float]:
        """
        Check if specific factual claims in the response are grounded
        in the retrieved chunks.
        Returns (is_grounded, confidence_score).
        is_grounded=True means the response passes the guard.
        """
        if not response_text or not chunks:
            return True, 1.0

        combined_context = " ".join(c.content for c in chunks).lower()
        response_lower = response_text.lower()

        # Find specific factual claims in the response
        claims = []
        for pattern in HALLUCINATION_SIGNALS:
            claims.extend(re.findall(pattern, response_lower, re.IGNORECASE))

        if not claims:
            # No specific claims to verify — assume grounded
            return True, 0.85

        # Check what fraction of claims appear in context
        grounded_count = sum(
            1 for claim in claims
            if str(claim).lower() in combined_context
        )

        grounding_ratio = grounded_count / len(claims) if claims else 1.0
        is_grounded = grounding_ratio >= self.threshold

        logger.debug(
            f"HallucinationGuard: {grounded_count}/{len(claims)} claims grounded "
            f"(ratio={grounding_ratio:.2f}, threshold={self.threshold})"
        )

        return is_grounded, grounding_ratio


# ── Module-level singleton ────────────────────────────────────────────────────

_guard = None


def get_guard() -> HallucinationGuard:
    global _guard
    if _guard is None:
        _guard = HallucinationGuard()
    return _guard