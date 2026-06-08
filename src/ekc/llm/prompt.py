"""
Role-adaptive prompt builder.
Token budget: system(200) + context(1500) + history(300) + query(100) ≈ 2100 tokens.
"""
import logging
from src.ekc.db.models import UserRole
from src.ekc.retrieval.engine import RetrievedChunk

logger = logging.getLogger(__name__)

# Role-specific system prompts
SYSTEM_PROMPTS = {
    UserRole.junior_engineer: """You are an enterprise IT knowledge assistant helping a junior engineer.
Provide clear, step-by-step explanations. Define technical terms when first used.
Always cite your sources using [SOURCE: chunk_id] format after each factual claim.
If you don't have enough information, say exactly: "I don't have enough information to answer this reliably."
Never invent procedures, steps, or SLA values not present in the provided context.""",

    UserRole.l1_support: """You are an enterprise IT knowledge assistant helping an L1 support agent.
Lead with the resolution or fix. Be concise and action-oriented.
Always cite your sources using [SOURCE: chunk_id] format after each factual claim.
Include escalation paths when relevant.
If you don't have enough information, say exactly: "I don't have enough information to answer this reliably."
Never invent ticket IDs, SLA values, or resolution steps not present in the provided context.""",

    UserRole.lead: """You are an enterprise IT knowledge assistant helping a team lead.
Be concise and strategic. Summarise key points and highlight risks.
Always cite your sources using [SOURCE: chunk_id] format after each factual claim.
If you don't have enough information, say exactly: "I don't have enough information to answer this reliably."
Never invent information not present in the provided context.""",

    UserRole.admin: """You are an enterprise IT knowledge assistant helping a system administrator.
Provide complete technical detail including configuration, compliance, and audit information.
Always cite your sources using [SOURCE: chunk_id] format after each factual claim.
If you don't have enough information, say exactly: "I don't have enough information to answer this reliably."
Never invent information not present in the provided context.""",
}


def build_prompt(
    query: str,
    chunks: list[RetrievedChunk],
    user_role: UserRole,
    conversation_history: list[dict] | None = None,
) -> tuple[str, str]:
    """
    Build (system_prompt, user_message) for the LLM.
    Returns a tuple ready to pass to OllamaClient.generate().
    """
    system_prompt = SYSTEM_PROMPTS.get(
        user_role, SYSTEM_PROMPTS[UserRole.junior_engineer]
    )

    # Build context block from retrieved chunks
    context_parts = []
    for chunk in chunks:
        context_parts.append(
            f"[chunk_id: {chunk.chunk_id[:8]}] "
            f"[source: {chunk.doc_title[:50]}] "
            f"[section: {chunk.section_title[:50]}]\n"
            f"{chunk.content[:600]}"
        )

    context_block = "\n\n---\n\n".join(context_parts)

    # Build conversation history block (last 2 turns max)
    history_block = ""
    if conversation_history:
        recent = conversation_history[-4:]   # last 2 Q&A pairs
        history_lines = []
        for turn in recent:
            role = turn.get("role", "user")
            content = turn.get("content", "")[:200]
            history_lines.append(f"{role.upper()}: {content}")
        if history_lines:
            history_block = (
                "CONVERSATION HISTORY (for context only):\n"
                + "\n".join(history_lines)
                + "\n\n"
            )

    user_message = f"""{history_block}CONTEXT FROM KNOWLEDGE BASE:
{context_block}

QUESTION: {query}

Answer using only the information in the context above. \
Cite each factual claim with [SOURCE: chunk_id]."""

    return system_prompt, user_message