from datetime import datetime, timezone

from sqlalchemy import select

from app.infrastructure.database import SessionLocal
from app.infrastructure.models import AgentSession, AgentRequest


def create_session(tenant_id, agent_id):
    with SessionLocal() as db:
        session = AgentSession(
            tenant_id=tenant_id,
            agent_id=agent_id,
        )
        db.add(session)
        db.commit()
        db.refresh(session)
        return session.id


def create_request(
    tenant_id,
    agent_id,
    session_id,
    provider,
    model,
):
    with SessionLocal() as db:
        request = AgentRequest(
            tenant_id=tenant_id,
            agent_id=agent_id,
            session_id=session_id,
            provider=provider,
            model=model,
            status="pending",
        )
        db.add(request)
        db.commit()
        db.refresh(request)
        return request.id


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
):
    from decimal import Decimal

    with SessionLocal() as db:
        request = db.execute(
            select(AgentRequest).where(
                AgentRequest.id == request_id,
                AgentRequest.tenant_id == tenant_id,
            )
        ).scalar_one_or_none()

        if request is None:
            raise ValueError("Request not found for tenant")

        if latency is not None and latency < 0:
            raise ValueError("Latency must be non-negative")

        for value in (input_tokens, output_tokens):
            if value is not None and value < 0:
                raise ValueError("Token counts must be non-negative")

        request.status = status
        request.latency = latency  # milliseconds
        request.input_tokens = input_tokens
        request.output_tokens = output_tokens
        request.estimated_cost = (
            Decimal(str(estimated_cost))
            if estimated_cost is not None
            else None
        )
        request.error_code = error_code
        request.completed_at = datetime.now(timezone.utc)

        db.commit()
        return request.id


def get_request(request_id, tenant_id):
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
