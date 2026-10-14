from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.contracts import (
    ModelRequest,
    TrustedIdentityContext,
)
from app.gateway.routes import (
    get_provider_router,
    get_runtime_identity,
    router,
)
from app.providers.errors import ProviderError


class FailingProvider:
    def __init__(
        self,
        *,
        code: str,
        retryable: bool,
    ) -> None:
        self.code = code
        self.retryable = retryable

    async def generate(
        self,
        request: ModelRequest,
    ):
        raise ProviderError(
            "Provider failed during test.",
            code=self.code,
            retryable=self.retryable,
        )


def _build_app(
    provider: FailingProvider,
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


def _request_body() -> dict:
    return {
        "provider": "ollama",
        "model": "llama3.2:3b",
        "messages": [
            {
                "role": "user",
                "content": "Hello",
            }
        ],
        "temperature": 0.7,
        "stream": False,
        "metadata": {},
    }


def test_provider_unavailable_maps_to_503() -> None:
    provider = FailingProvider(
        code="provider_unavailable",
        retryable=True,
    )

    client = TestClient(
        _build_app(provider)
    )

    response = client.post(
        "/v1/model/generate",
        json=_request_body(),
    )

    assert response.status_code == 503

    detail = response.json()["detail"]

    assert (
        detail["code"]
        == "provider_unavailable"
    )

    assert (
        detail["retryable"]
        is True
    )

    assert (
        detail["request_id"]
        .startswith("REQ-")
    )


def test_provider_timeout_maps_to_504() -> None:
    provider = FailingProvider(
        code="provider_timeout",
        retryable=True,
    )

    client = TestClient(
        _build_app(provider)
    )

    response = client.post(
        "/v1/model/generate",
        json=_request_body(),
    )

    assert response.status_code == 504

    detail = response.json()["detail"]

    assert (
        detail["code"]
        == "provider_timeout"
    )

    assert (
        detail["retryable"]
        is True
    )


def test_invalid_request_maps_to_400() -> None:
    provider = FailingProvider(
        code="invalid_request",
        retryable=False,
    )

    client = TestClient(
        _build_app(provider)
    )

    response = client.post(
        "/v1/model/generate",
        json=_request_body(),
    )

    assert response.status_code == 400

    detail = response.json()["detail"]

    assert (
        detail["code"]
        == "invalid_request"
    )

    assert (
        detail["retryable"]
        is False
    )