"""TicketLookupAgent — finds similar resolved tickets."""
import logging
from src.ekc.agents.state import AgentState
from src.ekc.retrieval.engine import get_engine
from src.ekc.llm.client import get_llm_client
from src.ekc.llm.formatter import get_formatter
from src.ekc.core.exceptions import LLMTimeoutError, LLMUnavailableError
from src.ekc.db.session import SessionLocal

logger = logging.getLogger(__name__)


def ticket_lookup_node(state: AgentState) -> AgentState:
    from src.ekc.retrieval.cache import get_cache
    cache = get_cache()
    cached_response = cache.get_response(state["query"])
    if cached_response:
        return {
            **state,
            "chunks": [],
            "raw_response": cached_response["answer"],
            "cited_response": cached_response["answer"],
            "sources": cached_response["sources"],
            "confidence_score": cached_response["confidence_score"],
            "follow_up_suggestions": cached_response["follow_up_suggestions"],
            "cache_hit": True,
            "fallback": False,
        }
    db = SessionLocal()
    try:
        engine = get_engine(db)
        llm = get_llm_client()
        formatter = get_formatter()

        # Search specifically in ticket namespaces
        chunks, cache_hit = engine.hybrid_search(
            state["query"],
            user_role=state["user_role"],
            top_k=5,
        )

        # Filter to ticket chunks
        ticket_chunks = [
            c for c in chunks
            if c.namespace in ("support", "devops") or "Ticket ID" in c.content
        ]

        if not ticket_chunks:
            # Fall back to doc_search if no tickets found
            from src.ekc.agents.document_search import document_search_node
            return document_search_node({**state, "intent": "doc_search"})

        system_prompt = """You are an IT support specialist. 
The user is looking for similar resolved tickets to help resolve their issue.
Summarise the resolution steps from similar tickets.
Always cite sources using [SOURCE: chunk_id].
Be concise and action-oriented."""

        context = "\n\n---\n\n".join(
            f"[chunk_id: {c.chunk_id[:8]}]\n{c.content[:500]}"
            for c in ticket_chunks[:3]
        )

        user_message = f"""SIMILAR RESOLVED TICKETS:
{context}

USER QUERY: {state['query']}

Summarise the resolution approach from these tickets."""

        try:
            raw_response = llm.generate(system_prompt, user_message, max_tokens=300)
        except (LLMTimeoutError, LLMUnavailableError):
            raw_response = "\n".join(
                f"- {c.content[:200]}" for c in ticket_chunks[:3]
            )

        from src.ekc.llm.citation import CitationEnforcer
        enforcer = CitationEnforcer()
        cited, sources = enforcer.enforce(raw_response, ticket_chunks)

        result = formatter.format(
            cited, sources, ticket_chunks,
            session_id=state["session_id"],
        )

        if result.answer:
            cache.set_response(state["query"], {
                "answer": result.answer,
                "sources": result.sources,
                "confidence_score": result.confidence_score,
                "follow_up_suggestions": result.follow_up_suggestions,
            })

        return {
            **state,
            "chunks": ticket_chunks,
            "cited_response": result.answer,
            "sources": result.sources,
            "confidence_score": result.confidence_score,
            "follow_up_suggestions": result.follow_up_suggestions,
            "cache_hit": cache_hit,
            "fallback": False,
        }
    finally:
        db.close()