import uuid
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


def complete_request(request_id, status, latency):
    with SessionLocal() as db:
        request = db.get(AgentRequest, request_id)

        if request is None:
            raise ValueError("Request not found")

        request.status = status
        request.latency = latency
        request.completed_at = datetime.now(timezone.utc)

        db.commit()
        return request.id


def get_request(request_id):
    with SessionLocal() as db:
        request = db.get(AgentRequest, request_id)

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
        }
