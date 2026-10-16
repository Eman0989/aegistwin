
import os
import uuid

import pytest

from app.agents.base import AgentMessage
from app.providers.router import ProviderRouter
from app.providers.errors import ProviderError


# ==================================================
# 1. OPTIONAL INTEGRATION TEST CONFIGURATION
# ==================================================

RUN_INTEGRATION = (
    os.getenv("RUN_POSTGRES_INTEGRATION") == "1"
)

pytestmark = pytest.mark.skipif(
    not RUN_INTEGRATION,
    reason=(
        "PostgreSQL integration tests are disabled. "
        "Set RUN_POSTGRES_INTEGRATION=1 to enable."
    ),
)


# ==================================================
# 2. DATABASE SAFETY CHECKS
# ==================================================

def verify_test_database():
    """
    Ensure integration tests use only the local
    PostgreSQL test database.
    """

    if os.getenv("DB_NAME") != "aegistwin_test_db":
        raise RuntimeError(
            "Refusing to use a non-test database."
        )

    # Import the configured database URL only
    # after checking the database name.
    from app.infrastructure.database import DATABASE_URL

    if DATABASE_URL.database != "aegistwin_test_db":
        raise RuntimeError(
            "Unsafe database selected."
        )

    if DATABASE_URL.host not in (
        "localhost",
        "127.0.0.1",
    ):
        raise RuntimeError(
            "Integration tests require a local database."
        )

    if DATABASE_URL.port != 55432:
        raise RuntimeError(
            "Unexpected database port."
        )


# ==================================================
# 3. TEST DATABASE FIXTURE
# ==================================================

@pytest.fixture
def test_request():
    """
    Create a temporary tenant, agent, session,
    and request.

    Automatically remove records created by
    this fixture after each test.
    """

    verify_test_database()

    from app.infrastructure.database import SessionLocal

    from app.infrastructure.models import (
        Tenant,
        Agent,
        AgentSession,
        AgentRequest,
    )

    from app.infrastructure.persistence import (
        create_session,
        create_request,
    )

    test_id = uuid.uuid4().hex[:8]

    tenant_id = None
    agent_id = None
    session_id = None
    request_id = None

    try:
        # STEP 1: Create the test tenant and agent.
        with SessionLocal() as db:
            tenant = Tenant(
                name=f"Integration Test {test_id}"
            )

            db.add(tenant)
            db.flush()

            agent = Agent(
                tenant_id=tenant.id,
                name=f"Test Agent {test_id}",
            )

            db.add(agent)
            db.flush()

            tenant_id = tenant.id
            agent_id = agent.id

            db.commit()

        # STEP 2: Create a session belonging
        # to the test tenant and agent.
        session_id = create_session(
            tenant_id=tenant_id,
            agent_id=agent_id,
        )

        # STEP 3: Create a pending model request.
        request_id = create_request(
            tenant_id=tenant_id,
            agent_id=agent_id,
            session_id=session_id,
            provider="ollama",
            model="llama3.2:3b",
        )

        # STEP 4: Return both identifiers.
        # Vishnu's updated API requires tenant_id.
        yield {
            "request_id": request_id,
            "tenant_id": tenant_id,
        }

    finally:
        # STEP 5: Delete test records in reverse
        # dependency order, even if the test fails.
        with SessionLocal() as db:

            if request_id is not None:
                request = db.get(
                    AgentRequest,
                    request_id,
                )

                if request is not None:
                    db.delete(request)
                    db.flush()

            if session_id is not None:
                session = db.get(
                    AgentSession,
                    session_id,
                )

                if session is not None:
                    db.delete(session)
                    db.flush()

            if agent_id is not None:
                agent = db.get(
                    Agent,
                    agent_id,
                )

                if agent is not None:
                    db.delete(agent)
                    db.flush()

            if tenant_id is not None:
                tenant = db.get(
                    Tenant,
                    tenant_id,
                )

                if tenant is not None:
                    db.delete(tenant)

            db.commit()


# ==================================================
# 4. TEST REAL OLLAMA + POSTGRESQL
# ==================================================

@pytest.mark.asyncio
async def test_real_ollama_request(test_request):
    """
    Send a real request through ProviderRouter
    and verify PostgreSQL records the result.
    """

    from app.infrastructure.persistence import (
        complete_request,
        get_request,
    )

    request_id = test_request["request_id"]
    tenant_id = test_request["tenant_id"]

    router = ProviderRouter()

    try:
        result = await router.generate(
            provider="ollama",
            messages=[
                AgentMessage(
                    role="user",
                    content=(
                        "Say hello in one short sentence."
                    ),
                )
            ],
        )

    except Exception:
        # Record the failure against the
        # authenticated test tenant.
        complete_request(
            request_id=request_id,
            tenant_id=tenant_id,
            status="failed",
            latency=0.0,
        )

        raise

    # Record actual provider results.
    complete_request(
        request_id=request_id,
        tenant_id=tenant_id,
        status="completed",
        latency=result.model_latency_ms,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
    )

    # Retrieve the saved record with tenant scope.
    saved = get_request(
        request_id=request_id,
        tenant_id=tenant_id,
    )

    # Verify real LLM output.
    assert result.content.strip()
    assert result.model_name

    # Verify database persistence.
    assert saved is not None
    assert saved["tenant_id"] == str(tenant_id)
    assert saved["status"] == "completed"
    assert saved["provider"] == "ollama"
    assert saved["model"] == "llama3.2:3b"
    assert saved["latency"] is not None
    assert saved["latency"] >= 0
    assert saved["input_tokens"] == result.input_tokens
    assert saved["output_tokens"] == result.output_tokens

    print("\nREAL OLLAMA TEST PASSED")
    print("AI response:", result.content)
    print("Model:", result.model_name)
    print("Input tokens:", saved["input_tokens"])
    print("Output tokens:", saved["output_tokens"])
    print("Latency:", saved["latency"], "ms")


# ==================================================
# 5. TEST PROVIDER FAILURE + POSTGRESQL
# ==================================================

@pytest.mark.asyncio
async def test_failed_provider_request(test_request):
    """
    Simulate provider unavailability and verify
    PostgreSQL records the failure.
    """

    from app.infrastructure.persistence import (
        complete_request,
        get_request,
    )

    request_id = test_request["request_id"]
    tenant_id = test_request["tenant_id"]

    class FailingRouter:
        async def generate(self, provider, messages):
            raise ProviderError(
                "Simulated provider outage",
                code="provider_unavailable",
                retryable=True,
            )

    router = FailingRouter()

    with pytest.raises(ProviderError) as error:
        try:
            await router.generate(
                provider="ollama",
                messages=[
                    AgentMessage(
                        role="user",
                        content="Hello",
                    )
                ],
            )

        except ProviderError as exc:
            # Persist provider failure with tenant scope.
            complete_request(
                request_id=request_id,
                tenant_id=tenant_id,
                status="failed",
                latency=0.0,
                error_code=exc.code,
            )

            raise

    # Retrieve the stored failure.
    saved = get_request(
        request_id=request_id,
        tenant_id=tenant_id,
    )

    # Verify exception information.
    assert error.value.code == "provider_unavailable"
    assert error.value.retryable is True

    # Verify persisted failure.
    assert saved is not None
    assert saved["tenant_id"] == str(tenant_id)
    assert saved["status"] == "failed"
    assert saved["provider"] == "ollama"
    assert saved["latency"] == 0.0
    assert saved["error_code"] == "provider_unavailable"

    print("\nPROVIDER FAILURE TEST PASSED")
    print("Error:", error.value.code)
    print("Saved status:", saved["status"])
