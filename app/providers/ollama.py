
import json
import httpx

from collections.abc import AsyncIterator

from app.agents.base import AgentMessage, AgentTurn
from app.agents.ollama import OllamaBenchmarkAgent
from app.providers.base import LLMProvider
from app.providers.errors import ProviderError


class OllamaProvider(LLMProvider):
    """Connect AegisTwin to a real local Ollama model."""

    def __init__(
        self,
        model: str = "llama3.2:3b",
        base_url: str = "http://127.0.0.1:11434",
    ):
        self.model = model
        self.base_url = base_url.rstrip("/")

        # Reuse the existing Ollama agent
        self.agent = OllamaBenchmarkAgent(
            model=self.model,
            base_url=self.base_url,
        )

    # ------------------------------------------
    # 1. GENERATE COMPLETE RESPONSE
    # ------------------------------------------

    async def generate(
        self,
        messages: list[AgentMessage],
    ) -> AgentTurn:
        """Generate a complete response from Ollama."""

        try:
            return await self.agent.respond(
                messages=messages,
                tools=[],
            )

        except RuntimeError as error:
            message = str(error)

            if "HTTP 404" in message:
                raise ProviderError(
                    "The requested Ollama model is unavailable.",
                    code="model_not_found",
                    retryable=False,
                ) from error

            if "timed out" in message.lower():
                raise ProviderError(
                    "The model request timed out.",
                    code="provider_timeout",
                    retryable=True,
                ) from error

            if "Cannot connect to Ollama" in message:
                raise ProviderError(
                    "Cannot connect to the Ollama server.",
                    code="provider_unavailable",
                    retryable=True,
                ) from error

            raise ProviderError(
                "The Ollama provider could not complete the request.",
                code="provider_error",
                retryable=False,
            ) from error

    # ------------------------------------------
    # 2. STREAM RESPONSE IN REAL TIME
    # ------------------------------------------

    async def stream(
        self,
        messages: list[AgentMessage],
    ) -> AsyncIterator[str]:
        """Stream text chunks from a real Ollama model."""

        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": message.role,
                    "content": message.content,
                }
                for message in messages
            ],
            "stream": True,
        }

        try:
            async with httpx.AsyncClient(timeout=180) as client:
                async with client.stream(
                    "POST",
                    f"{self.base_url}/api/chat",
                    json=payload,
                ) as response:

                    response.raise_for_status()

                    async for line in response.aiter_lines():
                        if not line:
                            continue

                        data = json.loads(line)

                        if "error" in data:
                            raise ProviderError(
                                "Ollama streaming failed.",
                                code="provider_error",
                            )

                        message = data.get("message") or {}
                        if not isinstance(message, dict):
                            raise ProviderError(
                                "Invalid Ollama stream message.",
                                code="invalid_provider_response",
                            )

                        content = message.get("content", "")

                        if content:
                            yield content

                        if data.get("done", False):
                            break

        except httpx.TimeoutException as error:
            raise ProviderError(
                "Ollama stream timed out.",
                code="provider_timeout",
                retryable=False,
            ) from error

        except httpx.HTTPStatusError as error:
            code = (
                "model_not_found"
                if error.response.status_code == 404
                else "provider_error"
            )

            raise ProviderError(
                "Ollama rejected the streaming request.",
                code=code,
                retryable=False,
            ) from error

        except httpx.RequestError as error:
            raise ProviderError(
                "Ollama streaming connection failed.",
                code="provider_unavailable",
                retryable=False,
            ) from error

        except (
            json.JSONDecodeError,
            TypeError,
            ValueError,
        ) as error:
            raise ProviderError(
                "Invalid streaming response from Ollama.",
                code="invalid_provider_response",
            ) from error

    # ------------------------------------------
    # 3. CHECK MODEL AVAILABILITY
    # ------------------------------------------

    async def health_check(self) -> bool:
        """Check that the local Ollama model is installed."""

        try:
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.get(
                    f"{self.base_url}/api/tags"
                )

                response.raise_for_status()

                models = response.json().get("models", [])

                return any(
                    item.get("name") == self.model
                    for item in models
                )

        except (
            httpx.HTTPError,
            ValueError,
            TypeError,
        ):
            return False
