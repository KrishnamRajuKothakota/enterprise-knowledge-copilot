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

        # Clean up [SOURCE: ...] tags from the displayed answer
        clean_answer = re.sub(
            r'\s*\[SOURCE:\s*[a-f0-9\-]+\]',
            '',
            answer,
            flags=re.IGNORECASE,
        ).strip()

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