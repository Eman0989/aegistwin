from unittest.mock import patch

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
from app.security.llm_response_inspector import (
    ResponseAction,
    ResponseInspection,
)


class FakeProviderRouter:
    def __init__(
        self,
        content: str = "Hello from the test provider.",
    ) -> None:
        self.last_request: (
            ModelRequest | None
        ) = None

        self.content = content

    async def generate(
        self,
        request: ModelRequest,
    ) -> ModelResponse:
        self.last_request = request

        return ModelResponse(
            request_id=request.request_id,
            provider=request.provider,
            model=request.model,
            content=self.content,
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


def _request_payload(
) -> dict:
    return {
        "provider": "ollama",
        "model": "llama3",
        "messages": [
            {
                "role": "user",
                "content": "Hello",
            }
        ],
    }


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
        json=_request_payload(),
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


# ==================================================
# POST-LLM RESPONSE SECURITY TESTS
# ==================================================


def test_gateway_allows_safe_model_response(
) -> None:
    """ALLOW returns the original provider response."""

    original_content = (
        "This is a safe model response."
    )

    provider = FakeProviderRouter(
        content=original_content
    )

    client = TestClient(
        _build_test_app(
            provider
        )
    )

    inspection = ResponseInspection(
        action=ResponseAction.ALLOW,
        content=original_content,
        reason="Safe response.",
    )

    with patch(
        "app.gateway.routes.inspect_response",
        return_value=inspection,
    ) as inspector:
        response = client.post(
            "/v1/model/generate",
            json=_request_payload(),
        )

    assert (
        response.status_code
        == 200
    )

    body = response.json()

    assert (
        body["content"]
        == original_content
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
        body["usage"]["input_tokens"]
        == 5
    )

    assert (
        body["usage"]["output_tokens"]
        == 7
    )

    inspector.assert_called_once_with(
        original_content
    )


def test_gateway_redacts_model_response(
) -> None:
    """REDACT returns sanitized content only."""

    unsafe_content = (
        "Contact alice@example.com."
    )

    sanitized_content = (
        "Contact [REDACTED]."
    )

    provider = FakeProviderRouter(
        content=unsafe_content
    )

    client = TestClient(
        _build_test_app(
            provider
        )
    )

    inspection = ResponseInspection(
        action=ResponseAction.REDACT,
        content=sanitized_content,
        reason=(
            "Supported sensitive data "
            "was redacted."
        ),
        matched_rules=(
            "email",
        ),
        redaction_count=1,
    )

    with patch(
        "app.gateway.routes.inspect_response",
        return_value=inspection,
    ) as inspector:
        response = client.post(
            "/v1/model/generate",
            json=_request_payload(),
        )

    assert (
        response.status_code
        == 200
    )

    body = response.json()

    assert (
        body["content"]
        == sanitized_content
    )

    assert (
        unsafe_content
        not in response.text
    )

    # Other ModelResponse metadata must survive.
    assert (
        body["provider"]
        == "ollama"
    )

    assert (
        body["model"]
        == "llama3"
    )

    assert (
        body["usage"]["input_tokens"]
        == 5
    )

    assert (
        body["usage"]["output_tokens"]
        == 7
    )

    assert (
        body["latency_ms"]
        == 12.5
    )

    assert (
        body["finish_reason"]
        == "stop"
    )

    inspector.assert_called_once_with(
        unsafe_content
    )


def test_gateway_blocks_unsafe_model_response(
) -> None:
    """BLOCK returns 403 and never releases model content."""

    unsafe_content = (
        "HIGHLY-SENSITIVE-SECRET-CONTENT"
    )

    provider = FakeProviderRouter(
        content=unsafe_content
    )

    client = TestClient(
        _build_test_app(
            provider
        )
    )

    inspection = ResponseInspection(
        action=ResponseAction.BLOCK,
        content=None,
        reason="Unsafe model response.",
    )

    with patch(
        "app.gateway.routes.inspect_response",
        return_value=inspection,
    ) as inspector:
        response = client.post(
            "/v1/model/generate",
            json=_request_payload(),
        )

    assert (
        response.status_code
        == 403
    )

    body = response.json()

    assert (
        body["detail"]["code"]
        == "response_blocked"
    )

    assert (
        body["detail"]["message"]
        == (
            "The model response was blocked "
            "by AegisTwin security policy."
        )
    )

    assert (
        body["detail"][
            "request_id"
        ].startswith("REQ-")
    )

    # Critical security invariant:
    # blocked model output must never be returned.
    assert (
        unsafe_content
        not in response.text
    )

    inspector.assert_called_once_with(
        unsafe_content
    )