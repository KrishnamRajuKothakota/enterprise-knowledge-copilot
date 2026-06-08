"""
LangGraph StateGraph orchestration.
Routes: supervisor -> specialist agent -> response
"""
import logging
from langgraph.graph import StateGraph, END
from src.ekc.agents.state import AgentState
from src.ekc.agents.supervisor import supervisor_node
from src.ekc.agents.document_search import document_search_node
from src.ekc.agents.ticket_lookup import ticket_lookup_node

logger = logging.getLogger(__name__)


def route_after_supervisor(state: AgentState) -> str:
    """Conditional edge: route based on classified intent."""
    intent = state.get("intent", "doc_search")
    routes = {
        "doc_search":    "document_search",
        "ticket_lookup": "ticket_lookup",
        "summarize":     "document_search",   # reuse doc_search for now
        "auto_resolve":  "ticket_lookup",
    }
    route = routes.get(intent, "document_search")
    logger.debug(f"Routing intent '{intent}' -> '{route}'")
    return route


def build_graph() -> StateGraph:
    graph = StateGraph(AgentState)

    # Add nodes
    graph.add_node("supervisor",       supervisor_node)
    graph.add_node("document_search",  document_search_node)
    graph.add_node("ticket_lookup",    ticket_lookup_node)

    # Entry point
    graph.set_entry_point("supervisor")

    # Conditional routing after supervisor
    graph.add_conditional_edges(
        "supervisor",
        route_after_supervisor,
        {
            "document_search": "document_search",
            "ticket_lookup":   "ticket_lookup",
        },
    )

    # All specialist agents go to END
    graph.add_edge("document_search", END)
    graph.add_edge("ticket_lookup",   END)

    return graph.compile()


# ── Module-level singleton ────────────────────────────────────────────────────

_graph = None


def get_graph():
    global _graph
    if _graph is None:
        _graph = build_graph()
    return _graph