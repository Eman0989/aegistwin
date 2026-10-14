
import os
from time import perf_counter
from collections.abc import AsyncIterator

import httpx

from app.agents.base import AgentMessage, AgentTurn
from app.providers.base import LLMProvider
from app.providers.errors import ProviderError


class OpenAICompatibleProvider(LLMProvider):
    """Connect to an OpenAI-compatible Chat Completions API."""

    def __init__(
        self,
        model: str | None = None,
        base_url: str | None = None,
        api_key: str | None = None,
        client: httpx.AsyncClient | None = None,
    ):
        self.model = model or os.getenv(
            "OPENAI_COMPATIBLE_MODEL", ""
        )
        self.base_url = (
            base_url
            or os.getenv("OPENAI_COMPATIBLE_BASE_URL", "")
        ).rstrip("/")
        self.api_key = api_key or os.getenv(
            "OPENAI_COMPATIBLE_API_KEY", ""
        )
        self.client = client

        if not self.model or not self.base_url:
            raise ValueError(
                "Model and provider base URL are required."
            )

        if not self.base_url.startswith(
            ("https://", "http://")
        ):
            raise ValueError("Invalid provider URL.")

    def _headers(self):
        headers = {
            "Content-Type": "application/json",
        }

        if self.api_key:
            headers["Authorization"] = (
                f"Bearer {self.api_key}"
            )

        return headers

    async def generate(
        self,
        messages: list[AgentMessage],
    ) -> AgentTurn:
        """Generate a real response using Chat Completions."""

        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": message.role,
                    "content": message.content,
                }
                for message in messages
            ],
            "stream": False,
        }

        owns_client = self.client is None
        client = self.client or httpx.AsyncClient(timeout=60)
        started = perf_counter()

        try:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers=self._headers(),
                json=payload,
            )
            response.raise_for_status()

            body = response.json()
            choices = body["choices"]
            content = choices[0]["message"]["content"]

            if not isinstance(content, str):
                raise ValueError("Unexpected message content.")

            usage = body.get("usage") or {}

            return AgentTurn(
                content=content,
                model_name=self.model,
                input_tokens=usage.get(
                    "prompt_tokens", 0
                ) or 0,
                output_tokens=usage.get(
                    "completion_tokens", 0
                ) or 0,
                model_latency_ms=(
                    perf_counter() - started
                ) * 1000,
            )

        except httpx.TimeoutException as error:
            raise ProviderError(
                "Model request timed out.",
                code="provider_timeout",
                retryable=True,
            ) from error

        except httpx.HTTPStatusError as error:
            status = error.response.status_code

            if status in (401, 403):
                code = "invalid_credentials"
            elif status == 404:
                code = "model_not_found"
            elif status == 429:
                code = "rate_limited"
            else:
                code = "provider_error"

            raise ProviderError(
                "Model provider rejected the request.",
                code=code,
                retryable=status in (429, 502, 503, 504),
            ) from error

        except httpx.RequestError as error:
            raise ProviderError(
                "Could not reach model provider.",
                code="provider_unavailable",
                retryable=True,
            ) from error

        except (
            ValueError,
            KeyError,
            IndexError,
            TypeError,
        ) as error:
            raise ProviderError(
                "Invalid model provider response.",
                code="invalid_provider_response",
            ) from error

        finally:
            if owns_client:
                await client.aclose()

    async def stream(
        self,
        messages: list[AgentMessage],
    ) -> AsyncIterator[str]:
        """Streaming implementation comes next."""
        raise NotImplementedError(
            "OpenAI-compatible streaming not implemented yet."
        )
        yield ""

    async def health_check(self) -> bool:
        """Check whether the configured API is reachable."""

        try:
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.get(
                    f"{self.base_url}/models",
                    headers=self._headers(),
                )
                response.raise_for_status()
                return True

        except httpx.HTTPError:
            return False
