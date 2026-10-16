
"""Tenant-scoped PostgreSQL persistence and request reliability."""

from datetime import datetime, timezone, timedelta
from decimal import Decimal
from math import isfinite
from uuid import uuid4

from sqlalchemy import (
    and_,
    func,
    select,
    update,
)

from app.infrastructure.database import SessionLocal
from app.infrastructure.models import (
    Agent,
    AgentRequest,
    AgentSession,
)


ALLOWED_FINAL_STATUSES = {
    "completed",
    "failed",
    "blocked",
}


# ==========================================================
# VALIDATION
# ==========================================================


def _validate_worker_id(worker_id):
    if (
        not isinstance(worker_id, str)
        or not worker_id.strip()
        or len(worker_id) > 150
    ):
        raise ValueError("Invalid worker ID.")


def _validate_lease_token(lease_token):
    if (
        not isinstance(lease_token, str)
        or not lease_token
        or len(lease_token) > 100
    ):
        raise ValueError("Invalid lease token.")


def _validate_lease_seconds(lease_seconds):
    if (
        isinstance(lease_seconds, bool)
        or not isinstance(lease_seconds, int)
        or not 1 <= lease_seconds <= 3600
    ):
        raise ValueError(
            "lease_seconds must be an integer between 1 and 3600."
        )


# ==========================================================
# SESSION CREATION
# ==========================================================


def create_session(tenant_id, agent_id):
    """Create a session for an authorized tenant-owned agent."""

    with SessionLocal() as db:
        agent = db.execute(
            select(Agent).where(
                Agent.id == agent_id,
                Agent.tenant_id == tenant_id,
            )
        ).scalar_one_or_none()

        if agent is None:
            raise ValueError("Agent not found for tenant")

        session = AgentSession(
            tenant_id=tenant_id,
            agent_id=agent_id,
        )

        db.add(session)
        db.commit()
        db.refresh(session)

        return session.id


# ==========================================================
# REQUEST CREATION
# ==========================================================


def create_request(
    tenant_id,
    agent_id,
    session_id,
    provider,
    model,
    public_request_id=None,
):
    """Create a pending request with tenant-scoped ownership."""

    with SessionLocal() as db:
        session = db.execute(
            select(AgentSession).where(
                AgentSession.id == session_id,
                AgentSession.tenant_id == tenant_id,
                AgentSession.agent_id == agent_id,
            )
        ).scalar_one_or_none()

        if session is None:
            raise ValueError(
                "Session not found for tenant and agent"
            )

        agent = db.execute(
            select(Agent).where(
                Agent.id == agent_id,
                Agent.tenant_id == tenant_id,
            )
        ).scalar_one_or_none()

        if agent is None:
            raise ValueError("Agent not found for tenant")

        request = AgentRequest(
            tenant_id=tenant_id,
            agent_id=agent_id,
            session_id=session_id,
            provider=provider,
            model=model,
            status="pending",
            public_request_id=public_request_id,
        )

        db.add(request)
        db.commit()
        db.refresh(request)

        return request.id


# ==========================================================
# ATOMIC REQUEST FINALIZATION
# ==========================================================


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
    lease_token=None,
):
    """Atomically finalize one pending request.

    Returns:
        UUID: Request successfully finalized.
        None: Request absent, already terminal, or lease invalid.

    A request that has never acquired a lease may be
    finalized without a token for legacy compatibility.

    A leased request requires the current unexpired token.
    """

    if status not in ALLOWED_FINAL_STATUSES:
        raise ValueError("Unsupported final request status.")

    if latency is not None:
        if (
            isinstance(latency, bool)
            or not isinstance(latency, (int, float))
            or not isfinite(latency)
            or latency < 0
        ):
            raise ValueError(
                "Latency must be a finite non-negative number."
            )

    for value in (input_tokens, output_tokens):
        if value is not None:
            if (
                isinstance(value, bool)
                or not isinstance(value, int)
                or value < 0
            ):
                raise ValueError(
                    "Token counts must be non-negative integers."
                )

    if estimated_cost is not None:
        try:
            cost = Decimal(str(estimated_cost))
        except (ValueError, ArithmeticError) as exc:
            raise ValueError("Invalid estimated cost.") from exc

        if not cost.is_finite() or cost < 0:
            raise ValueError(
                "Estimated cost must be finite and non-negative."
            )
    else:
        cost = None

    if error_code is not None:
        if not isinstance(error_code, str):
            raise ValueError("Error code must be a string.")

    # Compatibility path: only genuinely unleased requests
    # can be finalized without an ownership token.
    if lease_token is None:
        lease_condition = and_(
            AgentRequest.lease_token.is_(None),
            AgentRequest.lease_owner_id.is_(None),
            AgentRequest.lease_expires_at.is_(None),
        )

    else:
        _validate_lease_token(lease_token)

        lease_condition = and_(
            AgentRequest.lease_token == lease_token,
            AgentRequest.lease_owner_id.is_not(None),
            AgentRequest.lease_expires_at.is_not(None),
            AgentRequest.lease_expires_at
            > func.clock_timestamp(),
        )

    # PostgreSQL performs this conditional update atomically.
    # Database time avoids worker clock-skew problems.
    statement = (
        update(AgentRequest)
        .where(
            AgentRequest.id == request_id,
            AgentRequest.tenant_id == tenant_id,
            AgentRequest.status == "pending",
            lease_condition,
        )
        .values(
            status=status,
            latency=latency,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            estimated_cost=cost,
            error_code=error_code,
            completed_at=func.clock_timestamp(),
        )
        .returning(AgentRequest.id)
    )

    with SessionLocal() as db:
        finalized_id = db.execute(
            statement
        ).scalar_one_or_none()

        db.commit()

        return finalized_id


# ==========================================================
# REQUEST LOOKUP
# ==========================================================


def get_request(request_id, tenant_id):
    """Retrieve a request belonging to the specified tenant."""

    with SessionLocal() as db:
        request = db.execute(
            select(AgentRequest).where(
                AgentRequest.id == request_id,
                AgentRequest.tenant_id == tenant_id,
            )
        ).scalar_one_or_none()

        if request is None:
            return None

        return {
            "id": str(request.id),
            "tenant_id": str(request.tenant_id),
            "agent_id": str(request.agent_id),
            "session_id": str(request.session_id),
            "provider": request.provider,
            "model": request.model,
            "public_request_id": request.public_request_id,
            "status": request.status,
            "latency": request.latency,
            "latency_ms": request.latency,
            "input_tokens": request.input_tokens,
            "output_tokens": request.output_tokens,
            "estimated_cost": (
                str(request.estimated_cost)
                if request.estimated_cost is not None
                else None
            ),
            "error_code": request.error_code,
        }


# ==========================================================
# ACQUIRE REQUEST LEASE
# ==========================================================


def acquire_request_lease(
    tenant_id,
    request_id,
    worker_id,
    lease_seconds=60,
):
    """Atomically claim an unleased pending request.

    Returns:
        str: Unique lease token after successful acquisition.
        None: Request cannot be acquired.

    Previously leased requests are not automatically
    reassigned, even after their leases expire.
    """

    _validate_worker_id(worker_id)
    _validate_lease_seconds(lease_seconds)

    lease_token = uuid4().hex

    statement = (
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
            lease_token=lease_token,
            lease_expires_at=(
                func.clock_timestamp()
                + timedelta(seconds=lease_seconds)
            ),
            last_heartbeat_at=func.clock_timestamp(),
        )
        .returning(AgentRequest.id)
    )

    with SessionLocal() as db:
        claimed_id = db.execute(
            statement
        ).scalar_one_or_none()

        db.commit()

    if claimed_id is None:
        return None

    return lease_token


# ==========================================================
# RENEW REQUEST LEASE / HEARTBEAT
# ==========================================================


def renew_request_lease(
    tenant_id,
    request_id,
    worker_id,
    lease_token,
    lease_seconds=60,
):
    """Renew an existing active lease.

    Only the worker holding the current, unexpired
    lease token can renew the request.

    Returns:
        True: Successfully renewed.
        False: Ownership, status, or expiry check failed.
    """

    _validate_worker_id(worker_id)
    _validate_lease_token(lease_token)
    _validate_lease_seconds(lease_seconds)

    statement = (
        update(AgentRequest)
        .where(
            AgentRequest.id == request_id,
            AgentRequest.tenant_id == tenant_id,
            AgentRequest.status == "pending",
            AgentRequest.lease_owner_id == worker_id,
            AgentRequest.lease_token == lease_token,
            AgentRequest.lease_expires_at
            > func.clock_timestamp(),
        )
        .values(
            lease_expires_at=(
                func.clock_timestamp()
                + timedelta(seconds=lease_seconds)
            ),
            last_heartbeat_at=func.clock_timestamp(),
        )
        .returning(AgentRequest.id)
    )

    with SessionLocal() as db:
        renewed_id = db.execute(
            statement
        ).scalar_one_or_none()

        db.commit()

    return renewed_id is not None


# ==========================================================
# EXPIRED REQUEST RECOVERY
# ==========================================================


def recover_expired_requests(
    tenant_id,
    limit=100,
):
    """Recover expired, leased, pending requests.

    Recovery is tenant-scoped and terminal.

    Requests transition:
        pending -> recovered

    Recovery does not retry inference or provider calls.

    Uses PostgreSQL row locks with SKIP LOCKED to permit
    multiple recovery workers without duplicate recovery.

    Returns a list of recovered request UUIDs.
    """

    if (
        isinstance(limit, bool)
        or not isinstance(limit, int)
        or not 1 <= limit <= 1000
    ):
        raise ValueError(
            "limit must be an integer between 1 and 1000."
        )

    with SessionLocal() as db:
        # Lock only expired rows belonging to this tenant.
        # Other recovery workers skip rows already locked.
        expired_ids = db.execute(
            select(AgentRequest.id)
            .where(
                AgentRequest.tenant_id == tenant_id,
                AgentRequest.status == "pending",
                AgentRequest.lease_token.is_not(None),
                AgentRequest.lease_expires_at.is_not(None),
                AgentRequest.lease_expires_at
                <= func.clock_timestamp(),
            )
            .order_by(
                AgentRequest.lease_expires_at,
                AgentRequest.id,
            )
            .limit(limit)
            .with_for_update(skip_locked=True)
        ).scalars().all()

        if not expired_ids:
            db.commit()
            return []

        # Conditional update inside the same transaction.
        # Previously locked rows cannot be finalized by
        # another transaction until recovery commits.
        statement = (
            update(AgentRequest)
            .where(
                AgentRequest.id.in_(expired_ids),
                AgentRequest.tenant_id == tenant_id,
                AgentRequest.status == "pending",
                AgentRequest.lease_expires_at
                <= func.clock_timestamp(),
            )
            .values(
                status="recovered",
                completed_at=func.clock_timestamp(),
                error_code="lease_expired",
            )
            .returning(AgentRequest.id)
        )

        recovered_ids = list(
            db.execute(statement).scalars().all()
        )

        db.commit()

        return recovered_ids
