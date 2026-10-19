
import pytest
import httpx

from app.agents.base import AgentMessage
from app.providers.router import ProviderRouter
from app.providers.ollama import OllamaProvider
from app.providers.openai_compatible import (
    OpenAICompatibleProvider,
)
from app.providers.errors import ProviderError


@pytest.mark.asyncio
async def test_ollama_provider_health():
    def handler(request):
        return httpx.Response(
            200,
            json={
                "models": [{"name": "llama3.2:3b"}]
            },
        )

    transport = httpx.MockTransport(handler)

    # Verify Ollama health without running a real model.
    provider = OllamaProvider()

    original_client = httpx.AsyncClient

    def mock_client(*args, **kwargs):
        return original_client(
            transport=transport,
            **kwargs,
        )

    from unittest.mock import patch

    with patch(
        "app.providers.ollama.httpx.AsyncClient",
        side_effect=mock_client,
    ):
        assert await provider.health_check() is True


@pytest.mark.asyncio
async def test_openai_compatible_generation():
    def handler(request):
        assert request.url.path == "/v1/chat/completions"

        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": "Test response"
                        }
                    }
                ],
                "usage": {
                    "prompt_tokens": 5,
                    "completion_tokens": 3,
                },
            },
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler)
    ) as client:

        provider = OpenAICompatibleProvider(
            model="test-model",
            base_url="https://example.test/v1",
            api_key="test-key",
            client=client,
        )

        response = await provider.generate([
            AgentMessage(
                role="user",
                content="Hello",
            )
        ])

        assert response.content == "Test response"
        assert response.input_tokens == 5
        assert response.output_tokens == 3


@pytest.mark.asyncio
async def test_router_rejects_unknown_provider():
    router = ProviderRouter()

    with pytest.raises(
        ValueError,
        match="Unsupported provider",
    ):
        await router.generate(
            "unknown",
            [AgentMessage(role="user", content="Hi")],
        )


@pytest.mark.asyncio
async def test_openai_invalid_credentials():
    def handler(request):
        return httpx.Response(
            401,
            json={"error": "Unauthorized"},
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler)
    ) as client:

        provider = OpenAICompatibleProvider(
            model="test-model",
            base_url="https://example.test/v1",
            api_key="invalid-key",
            client=client,
        )

        with pytest.raises(ProviderError) as error:
            await provider.generate([
                AgentMessage(
                    role="user",
                    content="Hello",
                )
            ])

        assert error.value.code == "invalid_credentials"
        assert error.value.retryable is False

def test_ollama_uses_local_default(monkeypatch):
    monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)

    provider = OllamaProvider()

    assert provider.base_url == "http://127.0.0.1:11434"


def test_ollama_uses_environment_url(monkeypatch):
    monkeypatch.setenv(
        "OLLAMA_BASE_URL",
        "http://host.docker.internal:11434/",
    )

    provider = OllamaProvider()

    assert provider.base_url == "http://host.docker.internal:11434"


def test_explicit_ollama_url_overrides_environment(monkeypatch):
    monkeypatch.setenv(
        "OLLAMA_BASE_URL",
        "http://host.docker.internal:11434",
    )

    provider = OllamaProvider(
        base_url="http://127.0.0.1:11434"
    )

    assert provider.base_url == "http://127.0.0.1:11434"
