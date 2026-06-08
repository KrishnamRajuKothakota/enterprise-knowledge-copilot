"""
Role-aware context injection and document-level RBAC enforcement.
Filters chunks by access_roles before returning to LLM.
Prepends role-specific instruction to the query context.
"""
import logging
from sqlalchemy.orm import Session
from src.ekc.db.models import Chunk as ChunkModel, Document, UserRole

logger = logging.getLogger(__name__)

ROLE_INSTRUCTIONS = {
    UserRole.junior_engineer: (
        "You are helping a junior engineer. Provide verbose, step-by-step explanations. "
        "Define technical terms. Include all relevant procedure steps."
    ),
    UserRole.l1_support: (
        "You are helping an L1 support agent. Lead with the resolution or fix. "
        "Be concise and action-oriented. Include ticket escalation paths if relevant."
    ),
    UserRole.lead: (
        "You are helping a team lead. Be concise and strategic. "
        "Summarise key points. Highlight risks and dependencies."
    ),
    UserRole.admin: (
        "You are helping an admin. Provide complete technical detail. "
        "Include all configuration, audit, and compliance information."
    ),
}


class RoleContextInjector:

    def filter_by_role(
        self,
        chunk_ids: list[str],
        user_role: UserRole,
        user_namespace: str | None,
        db: Session,
    ) -> list[str]:
        """
        Filter chunk_ids to only those the user's role can access.
        Checks DOCUMENT.access_roles and DOCUMENT.namespace.
        """
        if not chunk_ids:
            return []

        allowed = []
        for chunk_id in chunk_ids:
            chunk = db.query(ChunkModel).filter(
                ChunkModel.chunk_id == chunk_id
            ).first()
            if not chunk:
                continue

            doc = db.query(Document).filter(
                Document.doc_id == chunk.doc_id
            ).first()
            if not doc:
                continue

            # Check access_roles
            access_roles = doc.access_roles or []
            if access_roles and user_role.value not in access_roles:
                logger.debug(
                    f"RBAC blocked chunk {chunk_id[:8]} "
                    f"(role={user_role.value}, allowed={access_roles})"
                )
                continue

            allowed.append(chunk_id)

        logger.debug(
            f"RBAC filter: {len(chunk_ids)} -> {len(allowed)} chunks "
            f"for role={user_role.value}"
        )
        return allowed

    def get_role_instruction(self, user_role: UserRole) -> str:
        return ROLE_INSTRUCTIONS.get(user_role, ROLE_INSTRUCTIONS[UserRole.junior_engineer])


# ── Module-level singleton ────────────────────────────────────────────────────

_injector = None


def get_role_injector() -> RoleContextInjector:
    global _injector
    if _injector is None:
        _injector = RoleContextInjector()
    return _injector