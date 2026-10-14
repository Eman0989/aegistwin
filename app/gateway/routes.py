"""Commercial runtime routes for AegisTwin."""

from __future__ import annotations

from typing import Any, Protocol
from uuid import uuid4

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
)

from app.contracts import (
    ModelRequest,
    ModelResponse,
    TrustedIdentityContext,
)
from app.gateway.runtime_auth import (
    get_runtime_identity,
)
from app.providers.commercial_adapter import (
    CommercialProviderAdapter,
)
from app.providers.errors import (
    ProviderError as RuntimeProviderError,
)


router = APIRouter(
    prefix="/v1/model",
    tags=["runtime"],
)


class RuntimeModelRequest(BaseModel):
    """External request accepted from an AI application.

    Trusted identity is deliberately not accepted
    from the request body. AegisTwin creates trusted
    identity after authentication.
    """

    model_config = ConfigDict(
        extra="forbid"
    )

    provider: str = Field(
        min_length=1
    )

    model: str = Field(
        min_length=1
    )

    messages: list[
        dict[str, Any]
    ] = Field(
        default_factory=list
    )

    temperature: float = Field(
        default=0.7,
        ge=0.0,
        le=2.0,
    )

    stream: bool = False

    metadata: dict[
        str,
        Any,
    ] = Field(
        default_factory=dict
    )


class ProviderRouterProtocol(Protocol):
    """Interface required by the commercial gateway."""

    async def generate(
        self,
        request: ModelRequest,
    ) -> ModelResponse:
        ...


commercial_provider_adapter = CommercialProviderAdapter()


def get_provider_router() -> ProviderRouterProtocol:
    """Return the configured commercial provider adapter."""

    return commercial_provider_adapter


def _provider_error_status(
    error: RuntimeProviderError,
) -> int:
    """Map provider failures to stable gateway HTTP statuses."""

    if error.code in {
        "invalid_request",
        "unsupported_provider",
        "unsupported_temperature",
        "streaming_not_supported",
        "model_not_found",
    }:
        return status.HTTP_400_BAD_REQUEST

    if error.code == "rate_limited":
        return status.HTTP_429_TOO_MANY_REQUESTS

    if error.code == "provider_timeout":
        return status.HTTP_504_GATEWAY_TIMEOUT

    if error.code == "provider_unavailable":
        return status.HTTP_503_SERVICE_UNAVAILABLE

    return status.HTTP_502_BAD_GATEWAY


# ==================================================
# SECURITY: SAFE PUBLIC PROVIDER ERROR MESSAGES
# ==================================================

SAFE_PROVIDER_ERROR_MESSAGES = {
    "invalid_request": (
        "The model request is invalid."
    ),
    "unsupported_provider": (
        "The requested provider is unsupported."
    ),
    "unsupported_temperature": (
        "The temperature setting is unsupported."
    ),
    "streaming_not_supported": (
        "Streaming is not supported."
    ),
    "model_not_found": (
        "The requested model was not found."
    ),
    "rate_limited": (
        "The model provider rate limit was reached."
    ),
    "provider_timeout": (
        "The model provider timed out."
    ),
    "provider_unavailable": (
        "The model provider is unavailable."
    ),
    "invalid_credentials": (
        "Model provider authentication failed."
    ),
}

DEFAULT_PROVIDER_ERROR_MESSAGE = (
    "The configured model provider failed "
    "to process the request."
)


def _safe_provider_error_code(code: str) -> str:
    """Do not expose unknown provider-defined error codes."""

    if code in SAFE_PROVIDER_ERROR_MESSAGES:
        return code

    return "provider_error"


# ==================================================
# AUTHENTICATED MODEL GENERATION
# ==================================================

@router.post(
    "/generate",
    response_model=ModelResponse,
)
async def generate_model(
    request: RuntimeModelRequest,
    identity: TrustedIdentityContext = Depends(
        get_runtime_identity
    ),
    provider_router: ProviderRouterProtocol = Depends(
        get_provider_router
    ),
) -> ModelResponse:
    """Send one authenticated model request through AegisTwin."""

    request_id = f"REQ-{uuid4().hex[:12]}"

    model_request = ModelRequest(
        request_id=request_id,
        provider=request.provider,
        model=request.model,
        messages=request.messages,
        temperature=request.temperature,
        stream=request.stream,
        trusted_context=identity,
        metadata=request.metadata,
    )

    try:
        response = await provider_router.generate(
            model_request
        )

    except RuntimeProviderError as exc:
        # Never return str(exc): a provider exception
        # could contain an API key or other secret.
        public_code = _safe_provider_error_code(
            exc.code
        )

        raise HTTPException(
            status_code=_provider_error_status(exc),
            detail={
                "code": public_code,
                "message": SAFE_PROVIDER_ERROR_MESSAGES.get(
                    public_code,
                    DEFAULT_PROVIDER_ERROR_MESSAGE,
                ),
                "retryable": exc.retryable,
                "request_id": request_id,
            },
        ) from exc

    except HTTPException:
        raise

    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "code": "provider_error",
                "message": DEFAULT_PROVIDER_ERROR_MESSAGE,
                "retryable": False,
                "request_id": request_id,
            },
        ) from exc

    return response
