
import json
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

        self.api_key = (
            api_key
            if api_key is not None
            else os.getenv("OPENAI_COMPATIBLE_API_KEY", "")
        )

        self.client = client

        if not self.model or not self.base_url:
            raise ValueError(
                "Model and provider base URL are required."
            )

        if not self.base_url.startswith(
            ("https://", "http://")
        ):
            raise ValueError(
                "Invalid provider URL."
            )

    # -----------------------------------------
    # 1. AUTHENTICATION HEADERS
    # -----------------------------------------

    def _headers(self) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
        }

        if self.api_key:
            headers["Authorization"] = (
                f"Bearer {self.api_key}"
            )

        return headers

    # -----------------------------------------
    # 2. FORMAT MESSAGES
    # -----------------------------------------

    def _messages(
        self,
        messages: list[AgentMessage],
    ) -> list[dict]:
        return [
            {
                "role": message.role,
                "content": message.content,
            }
            for message in messages
        ]

    # -----------------------------------------
    # 3. ERROR HANDLING
    # -----------------------------------------

    def _handle_http_error(
        self,
        error: httpx.HTTPStatusError,
    ) -> ProviderError:

        status = error.response.status_code

        if status in (401, 403):
            return ProviderError(
                "Invalid provider credentials or access denied.",
                code="invalid_credentials",
                retryable=False,
            )

        if status == 404:
            return ProviderError(
                "The requested model or endpoint was not found.",
                code="model_not_found",
                retryable=False,
            )

        if status == 429:
            return ProviderError(
                "Provider rate limit exceeded.",
                code="rate_limited",
                retryable=True,
            )

        return ProviderError(
            "Model provider rejected the request.",
            code="provider_error",
            retryable=status in (502, 503, 504),
        )

    # -----------------------------------------
    # 4. GENERATE COMPLETE RESPONSE
    # -----------------------------------------

    async def generate(
        self,
        messages: list[AgentMessage],
    ) -> AgentTurn:
        """Generate one complete model response."""

        payload = {
            "model": self.model,
            "messages": self._messages(messages),
            "stream": False,
        }

        owns_client = self.client is None

        client = self.client or httpx.AsyncClient(
            timeout=60
        )

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
                raise ValueError(
                    "Unexpected model response content."
                )

            usage = body.get("usage") or {}

            return AgentTurn(
                content=content,
                model_name=self.model,
                input_tokens=int(
                    usage.get("prompt_tokens", 0) or 0
                ),
                output_tokens=int(
                    usage.get("completion_tokens", 0) or 0
                ),
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
            raise self._handle_http_error(error) from error

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

    # -----------------------------------------
    # 5. REAL-TIME STREAMING
    # -----------------------------------------

    async def stream(
        self,
        messages: list[AgentMessage],
    ) -> AsyncIterator[str]:
        """Stream response chunks from a compatible API."""

        payload = {
            "model": self.model,
            "messages": self._messages(messages),
            "stream": True,
        }

        owns_client = self.client is None

        client = self.client or httpx.AsyncClient(
            timeout=180
        )

        completed = False

        try:
            async with client.stream(
                "POST",
                f"{self.base_url}/chat/completions",
                headers=self._headers(),
                json=payload,
            ) as response:

                response.raise_for_status()

                async for line in response.aiter_lines():

                    if not line.startswith("data:"):
                        continue

                    data = line[5:].strip()

                    if data == "[DONE]":
                        completed = True
                        break

                    try:
                        event = json.loads(data)
                        choices = event.get("choices", [])

                        if not isinstance(choices, list):
                            raise ValueError(
                                "Invalid streaming choices."
                            )

                        for choice in choices:
                            if not isinstance(choice, dict):
                                raise ValueError(
                                    "Invalid streaming choice."
                                )

                            delta = choice.get("delta") or {}

                            if not isinstance(delta, dict):
                                raise ValueError(
                                    "Invalid streaming delta."
                                )

                            content = delta.get("content")

                            if content is not None:
                                if not isinstance(content, str):
                                    raise ValueError(
                                        "Invalid stream content."
                                    )

                                if content:
                                    yield content

                    except (
                        json.JSONDecodeError,
                        TypeError,
                        ValueError,
                        AttributeError,
                    ) as error:
                        raise ProviderError(
                            "Invalid provider streaming data.",
                            code="invalid_provider_response",
                        ) from error

                if not completed:
                    raise ProviderError(
                        "Model stream ended before completion.",
                        code="stream_interrupted",
                        retryable=False,
                    )

        except httpx.TimeoutException as error:
            raise ProviderError(
                "Streaming request timed out.",
                code="provider_timeout",
                retryable=False,
            ) from error

        except httpx.HTTPStatusError as error:
            raise self._handle_http_error(error) from error

        except httpx.RequestError as error:
            raise ProviderError(
                "Streaming connection failed.",
                code="provider_unavailable",
                retryable=False,
            ) from error

        finally:
            if owns_client:
                await client.aclose()

    # -----------------------------------------
    # 6. HEALTH CHECK
    # -----------------------------------------

    async def health_check(self) -> bool:
        """Check whether the provider's models API works."""

        owns_client = self.client is None

        client = self.client or httpx.AsyncClient(
            timeout=5
        )

        try:
            response = await client.get(
                f"{self.base_url}/models",
                headers=self._headers(),
            )

            response.raise_for_status()

            return True

        except httpx.HTTPError:
            return False

        finally:
            if owns_client:
                await client.aclose()
