"""
ResponseFormatter — assembles the final API response schema.
Schema: {answer, sources, confidence_score, follow_up_suggestions, session_id}
"""
import logging
import re
from dataclasses import dataclass, field
from src.ekc.retrieval.engine import RetrievedChunk

logger = logging.getLogger(__name__)


@dataclass
class FormattedResponse:
    answer: str
    sources: list[dict]
    confidence_score: float
    follow_up_suggestions: list[str]
    session_id: str
    cache_hit: bool = False
    fallback: bool = False


class ResponseFormatter:

    def format(
        self,
        answer: str,
        sources: list[dict],
        chunks: list[RetrievedChunk],
        session_id: str,
        cache_hit: bool = False,
        fallback: bool = False,
    ) -> FormattedResponse:

        # Compute confidence from reranker scores
        confidence = self._compute_confidence(chunks, answer)

        # Generate follow-up suggestions based on top chunk content
        follow_ups = self._suggest_follow_ups(chunks)

        # Fix missing spaces between words (LLM tokenization artifact)
        import re as _re2
        # camelCase: lowercase->uppercase
        answer = _re2.sub(r'([a-z])([A-Z])', r'\1 \2', answer)
        # ALLCAPS->lowercase: e.g. VPNissue -> VPN issue
        answer = _re2.sub(r'([A-Z]{2,})([a-z])', r'\1 \2', answer)
        # lowercase->digit or digit->lowercase
        answer = _re2.sub(r'([a-z])([0-9])', r'\1 \2', answer)
        answer = _re2.sub(r'([0-9])([a-z])', r'\1 \2', answer)
        # Fix common concatenations: word ending + common prepositions/articles
        for pair in [('the','The'),('to','To'),('with','With'),('by','By'),
                     ('and','And'),('in','In'),('of','Of'),('a','A'),('an','An')]:
            answer = _re2.sub(r'([a-z])(' + pair[0] + r')([A-Z\s])', r'\1 \2\3', answer)
        # Add space after punctuation if missing
        answer = _re2.sub(r'([.,;:])([A-Za-z])', r'\1 \2', answer)
        # Fix spurious spaces inside words (e.g. "Okt a" -> "Okta")
        answer = _re2.sub(r'([A-Za-z]{2,})\s([a-z]{1,2})(\s)', r'\1\2\3', answer)
        # Fix space before punctuation
        answer = _re2.sub(r'\s+([.,;:])', r'\1', answer)
        # Collapse multiple spaces
        answer = _re2.sub(r' {2,}', ' ', answer)

        # Replace PII redaction tokens with readable text
        import re as _re
        answer = _re.sub(r'\[PERSON_?\d*\]', '[name redacted]', answer)
        answer = _re.sub(r'\[EMAIL_?\d*\]', '[redacted email]', answer)
        answer = _re.sub(r'\[PHONE_?\d*\]', '[redacted phone]', answer)
        answer = _re.sub(r'\[AADHAAR_?\d*\]', '[redacted ID]', answer)
        answer = _re.sub(r'\[PAN_?\d*\]', '[redacted PAN]', answer)

        # Don't strip citation tags from fallback responses — they're the whole content
        if fallback:
            clean_answer = answer
        else:
            # Remove [SOURCE: ...] tags in all formats
            clean_answer = re.sub(r'\[\s*SOURCE:[^\]]*\]', '', answer, flags=re.IGNORECASE)
            clean_answer = re.sub(r'\[SOURCE:[^\]]*\]', '', clean_answer, flags=re.IGNORECASE)
            # Remove orphan brackets
            clean_answer = re.sub(r'\s*\]\s*', ' ', clean_answer)
            clean_answer = re.sub(r'\s*\[\s*', ' ', clean_answer)
            clean_answer = re.sub(r'\s+', ' ', clean_answer).strip()

        return FormattedResponse(
            answer=clean_answer,
            sources=sources,
            confidence_score=round(confidence, 3),
            follow_up_suggestions=follow_ups,
            session_id=session_id,
            cache_hit=cache_hit,
            fallback=fallback,
        )

    def _compute_confidence(
        self,
        chunks: list[RetrievedChunk],
        answer: str,
    ) -> float:
        """
        Confidence = blend of:
        - Top chunk reranker score (normalised)
        - Whether the answer contains "I don't have enough information"
        """
        if not chunks:
            return 0.0

        if "i don't have enough information" in answer.lower():
            return 0.1

        # Normalise reranker scores to 0-1 range
        top_score = chunks[0].score if chunks else 0.0

        # ms-marco scores range roughly -10 to +10
        normalised = max(0.0, min(1.0, (top_score + 10) / 20))

        return normalised

    def _suggest_follow_ups(self, chunks: list[RetrievedChunk]) -> list[str]:
        """Generate 2-3 follow-up questions based on retrieved content."""
        if not chunks:
            return []

        suggestions = []
        top_chunk = chunks[0]

        # Section-based suggestions
        section = top_chunk.section_title.lower()
        namespace = top_chunk.namespace

        if "incident" in section or namespace == "it-ops":
            suggestions.extend([
                "What is the escalation path for P1 incidents?",
                "What are the SLA targets for each priority level?",
            ])
        if "vpn" in section:
            suggestions.extend([
                "How do I troubleshoot VPN connection failures?",
                "What are the VPN client installation steps?",
            ])
        if namespace == "kubernetes":
            suggestions.extend([
                "How do I check pod status after a rollback?",
                "What is the procedure for a rolling update?",
            ])
        if namespace == "devops":
            suggestions.extend([
                "Are there similar tickets with resolutions?",
                "What SOP covers this type of issue?",
            ])

        return suggestions[:3]


# ── Module-level singleton ────────────────────────────────────────────────────

_formatter = None


def get_formatter() -> ResponseFormatter:
    global _formatter
    if _formatter is None:
        _formatter = ResponseFormatter()
    return _formatter