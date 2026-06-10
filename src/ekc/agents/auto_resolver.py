"""
TicketAutoResolverAgent — ReAct loop for automatic ticket resolution.
Max 3 iterations. Exits when confidence >= 0.7 or iterations exhausted.
Falls back to EscalationAgent on low confidence.
"""
import logging
import re
from src.ekc.agents.state import AgentState
from src.ekc.retrieval.engine import get_engine
from src.ekc.llm.client import get_llm_client
from src.ekc.llm.formatter import get_formatter
from src.ekc.core.exceptions import LLMTimeoutError, LLMUnavailableError
from src.ekc.db.session import SessionLocal
from src.ekc.db.models import UserRole

logger = logging.getLogger(__name__)

MAX_ITERATIONS = 3
CONFIDENCE_THRESHOLD = 0.70


def auto_resolver_node(state: AgentState) -> AgentState:
    """ReAct loop: Thought → Action → Observation, max 3 iterations."""
    from src.ekc.retrieval.cache import get_cache
    cache = get_cache()

    # Check response cache first
    cached = cache.get_response(state["query"])
    if cached:
        return {
            **state,
            "chunks": [],
            "cited_response": cached["answer"],
            "sources": cached["sources"],
            "confidence_score": cached["confidence_score"],
            "follow_up_suggestions": cached["follow_up_suggestions"],
            "cache_hit": True,
            "fallback": False,
        }

    db = SessionLocal()
    try:
        engine = get_engine(db)
        llm = get_llm_client()
        formatter = get_formatter()

        query = state["query"]
        all_chunks = []
        iteration = 0
        resolution = ""
        confidence = 0.0

        # ── ReAct loop ────────────────────────────────────────────────────
        while iteration < MAX_ITERATIONS:
            iteration += 1
            logger.info(f"AutoResolver iteration {iteration}/{MAX_ITERATIONS}")

            # ACTION — retrieve evidence
            chunks, _ = engine.hybrid_search(
                query,
                user_role=UserRole.l1_support,
                top_k=5,
                use_cache=False,
            )

            if not chunks:
                logger.warning("No chunks retrieved — escalating")
                break

            # Accumulate unique chunks across iterations
            seen_ids = {c.chunk_id for c in all_chunks}
            for c in chunks:
                if c.chunk_id not in seen_ids:
                    all_chunks.append(c)
                    seen_ids.add(c.chunk_id)

            # THOUGHT + ACTION — ask LLM to reason and attempt resolution
            context = "\n\n---\n\n".join(
                f"[SOURCE: {c.chunk_id[:8]}] {c.section_title}\n{c.content[:400]}"
                for c in all_chunks[:5]
            )

            react_prompt = f"""You are an L1 IT support agent attempting to resolve a ticket.

TICKET: {query}

EVIDENCE (iteration {iteration}/{MAX_ITERATIONS}):
{context}

Reason step by step:
1. THOUGHT: What does this evidence tell me about resolving this ticket?
2. RESOLUTION: Write a specific resolution (or "INSUFFICIENT EVIDENCE" if unable)
3. CONFIDENCE: Rate your confidence 0.0-1.0 that this resolution is correct

Format your response exactly as:
THOUGHT: <your reasoning>
RESOLUTION: <resolution steps or INSUFFICIENT EVIDENCE>
CONFIDENCE: <0.0-1.0>"""

            try:
                react_response = llm.generate(
                    "You are a precise IT support specialist.",
                    react_prompt,
                    max_tokens=300,
                )
            except (LLMTimeoutError, LLMUnavailableError):
                logger.warning("LLM unavailable in ReAct loop")
                break

            # OBSERVATION — parse response
            thought, resolution, confidence = _parse_react_response(react_response)
            logger.info(
                f"  Iteration {iteration}: confidence={confidence:.2f} "
                f"resolution_len={len(resolution)}"
            )

            # Exit loop if confident enough
            if confidence >= CONFIDENCE_THRESHOLD:
                logger.info(f"Confidence {confidence:.2f} >= threshold, resolving")
                break

            # Refine query for next iteration based on what we learned
            if iteration < MAX_ITERATIONS and thought:
                query = _refine_query(state["query"], thought)

        # ── Build final response ──────────────────────────────────────────
        if confidence >= CONFIDENCE_THRESHOLD and resolution and resolution != "INSUFFICIENT EVIDENCE":
            final_answer = (
                f"**Auto-Resolution Suggestion** (confidence: {confidence:.0%})\n\n"
                f"{resolution}\n\n"
                f"*Please review before applying. Sources cited below.*"
            )
            sources = [
                {
                    "chunk_id": c.chunk_id,
                    "doc_title": c.doc_title,
                    "section_title": c.section_title,
                    "page_number": c.page_number,
                    "namespace": c.namespace,
                }
                for c in all_chunks[:3]
            ]
            fallback = False
        else:
            # Low confidence — escalation path
            final_answer = (
                f"**Escalation Required** (confidence: {confidence:.0%} < {CONFIDENCE_THRESHOLD:.0%} threshold)\n\n"
                f"Could not resolve automatically after {iteration} iteration(s).\n"
                f"Relevant context has been gathered for L2 handoff.\n\n"
                f"Best available evidence:\n{resolution if resolution else 'No resolution found.'}"
            )
            sources = [
                {
                    "chunk_id": c.chunk_id,
                    "doc_title": c.doc_title,
                    "section_title": c.section_title,
                    "page_number": c.page_number,
                    "namespace": c.namespace,
                }
                for c in all_chunks[:3]
            ]
            fallback = True

        result = formatter.format(
            final_answer, sources, all_chunks,
            session_id=state["session_id"],
            cache_hit=False,
            fallback=fallback,
        )

        # Cache successful resolutions
        if not fallback and result.answer:
            cache.set_response(state["query"], {
                "answer": result.answer,
                "sources": result.sources,
                "confidence_score": result.confidence_score,
                "follow_up_suggestions": result.follow_up_suggestions,
            })

        return {
            **state,
            "chunks": all_chunks,
            "cited_response": result.answer,
            "sources": result.sources,
            "confidence_score": confidence,
            "follow_up_suggestions": result.follow_up_suggestions,
            "cache_hit": False,
            "fallback": fallback,
            "iteration_count": iteration,
        }

    finally:
        db.close()


def _parse_react_response(text: str) -> tuple[str, str, float]:
    """Parse THOUGHT / RESOLUTION / CONFIDENCE from ReAct response."""
    thought = ""
    resolution = "INSUFFICIENT EVIDENCE"
    confidence = 0.0

    thought_match = re.search(r"THOUGHT:\s*(.+?)(?=RESOLUTION:|$)", text, re.DOTALL)
    if thought_match:
        thought = thought_match.group(1).strip()

    resolution_match = re.search(r"RESOLUTION:\s*(.+?)(?=CONFIDENCE:|$)", text, re.DOTALL)
    if resolution_match:
        resolution = resolution_match.group(1).strip()

    confidence_match = re.search(r"CONFIDENCE:\s*([\d.]+)", text)
    if confidence_match:
        try:
            confidence = min(1.0, max(0.0, float(confidence_match.group(1))))
        except ValueError:
            confidence = 0.0

    return thought, resolution, confidence


def _refine_query(original_query: str, thought: str) -> str:
    """Refine the search query based on ReAct thought for next iteration."""
    # Extract key technical terms from thought to focus next search
    tech_terms = re.findall(
        r'\b(SOP-IT-\d+|kubernetes|docker|VPN|incident|escalat\w+|'
        r'CrashLoop\w*|ImagePull\w*|deploy\w+|patch\w*|backup\w*)\b',
        thought, re.IGNORECASE
    )
    if tech_terms:
        refined = f"{original_query} {' '.join(set(tech_terms[:3]))}"
        logger.debug(f"Refined query: {refined[:80]}")
        return refined
    return original_query