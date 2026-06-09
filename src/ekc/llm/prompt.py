"""
Role-adaptive prompt builder.
Token budget: system(200) + context(1500) + history(300) + query(100) ≈ 2100 tokens.
"""
import logging
from src.ekc.db.models import UserRole
from src.ekc.retrieval.engine import RetrievedChunk

logger = logging.getLogger(__name__)

# Role-specific system prompts
ROLE_SYSTEM_PROMPTS = {
    UserRole.junior_engineer: """You are an IT knowledge assistant for SriniInfotech.
Answer the question DIRECTLY and CONCISELY in the first sentence.
Then provide supporting detail from the context.
Only use information from the provided context chunks.
If the context does not contain the answer, say exactly: "I don't have enough information to answer this reliably."
Always cite sources using [SOURCE: chunk_id].""",

    UserRole.l1_support: """You are an L1 IT support assistant for SriniInfotech.
Start with the resolution steps immediately — no preamble.
Be specific and actionable. Use numbered steps where applicable.
Only use information from the provided context chunks.
If the context does not contain the answer, say exactly: "I don't have enough information to answer this reliably."
Always cite sources using [SOURCE: chunk_id].""",

    UserRole.lead: """You are a senior IT advisor for SriniInfotech.
Give a concise, direct answer. Assume technical competence.
Only use information from the provided context chunks.
If the context does not contain the answer, say exactly: "I don't have enough information to answer this reliably."
Cite sources using [SOURCE: chunk_id].""",

    UserRole.admin: """You are an IT knowledge assistant for SriniInfotech.
Answer the question DIRECTLY and CONCISELY in the first sentence.
Then provide supporting detail from the context.
Only use information from the provided context chunks.
If the context does not contain the answer, say exactly: "I don't have enough information to answer this reliably."
Always cite sources using [SOURCE: chunk_id].""",
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
    system_prompt = ROLE_SYSTEM_PROMPTS.get(
        user_role, ROLE_SYSTEM_PROMPTS[UserRole.junior_engineer]
    )

    # Build context block from retrieved chunks
    context_parts = []
    for chunk in chunks:
        context_parts.append(
            f"[chunk_id: {chunk.chunk_id[:8]}] "
            f"[source: {chunk.doc_title[:50]}] "
            f"[section: {chunk.section_title[:50]}]\n"
            f"{chunk.content[:300]}"   # was 400
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