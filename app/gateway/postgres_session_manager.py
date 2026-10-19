
"""Database-backed session creation and reuse."""

from __future__ import annotations

from dataclasses import dataclass, replace
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.contracts import TrustedIdentityContext
from app.gateway.postgres_session_resolver import (
    InvalidDatabaseIdentity,
    SessionAccessDenied,
    _parse_uuid,
    resolve_existing_session,
)
from app.infrastructure.models import Agent, AgentSession


@dataclass(frozen=True)
class ManagedSession:
    identity: TrustedIdentityContext
    session_id: UUID
    created: bool


def manage_postgres_session(
    *,
    identity: TrustedIdentityContext,
    db: Session,
    requested_session_id: str | None,
) -> ManagedSession:
    """Create or authorize a database-backed session.

    The caller owns the transaction. No commit is performed here.
    Only call this function after authenticating the runtime identity.
    """

    tenant_id = _parse_uuid(identity.tenant_id)
    agent_id = _parse_uuid(identity.agent_id)

    # Existing session: validate ownership and active status.
    if requested_session_id is not None:
        session_id = _parse_uuid(requested_session_id)

        trusted_identity = identity.model_copy(
            update={"session_id": str(session_id)}
        )

        resolved = resolve_existing_session(
            trusted_identity,
            db,
        )

        return ManagedSession(
            identity=trusted_identity,
            session_id=resolved.session_id,
            created=False,
        )

    # New session: verify that the authenticated agent
    # belongs to the authenticated tenant.
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

    session = AgentSession(
        tenant_id=tenant_id,
        agent_id=agent_id,
    )

    db.add(session)
    db.flush()

    trusted_identity = identity.model_copy(
        update={"session_id": str(session.id)}
    )

    return ManagedSession(
        identity=trusted_identity,
        session_id=session.id,
        created=True,
    )
