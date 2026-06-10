"""
EscalationAgent — packages ticket context for L2 handoff.
In production: posts to Jira webhook. Here: returns escalation bundle.
"""
import logging
from src.ekc.agents.state import AgentState

logger = logging.getLogger(__name__)


def escalation_node(state: AgentState) -> AgentState:
    """Package context bundle for L2 escalation."""
    chunks = state.get("chunks", [])

    context_bundle = []
    for c in chunks[:5]:
        context_bundle.append(
            f"- [{c.namespace}] {c.doc_title} / {c.section_title}: "
            f"{c.content[:200]}"
        )

    escalation_summary = (
        f"**L2 Escalation Package**\n\n"
        f"**Original Query:** {state['query']}\n\n"
        f"**Auto-Resolution:** Failed (confidence below threshold)\n\n"
        f"**Relevant Context Gathered:**\n"
        + "\n".join(context_bundle) +
        f"\n\n**Recommended Action:** Assign to L2 resolver group "
        f"with this context bundle attached."
    )

    sources = [
        {
            "chunk_id": c.chunk_id,
            "doc_title": c.doc_title,
            "section_title": c.section_title,
            "page_number": c.page_number,
            "namespace": c.namespace,
        }
        for c in chunks[:3]
    ]

    return {
        **state,
        "cited_response": escalation_summary,
        "sources": sources,
        "confidence_score": state.get("confidence_score", 0.0),
        "follow_up_suggestions": [
            "View similar resolved tickets",
            "Check escalation SOP",
        ],
        "fallback": True,
    }