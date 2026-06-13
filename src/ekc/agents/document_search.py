"""DocumentSearchAgent — retrieves context and generates cited answer."""
import logging
from src.ekc.agents.state import AgentState
from src.ekc.retrieval.engine import get_engine
from src.ekc.llm.client import get_llm_client
from src.ekc.llm.prompt import build_prompt
from src.ekc.llm.citation import CitationEnforcer
from src.ekc.llm.guard import get_guard
from src.ekc.llm.formatter import get_formatter
from src.ekc.core.exceptions import LLMTimeoutError, LLMUnavailableError
from src.ekc.db.session import SessionLocal
 
logger = logging.getLogger(__name__)
MAX_RETRIES = 2
 
 
def document_search_node(state: AgentState) -> AgentState:
    from src.ekc.retrieval.cache import get_cache

    # Check response-level cache first — skips retrieval AND LLM entirely.
    # Skip cache entirely for follow-up queries (those with conversation history),
    # because a context-free cached answer would be wrong for a contextual question.
    cache = get_cache()
    _has_history = bool(state.get("conversation_history"))
    cached_response = None if _has_history else cache.get_response(
        state["query"], role=str(state.get("user_role", "default"))
    )
    if cached_response:
        logger.info(f"Response cache hit for: {state['query'][:50]}")
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
        enforcer = CitationEnforcer()
        guard = get_guard()
        formatter = get_formatter()
 
        # Retrieve
        chunks, cache_hit = engine.hybrid_search(
            state["query"],
            user_role=state["user_role"],
            top_k=5,
        )
 
        if not chunks:
            return {
                **state,
                "chunks": [],
                "fallback": True,
                "raw_response": "No relevant documents found.",
                "cited_response": "No relevant documents found.",
                "sources": [],
                "confidence_score": 0.0,
                "follow_up_suggestions": [],
                "cache_hit": False,
            }
 
        # Build prompt and generate
        system_prompt, user_message = build_prompt(
            state["query"], chunks, state["user_role"],
            conversation_history=state.get("conversation_history", [])
        )
 
        raw_response = ""
        fallback = False
 
        for attempt in range(MAX_RETRIES + 1):
            try:
                raw_response = llm.generate(
                    system_prompt, user_message, max_tokens=500
                )
                is_grounded, conf = guard.check(raw_response, chunks)
                if is_grounded or attempt == MAX_RETRIES:
                    break
                logger.warning(f"HallucinationGuard failed attempt {attempt+1}, retrying")
            except LLMTimeoutError:
                fallback = True
                raw_response = _build_fallback(chunks)
                break
            except LLMUnavailableError:
                fallback = True
                raw_response = _build_fallback(chunks)
                break
 
        # Skip CitationEnforcer for fallback — raw excerpts are the answer
        if fallback:
            cited_response = raw_response
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
        else:
            cited_response, sources = enforcer.enforce(raw_response, chunks)
 
        result = formatter.format(
            cited_response, sources, chunks,
            session_id=state["session_id"],
            cache_hit=cache_hit,
            fallback=fallback,
        )
        # Cache the full response for instant repeat queries
        # Apply space fix before caching so cached responses are also clean
        import re as _space_re
        clean_cached_answer = result.answer
        clean_cached_answer = _space_re.sub(r' {2,}', ' ', clean_cached_answer).strip()
        # Only cache context-free answers. If the query used conversation history,
        # the answer is specific to this conversation and must NOT be served to
        # other users/sessions (privacy + correctness — see BUG 2).
        has_history = bool(state.get("conversation_history"))
        if not fallback and clean_cached_answer and not has_history:
            _cache_role = str(state.get("user_role", "default"))
            cache.set_response(state["query"], {
                "answer": clean_cached_answer,
                "sources": result.sources,
                "confidence_score": result.confidence_score,
                "follow_up_suggestions": result.follow_up_suggestions,
            }, role=_cache_role)
 
        return {
            **state,
            "chunks": chunks,
            "raw_response": raw_response,
            "cited_response": result.answer,
            "sources": result.sources,
            "confidence_score": result.confidence_score,
            "follow_up_suggestions": result.follow_up_suggestions,
            "cache_hit": cache_hit,
            "fallback": fallback,
        }
    finally:
        db.close()
 
 
def _build_fallback(chunks) -> str:
    """Return raw snippets when LLM is unavailable."""
    parts = ["⚠️ LLM unavailable. Here are the most relevant excerpts:\n"]
    for i, c in enumerate(chunks[:3], 1):
        parts.append(f"{i}. [{c.section_title}]\n{c.content[:300]}\n")
    return "\n".join(parts)
