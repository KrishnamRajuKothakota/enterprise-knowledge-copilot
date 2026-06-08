"""LangGraph agent state definition."""
from typing import TypedDict, Annotated
from src.ekc.db.models import UserRole


class AgentState(TypedDict):
    query: str
    session_id: str
    user_id: str
    user_role: UserRole
    intent: str                    # doc_search | ticket_lookup | summarize | auto_resolve
    chunks: list                   # RetrievedChunk list
    raw_response: str
    cited_response: str
    sources: list[dict]
    confidence_score: float
    follow_up_suggestions: list[str]
    cache_hit: bool
    fallback: bool
    iteration_count: int           # loop guard for REGENERATING state
    error: str