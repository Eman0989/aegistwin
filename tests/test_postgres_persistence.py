import uuid

from sqlalchemy import select

from app.infrastructure.database import SessionLocal
from app.infrastructure.models import Tenant, Agent
from app.infrastructure.persistence import (
    create_session,
    create_request,
    complete_request,
    get_request,
)


def main():
    with SessionLocal() as db:
        tenant = Tenant(
            name="AegisTwin Persistence Test"
        )
        db.add(tenant)
        db.flush()

        agent = Agent(
            tenant_id=tenant.id,
            name="Test Security Agent",
            description="Database integration test agent",
        )
        db.add(agent)
        db.commit()

        tenant_id = tenant.id
        agent_id = agent.id

    session_id = create_session(
        tenant_id=tenant_id,
        agent_id=agent_id,
    )
    print("Session created:", session_id)

    request_id = create_request(
        tenant_id=tenant_id,
        agent_id=agent_id,
        session_id=session_id,
        provider="ollama",
        model="llama3",
    )
    print("Request created:", request_id)

    complete_request(
        request_id=request_id,
        status="completed",
        latency=125.5,
    )

    saved = get_request(request_id)

    assert saved is not None
    assert saved["status"] == "completed"
    assert saved["provider"] == "ollama"
    assert saved["model"] == "llama3"
    assert saved["latency"] == 125.5
    assert saved["session_id"] == str(session_id)

    print("Request retrieved:", saved["id"])
    print("Status:", saved["status"])
    print("Latency:", saved["latency"])
    print("AEGISTWIN PERSISTENCE TEST: PASSED")


if __name__ == "__main__":
    main()
