
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.providers.errors import ProviderError
from app.gateway.routes import (
    get_provider_router,
    router,
)
from app.gateway.runtime_auth import (
    RUNTIME_API_KEY_ENV,
)


class SpyProvider:
    def __init__(self):
        self.called = False

    async def generate(self, request):
        self.called = True
        raise AssertionError(
            "Provider must not be called without authentication"
        )


def test_missing_api_key_never_calls_provider(monkeypatch):
    monkeypatch.setenv(
        RUNTIME_API_KEY_ENV,
        "local-test-secret",
    )

    app = FastAPI()
    app.include_router(router)

    provider = SpyProvider()
    app.dependency_overrides[get_provider_router] = (
        lambda: provider
    )

    client = TestClient(app)

    response = client.post(
        "/v1/model/generate",
        json={
            "provider": "ollama",
            "model": "llama3.2:3b",
            "messages": [
                {
                    "role": "user",
                    "content": "Hello",
                }
            ],
        },
    )

    assert response.status_code == 401
    assert provider.called is False

def test_provider_error_does_not_expose_secret(monkeypatch):
    """Provider errors must not expose API credentials."""

    fake_secret = "sk-FAKE-PRIVATE-12345"

    monkeypatch.setenv(
        "AEGISTWIN_RUNTIME_API_KEY",
        "local-test-secret",
    )
    monkeypatch.setenv(
        "AEGISTWIN_RUNTIME_TENANT_ID",
        "test-tenant",
    )
    monkeypatch.setenv(
        "AEGISTWIN_RUNTIME_USER_ID",
        "test-user",
    )
    monkeypatch.setenv(
        "AEGISTWIN_RUNTIME_AGENT_ID",
        "test-agent",
    )

    class LeakingProvider:
        async def generate(self, request):
            raise ProviderError(
                f"External provider rejected key {fake_secret}",
                code="invalid_credentials",
                retryable=False,
            )

    app = FastAPI()
    app.include_router(router)

    app.dependency_overrides[get_provider_router] = (
        lambda: LeakingProvider()
    )

    client = TestClient(app)

    response = client.post(
        "/v1/model/generate",
        headers={
            "X-Aegis-API-Key": "local-test-secret",
        },
        json={
            "provider": "ollama",
            "model": "llama3.2:3b",
            "messages": [
                {
                    "role": "user",
                    "content": "Hello",
                }
            ],
        },
    )

    assert response.status_code == 502
    assert fake_secret not in response.text
    assert response.json()["detail"]["code"] == "invalid_credentials"
