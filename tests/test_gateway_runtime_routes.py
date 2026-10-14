from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.contracts import (
    ModelRequest,
    ModelResponse,
    TrustedIdentityContext,
)
from app.gateway.routes import (
    get_provider_router,
    get_runtime_identity,
    router,
)


class FakeProviderRouter:
    def __init__(self) -> None:
        self.last_request: (
            ModelRequest | None
        ) = None

    async def generate(
        self,
        request: ModelRequest,
    ) -> ModelResponse:
        self.last_request = request

        return ModelResponse(
            request_id=request.request_id,
            provider=request.provider,
            model=request.model,
            content=(
                "Hello from the test provider."
            ),
            usage={
                "input_tokens": 5,
                "output_tokens": 7,
            },
            finish_reason="stop",
            latency_ms=12.5,
        )


def _build_test_app(
    provider: FakeProviderRouter,
) -> FastAPI:
    test_app = FastAPI()

    test_app.include_router(
        router
    )

    async def fake_identity(
    ) -> TrustedIdentityContext:
        return TrustedIdentityContext(
            tenant_id="tenant-test",
            user_id="user-test",
            agent_id="agent-test",
            session_id="session-test",
            permissions={
                "model:generate"
            },
            credential_source="test",
        )

    test_app.dependency_overrides[
        get_runtime_identity
    ] = fake_identity

    test_app.dependency_overrides[
        get_provider_router
    ] = lambda: provider

    return test_app


def test_generate_route_calls_provider(
) -> None:
    provider = FakeProviderRouter()

    client = TestClient(
        _build_test_app(
            provider
        )
    )

    response = client.post(
        "/v1/model/generate",
        json={
            "provider": "ollama",
            "model": "llama3",
            "messages": [
                {
                    "role": "user",
                    "content": "Hello",
                }
            ],
        },
    )

    assert (
        response.status_code
        == 200
    )

    body = response.json()

    assert (
        body["content"]
        == "Hello from the test provider."
    )

    assert (
        body["provider"]
        == "ollama"
    )

    assert (
        body["model"]
        == "llama3"
    )

    assert (
        provider.last_request
        is not None
    )

    assert (
        provider
        .last_request
        .trusted_context
        .tenant_id
        == "tenant-test"
    )

    assert (
        provider
        .last_request
        .request_id
        .startswith("REQ-")
    )


def test_external_identity_fields_are_rejected(
) -> None:
    provider = FakeProviderRouter()

    client = TestClient(
        _build_test_app(
            provider
        )
    )

    response = client.post(
        "/v1/model/generate",
        json={
            "provider": "ollama",
            "model": "llama3",
            "messages": [],
            "tenant_id": "fake-bank",
            "permissions": [
                "admin"
            ],
        },
    )

    assert (
        response.status_code
        == 422
    )


def test_request_id_is_propagated_to_response(
) -> None:
    provider = FakeProviderRouter()

    client = TestClient(
        _build_test_app(
            provider
        )
    )

    response = client.post(
        "/v1/model/generate",
        json={
            "provider": "ollama",
            "model": "llama3",
            "messages": [
                {
                    "role": "user",
                    "content": (
                        "Test request ID"
                    ),
                }
            ],
        },
    )

    assert (
        response.status_code
        == 200
    )

    assert (
        provider.last_request
        is not None
    )

    assert (
        response.json()[
            "request_id"
        ]
        == provider
        .last_request
        .request_id
    )