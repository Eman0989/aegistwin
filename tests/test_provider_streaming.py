
import httpx
import pytest

from app.agents.base import AgentMessage
from app.providers.errors import ProviderError
from app.providers.openai_compatible import (
    OpenAICompatibleProvider,
)


@pytest.mark.asyncio
async def test_successful_stream():
    def handler(request):
        return httpx.Response(
            200,
            headers={
                "content-type": "text/event-stream"
            },
            text=(
                'data: {"choices":[{"delta":{"content":"Hello"}}]}\n\n'
                'data: {"choices":[{"delta":{"content":" world!"}}]}\n\n'
                'data: [DONE]\n\n'
            ),
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

        chunks = [
            chunk
            async for chunk in provider.stream([
                AgentMessage(
                    role="user",
                    content="Hello",
                )
            ])
        ]

        assert chunks == ["Hello", " world!"]


@pytest.mark.asyncio
async def test_interrupted_stream():
    def handler(request):
        return httpx.Response(
            200,
            headers={
                "content-type": "text/event-stream"
            },
            text=(
                'data: {"choices":[{"delta":{"content":"Partial"}}]}\n\n'
            ),
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

        received = []

        with pytest.raises(ProviderError) as error:
            async for chunk in provider.stream([
                AgentMessage(
                    role="user",
                    content="Hello",
                )
            ]):
                received.append(chunk)

        assert received == ["Partial"]
        assert error.value.code == "stream_interrupted"
        assert error.value.retryable is False
