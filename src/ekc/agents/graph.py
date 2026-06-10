"""LangGraph StateGraph orchestration."""
import logging
from langgraph.graph import StateGraph, END
from src.ekc.agents.state import AgentState
from src.ekc.agents.supervisor import supervisor_node
from src.ekc.agents.document_search import document_search_node
from src.ekc.agents.ticket_lookup import ticket_lookup_node
from src.ekc.agents.auto_resolver import auto_resolver_node
from src.ekc.agents.escalation import escalation_node

logger = logging.getLogger(__name__)


def route_after_supervisor(state: AgentState) -> str:
    intent = state.get("intent", "doc_search")
    routes = {
        "doc_search":    "document_search",
        "ticket_lookup": "ticket_lookup",
        "summarize":     "document_search",
        "auto_resolve":  "auto_resolve",
    }
    route = routes.get(intent, "document_search")
    logger.debug(f"Routing intent '{intent}' -> '{route}'")
    return route


def route_after_resolver(state: AgentState) -> str:
    """After auto_resolve: escalate if low confidence."""
    if state.get("fallback") and state.get("confidence_score", 0) < 0.70:
        return "escalation"
    return END


def build_graph() -> StateGraph:
    graph = StateGraph(AgentState)

    graph.add_node("supervisor",      supervisor_node)
    graph.add_node("document_search", document_search_node)
    graph.add_node("ticket_lookup",   ticket_lookup_node)
    graph.add_node("auto_resolve",    auto_resolver_node)
    graph.add_node("escalation",      escalation_node)

    graph.set_entry_point("supervisor")

    graph.add_conditional_edges(
        "supervisor",
        route_after_supervisor,
        {
            "document_search": "document_search",
            "ticket_lookup":   "ticket_lookup",
            "auto_resolve":    "auto_resolve",
        },
    )

    # Auto resolver can escalate
    graph.add_conditional_edges(
        "auto_resolve",
        route_after_resolver,
        {
            "escalation": "escalation",
            END: END,
        },
    )

    graph.add_edge("document_search", END)
    graph.add_edge("ticket_lookup",   END)
    graph.add_edge("escalation",      END)

    return graph.compile()


_graph = None

def get_graph():
    global _graph
    if _graph is None:
        _graph = build_graph()
    return _graph