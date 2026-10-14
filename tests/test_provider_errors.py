
import pytest
import httpx

from app.agents.base import AgentMessage
from app.providers.openai_compatible import OpenAICompatibleProvider
from app.providers.errors import ProviderError


@pytest.mark.asyncio
async def test_provider_connection_failure():

    def fail_connection(request):
        raise httpx.ConnectError(
            "Connection refused",
            request=request,
        )

    transport = httpx.MockTransport(fail_connection)

    async with httpx.AsyncClient(
        transport=transport
    ) as client:

        provider = OpenAICompatibleProvider(
            model="test-model",
            base_url="https://example.test/v1",
            api_key="test-key",
            client=client,
        )

        with pytest.raises(ProviderError) as error:
            await provider.generate([
                AgentMessage(
                    role="user",
                    content="Hello",
                )
            ])

        assert error.value.code == "provider_unavailable"
        assert error.value.retryable is True


@pytest.mark.asyncio
async def test_provider_timeout():

    def timeout(request):
        raise httpx.ReadTimeout(
            "Request timed out",
            request=request,
        )

    transport = httpx.MockTransport(timeout)

    async with httpx.AsyncClient(
        transport=transport
    ) as client:

        provider = OpenAICompatibleProvider(
            model="test-model",
            base_url="https://example.test/v1",
            api_key="test-key",
            client=client,
        )

        with pytest.raises(ProviderError) as error:
            await provider.generate([
                AgentMessage(
                    role="user",
                    content="Hello",
                )
            ])

        assert error.value.code == "provider_timeout"
        assert error.value.retryable is True
