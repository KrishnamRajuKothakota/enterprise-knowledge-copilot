from fastapi import Request

"""POST /api/v1/query — main query endpoint."""
import uuid
import logging
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from src.ekc.db.session import get_db
from src.ekc.db.models import User, UserRole, QuerySession, QueryLog
from src.ekc.api.deps import get_current_user
from src.ekc.agents.graph import get_graph
from datetime import datetime

logger = logging.getLogger(__name__)
router = APIRouter()

def _resolve_role(requested_role, jwt_role):
    """
    Use requested role for demo role-switching.
    Security: only admin users can switch to any role.
    Non-admin users can only switch between non-admin roles.
    This prevents privilege escalation via the role parameter.
    """
    from src.ekc.db.models import UserRole
    valid = {r.value for r in UserRole}
    if not requested_role or requested_role not in valid:
        return jwt_role
    # Only admin JWT can assume admin role
    if requested_role == "admin" and jwt_role.value != "admin":
        return jwt_role
    return UserRole(requested_role)


class QueryRequest(BaseModel):
    query: str
    session_id: str | None = None
    role: str | None = None  # Optional role override for demo


class QueryResponse(BaseModel):
    answer: str
    sources: list[dict]
    confidence_score: float
    follow_up_suggestions: list[str]
    session_id: str
    query_id: str
    cache_hit: bool
    fallback: bool
    escalated: bool


@router.post("/query", response_model=QueryResponse)
async def query_endpoint(
    request: Request,
    req: QueryRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    import time
    start = time.time()

    # Session management
    session_id = req.session_id or str(uuid.uuid4())
    session = db.query(QuerySession).filter(
        QuerySession.session_id == session_id
    ).first()
    if not session:
        session = QuerySession(
            session_id=session_id,
            user_id=current_user.user_id,
            context_window=[],
        )
        db.add(session)
        db.commit()

    # Run agent graph
    graph = get_graph()
    # Load conversation history for context-aware responses
    conversation_history = session.context_window or []

    initial_state = {
        "query": req.query,
        "session_id": session_id,
        "user_id": current_user.user_id,
        "user_role": _resolve_role(req.role, current_user.role),
        "conversation_history": conversation_history,
        "intent": "",
        "chunks": [],
        "raw_response": "",
        "cited_response": "",
        "sources": [],
        "confidence_score": 0.0,
        "follow_up_suggestions": [],
        "cache_hit": False,
        "fallback": False,
        "escalated": False,
        "iteration_count": 0,
        "error": "",
    }

    import asyncio
    loop = asyncio.get_event_loop()
    final_state = await loop.run_in_executor(None, graph.invoke, initial_state)

    latency_ms = int((time.time() - start) * 1000)
    query_id = str(uuid.uuid4())

    # Log to QUERY_LOG
    try:
        chunk_ids = [c.chunk_id for c in final_state.get("chunks", [])]
        db.add(QueryLog(
            query_id=query_id,
            session_id=session_id,
            user_id=current_user.user_id,
            query_text=req.query,
            retrieved_chunk_ids=chunk_ids,
            response_text=final_state.get("cited_response", ""),
            confidence_score=final_state.get("confidence_score", 0.0),
            latency_ms=latency_ms,
            cache_hit=final_state.get("cache_hit", False),
            status="fallback" if final_state.get("fallback") else "answered",
        ))
        # Update session context
        session.context_window = (session.context_window or []) + [
            {"role": "user", "content": req.query},
            {"role": "assistant", "content": final_state.get("cited_response", "")[:500]},
        ]
        session.last_active = datetime.utcnow()
        db.commit()
    except Exception as e:
        logger.error(f"Query logging failed: {e}")
        db.rollback()

    return QueryResponse(
        answer=final_state.get("cited_response", ""),
        sources=final_state.get("sources", []),
        confidence_score=final_state.get("confidence_score", 0.0),
        follow_up_suggestions=final_state.get("follow_up_suggestions", []),
        session_id=session_id,
        query_id=query_id,
        cache_hit=final_state.get("cache_hit", False),
        fallback=final_state.get("fallback", False),
        escalated=final_state.get("escalated", False),
    )