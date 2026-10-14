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


class ProviderRouterProtocol(
    Protocol
):
    """Interface expected from the LLM provider layer."""

    async def generate(
        self,
        request: ModelRequest,
    ) -> ModelResponse:
        ...


def get_provider_router() -> ProviderRouterProtocol:
    """Temporary provider dependency.

    Emaan's real ProviderRouter will replace
    this implementation during integration.
    """

    raise HTTPException(
        status_code=(
            status.HTTP_503_SERVICE_UNAVAILABLE
        ),
        detail=(
            "LLM provider router is not "
            "configured yet."
        ),
    )


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

    request_id = (
        f"REQ-{uuid4().hex[:12]}"
    )

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
        response = (
            await provider_router.generate(
                model_request
            )
        )

    except HTTPException:
        raise

    except Exception as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_502_BAD_GATEWAY
            ),
            detail=(
                "The configured model provider "
                "failed to process the request."
            ),
        ) from exc

    return response