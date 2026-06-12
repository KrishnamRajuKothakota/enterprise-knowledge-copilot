"""
SupervisorAgent — classifies intent and routes to specialist agent.
"""
import re
import logging
from src.ekc.agents.state import AgentState

logger = logging.getLogger(__name__)

INTENT_PATTERNS = [
    ("auto_resolve", [
        r'\bresolve\s+ticket\b',
        r'\bfix\s+ticket\b',
        r'\bauto.?resolv',
        r'\bTicket\s+ID\s*:\s*\w+',
        r'\b(resolve|fix)\b.*\b(JRA|INC)-\d+\b',
    ]),
    ("ticket_lookup", [
        r'\b(tell|show|give|what).{0,20}(ticket|JRA-\d+|INC-\d+)\b',
        r'\b(status|summary|details?|info)\s+(of|for|about)\s+(ticket|JRA|INC)\b',
        r'\b(summary|status).{0,10}(ticket|JRA-\d+|INC-\d+)\b',
        r'\bsimilar\s+(tickets?|issues?|incidents?)\b',
        r'\b(raise|create|open|log)\s+(a\s+)?(ticket|incident)\b',
    ]),
    ("summarize", [
        r'\b(summarize?|summarise?|summary|overview|tldr)\b',
        r'\b(give\s+me\s+(a\s+)?(brief|short|quick))\b',
    ]),
    ("doc_search", [
        r'\b(how\s+(do\s+)?I|what\s+is|where\s+(is|can)|procedure|steps?|guide|SOP)\b',
        r'\b(find|search|look\s+up|retrieve)\b',
        r'\b(escalat|onboard|provision|deploy|rollback|backup|patch)\b',
        r'\b(kubernetes|kubectl|docker|k8s|pod|deployment)\b',
    ]),
]

# Queries containing these words always go to doc_search regardless of other matches
# Ticket+summary queries go to ticket_lookup, not summarize
TICKET_SUMMARY_PATTERN = r'\b(summary|status|details?)\b.{0,30}\b(ticket|JRA|INC)\b'

DOC_SEARCH_OVERRIDE = [
    r'\bSOP(s)?\b',
    r'\bprocedure(s)?\b',
    r'\bpolic(y|ies)\b',
    r'\bwhich\s+SOP\b',
    r'\bappl(y|ies|ied)\s+to\b',
]


def classify_intent(query: str) -> str:
    """Returns intent string: doc_search | ticket_lookup | summarize | auto_resolve."""
    # Doc search override — if query is clearly about procedures/SOPs, skip ticket patterns
    for pattern in DOC_SEARCH_OVERRIDE:
        if re.search(pattern, query, re.IGNORECASE):
            logger.debug(f"Intent: doc_search (override match)")
            return "doc_search"

    # Ticket summary queries should go to ticket_lookup not summarize
    if re.search(TICKET_SUMMARY_PATTERN, query, re.IGNORECASE):
        return "ticket_lookup"

    for intent, patterns in INTENT_PATTERNS:
        for pattern in patterns:
            if re.search(pattern, query, re.IGNORECASE):
                logger.debug(f"Intent classified: {intent} (pattern match)")
                return intent

    logger.debug("Intent defaulted to: doc_search")
    return "doc_search"


def supervisor_node(state: AgentState) -> AgentState:
    """LangGraph node — classifies intent and sets it in state."""
    intent = classify_intent(state["query"])
    logger.info(f"Query intent: {intent} — '{state['query'][:60]}'")
    return {**state, "intent": intent, "iteration_count": 0}
