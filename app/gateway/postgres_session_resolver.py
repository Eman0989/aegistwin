
"""PostgreSQL session ownership resolution for the runtime gateway."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.contracts import TrustedIdentityContext
from app.infrastructure.models import Agent, AgentSession


class InvalidDatabaseIdentity(ValueError):
    """A trusted runtime identity cannot be resolved to UUIDs."""


class SessionAccessDenied(PermissionError):
    """The requested session is not authorized for this identity."""


@dataclass(frozen=True)
class ResolvedSession:
    tenant_id: UUID
    agent_id: UUID
    session_id: UUID


def _parse_uuid(value: str) -> UUID:
    try:
        return UUID(value)
    except (ValueError, TypeError, AttributeError) as exc:
        raise InvalidDatabaseIdentity(
            "Invalid database identity."
        ) from exc


def resolve_existing_session(
    identity: TrustedIdentityContext,
    db: Session,
) -> ResolvedSession:
    """Resolve a session using trusted tenant and agent ownership."""

    tenant_id = _parse_uuid(identity.tenant_id)
    agent_id = _parse_uuid(identity.agent_id)
    session_id = _parse_uuid(identity.session_id)

    agent = db.execute(
        select(Agent).where(
            Agent.id == agent_id,
            Agent.tenant_id == tenant_id,
        )
    ).scalar_one_or_none()

    if agent is None:
        raise SessionAccessDenied(
            "Agent is not authorized for this tenant."
        )

    session = db.execute(
        select(AgentSession).where(
            AgentSession.id == session_id,
            AgentSession.tenant_id == tenant_id,
            AgentSession.agent_id == agent_id,
            AgentSession.ended_at.is_(None),
        )
    ).scalar_one_or_none()

    if session is None:
        raise SessionAccessDenied(
            "Session is not authorized."
        )

    return ResolvedSession(
        tenant_id=tenant_id,
        agent_id=agent_id,
        session_id=session_id,
    )
