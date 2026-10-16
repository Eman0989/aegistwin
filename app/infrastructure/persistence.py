"""Tenant-scoped request persistence with atomic worker leases."""

import os
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select, update

from app.infrastructure.database import SessionLocal
from app.infrastructure.models import Agent, AgentRequest, AgentSession


DEFAULT_LEASE_SECONDS = int(os.getenv("AEGISTWIN_LEASE_SECONDS", "60"))


def _lease_duration(seconds):
    if isinstance(seconds, bool) or not isinstance(seconds, (int, float)) or not 0 < seconds <= 86400:
        raise ValueError(
            "lease_seconds must be greater than 0 and at most 86400")
    return timedelta(seconds=seconds)


def create_session(tenant_id, agent_id):
    with SessionLocal() as db:
        authorized = db.scalar(
            select(Agent.id).where(Agent.id == agent_id,
                                   Agent.tenant_id == tenant_id)
        )
        if authorized is None:
            raise ValueError("Agent not found for tenant")

        session = AgentSession(tenant_id=tenant_id, agent_id=agent_id)
        db.add(session)
        db.commit()
        db.refresh(session)
        return session.id


def create_request(
    tenant_id, agent_id, session_id, provider, model, public_request_id=None
):
    if public_request_id is not None and (
        not isinstance(public_request_id, str)
        or not public_request_id.strip()
        or len(public_request_id) > 100
    ):
        raise ValueError(
            "public_request_id must be a nonempty string of at most 100 characters")

    with SessionLocal() as db:
        authorized_session = db.scalar(
            select(AgentSession.id).where(
                AgentSession.id == session_id,
                AgentSession.tenant_id == tenant_id,
                AgentSession.agent_id == agent_id,
            )
        )
        if authorized_session is None:
            raise ValueError("Session not found for tenant and agent")
        authorized_agent = db.scalar(
            select(Agent.id).where(Agent.id == agent_id,
                                   Agent.tenant_id == tenant_id)
        )
        if authorized_agent is None:
            raise ValueError("Agent not found for tenant")

        record = AgentRequest(
            tenant_id=tenant_id,
            agent_id=agent_id,
            session_id=session_id,
            provider=provider,
            model=model,
            status="pending",
            public_request_id=public_request_id,
        )
        db.add(record)
        db.commit()
        db.refresh(record)
        return record.id


def acquire_request_lease(
    tenant_id, request_id, worker_id, lease_seconds=DEFAULT_LEASE_SECONDS
):
    """Claim an unleased pending request; return the secret token or None."""
    if not isinstance(worker_id, str) or not worker_id.strip() or len(worker_id) > 255:
        raise ValueError(
            "worker_id must be a nonempty string of at most 255 characters")
    duration = _lease_duration(lease_seconds)
    now = datetime.now(timezone.utc)
    token = uuid.uuid4().hex

    with SessionLocal.begin() as db:
        stmt = (
            update(AgentRequest)
            .where(
                AgentRequest.id == request_id,
                AgentRequest.tenant_id == tenant_id,
                AgentRequest.status == "pending",
                AgentRequest.lease_owner_id.is_(None),
                AgentRequest.lease_token.is_(None),
                AgentRequest.lease_expires_at.is_(None),
            )
            .values(
                lease_owner_id=worker_id,
                lease_token=token,
                lease_expires_at=now + duration,
                last_heartbeat_at=now,
            )
            .returning(AgentRequest.lease_token)
        )
        return db.scalar(stmt)


def renew_request_lease(
    tenant_id, request_id, worker_id, lease_token,
    lease_seconds=DEFAULT_LEASE_SECONDS,
):
    """Renew only the currently valid lease. False means nothing changed."""
    if not worker_id or not lease_token:
        return False
    duration = _lease_duration(lease_seconds)
    now = datetime.now(timezone.utc)

    with SessionLocal.begin() as db:
        stmt = (
            update(AgentRequest)
            .where(
                AgentRequest.id == request_id,
                AgentRequest.tenant_id == tenant_id,
                AgentRequest.status == "pending",
                AgentRequest.lease_owner_id == worker_id,
                AgentRequest.lease_token == lease_token,
                AgentRequest.lease_expires_at > now,
            )
            .values(lease_expires_at=now + duration, last_heartbeat_at=now)
            .returning(AgentRequest.id)
        )
        return db.scalar(stmt) is not None


def complete_request(
    request_id,
    tenant_id,
    status,
    latency=None,
    *,
    input_tokens=None,
    output_tokens=None,
    estimated_cost=None,
    error_code=None,
    worker_id=None,
    lease_token=None,
):
    """Finalize pending request exactly once. Return request UUID or None.

    Existing unleased requests can finalize without a token during migration.
    Any leased request requires the current worker ID, token and unexpired lease.
    """
    if not isinstance(status, str) or not status.strip() or status in {"pending", "recovered"}:
        raise ValueError(
            "status must identify a terminal result other than recovered")
    if latency is not None and latency < 0:
        raise ValueError("Latency must be non-negative")
    if any(value is not None and value < 0 for value in (input_tokens, output_tokens)):
        raise ValueError("Token counts must be non-negative")
    if (worker_id is None) != (lease_token is None):
        raise ValueError("worker_id and lease_token must be supplied together")

    now = datetime.now(timezone.utc)
    conditions = [
        AgentRequest.id == request_id,
        AgentRequest.tenant_id == tenant_id,
        AgentRequest.status == "pending",
    ]
    if lease_token is None:
        # Compatibility with requests created before gateway lease integration.
        # A worker can never use this route to bypass an acquired lease.
        conditions.extend((
            AgentRequest.lease_owner_id.is_(None),
            AgentRequest.lease_token.is_(None),
            AgentRequest.lease_expires_at.is_(None),
        ))
    else:
        conditions.extend((
            AgentRequest.lease_owner_id == worker_id,
            AgentRequest.lease_token == lease_token,
            AgentRequest.lease_expires_at > now,
        ))

    with SessionLocal.begin() as db:
        stmt = (
            update(AgentRequest)
            .where(*conditions)
            .values(
                status=status,
                latency=latency,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                estimated_cost=(
                    Decimal(str(estimated_cost)
                            ) if estimated_cost is not None else None
                ),
                error_code=error_code,
                completed_at=now,
                # Keep owner/heartbeat for audit, invalidate the bearer token.
                lease_token=None,
                lease_expires_at=None,
            )
            .returning(AgentRequest.id)
        )
        return db.scalar(stmt)


def recover_expired_requests(tenant_id, limit=100):
    """Terminally recover up to `limit` expired pending requests for one tenant."""
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 1000:
        raise ValueError("limit must be an integer between 1 and 1000")
    now = datetime.now(timezone.utc)

    with SessionLocal.begin() as db:
        candidates = (
            select(AgentRequest.id)
            .where(
                AgentRequest.tenant_id == tenant_id,
                AgentRequest.status == "pending",
                AgentRequest.lease_token.is_not(None),
                AgentRequest.lease_expires_at <= now,
            )
            .order_by(AgentRequest.lease_expires_at, AgentRequest.id)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        stmt = (
            update(AgentRequest)
            .where(
                AgentRequest.id.in_(candidates),
                AgentRequest.tenant_id == tenant_id,
                AgentRequest.status == "pending",
                AgentRequest.lease_token.is_not(None),
                AgentRequest.lease_expires_at <= now,
            )
            .values(
                status="recovered",
                completed_at=now,
                error_code="LEASE_EXPIRED",
                lease_token=None,
                lease_expires_at=None,
            )
            .returning(AgentRequest.id)
        )
        return len(db.scalars(stmt).all())


def get_request(request_id, tenant_id):
    with SessionLocal() as db:
        request = db.scalar(
            select(AgentRequest).where(
                AgentRequest.id == request_id,
                AgentRequest.tenant_id == tenant_id,
            )
        )
        if request is None:
            return None
        return {
            "id": str(request.id),
            "tenant_id": str(request.tenant_id),
            "agent_id": str(request.agent_id),
            "session_id": str(request.session_id),
            "provider": request.provider,
            "model": request.model,
            "status": request.status,
            "latency": request.latency,
            "latency_ms": request.latency,
            "input_tokens": request.input_tokens,
            "output_tokens": request.output_tokens,
            "estimated_cost": (
                str(request.estimated_cost) if request.estimated_cost is not None else None
            ),
            "error_code": request.error_code,
            "public_request_id": request.public_request_id,
            "lease_owner_id": request.lease_owner_id,
            "lease_expires_at": (
                request.lease_expires_at.isoformat()
                if request.lease_expires_at is not None else None
            ),
            "last_heartbeat_at": (
                request.last_heartbeat_at.isoformat()
                if request.last_heartbeat_at is not None else None
            ),
        }
