"""
SupervisorAgent — classifies intent and routes to specialist agent.
Intent classification: regex patterns first, LLM fallback.
"""
import re
import logging
from src.ekc.agents.state import AgentState

logger = logging.getLogger(__name__)

# Regex intent patterns — fast path
INTENT_PATTERNS = {
    "ticket_lookup": [
        r'\b(ticket|incident|jira|INC-?\d+|JRA-?\d+)\b',
        r'\b(raise|create|open|log)\s+(a\s+)?(ticket|incident)\b',
        r'\bsimilar\s+(tickets?|issues?|incidents?)\b',
    ],
    "auto_resolve": [
        r'\b(auto.?resolv|resolve\s+ticket|fix\s+ticket)\b',
        r'\bTicket\s+ID\s*:\s*\w+',
    ],
    "summarize": [
        r'\b(summarize?|summarise?|summary|overview|tldr)\b',
        r'\b(give\s+me\s+(a\s+)?(brief|short|quick))\b',
    ],
    "doc_search": [
        r'\b(how\s+(do\s+)?I|what\s+is|where\s+(is|can)|procedure|steps?|guide|SOP)\b',
        r'\b(find|search|look\s+up|retrieve)\b',
        r'\b(escalat|onboard|provision|deploy|rollback|backup|patch)\b',
    ],
    "auto_resolve": [
        r'\b(auto.?resolv|resolve\s+ticket|fix\s+ticket)\b',
        r'\bTicket\s+ID\s*:\s*\w+',
        r'\b(JRA|INC)-\d+\b',
        r'\b(how\s+to\s+fix|troubleshoot|resolve)\s+(this|the)\s+(ticket|issue|error)\b',
    ],
}


def classify_intent(query: str) -> str:
    """Returns intent string: doc_search | ticket_lookup | summarize | auto_resolve."""
    query_lower = query.lower()

    for intent, patterns in INTENT_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, query, re.IGNORECASE):
                logger.debug(f"Intent classified: {intent} (pattern match)")
                return intent

    # Default to doc_search
    logger.debug("Intent defaulted to: doc_search")
    return "doc_search"


def supervisor_node(state: AgentState) -> AgentState:
    """LangGraph node — classifies intent and sets it in state."""
    intent = classify_intent(state["query"])
    return {**state, "intent": intent, "iteration_count": 0}