
"""Commercial runtime routes for AegisTwin."""

from __future__ import annotations

from typing import Any, Protocol
from uuid import uuid4

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
    Response,
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

from app.gateway.postgres_http import (
    generate_postgres_response,
)

from app.gateway.postgres_runtime_config import (
    postgres_runtime_enabled,
)

from app.infrastructure.database import (
    SessionLocal,
)

from app.providers.commercial_adapter import (
    CommercialProviderAdapter,
)

from app.providers.errors import (
    ProviderError as RuntimeProviderError,
)

from app.security.llm_response_inspector import (
    ResponseAction,
    inspect_response,
)


# ==================================================
# ROUTER
# ==================================================

router = APIRouter(
    prefix="/v1/model",
    tags=["runtime"],
)


# ==================================================
# EXTERNAL REQUEST MODEL
# ==================================================

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


# ==================================================
# PROVIDER INTERFACE
# ==================================================

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


# ==================================================
# PROVIDER ERROR STATUS MAPPING
# ==================================================

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
# SECURITY: SAFE PROVIDER ERROR MESSAGES
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


def _safe_provider_error_code(
    code: str,
) -> str:
    """Do not expose unknown provider-defined error codes."""

    if code in SAFE_PROVIDER_ERROR_MESSAGES:
        return code

    return "provider_error"


def _provider_http_exception(
    error: RuntimeProviderError,
    request_id: str,
) -> HTTPException:
    """Construct a sanitized public provider error."""

    public_code = _safe_provider_error_code(
        error.code
    )

    return HTTPException(
        status_code=_provider_error_status(error),
        detail={
            "code": public_code,
            "message": SAFE_PROVIDER_ERROR_MESSAGES.get(
                public_code,
                DEFAULT_PROVIDER_ERROR_MESSAGE,
            ),
            "retryable": error.retryable,
            "request_id": request_id,
        },
    )


def _blocked_response_exception(
    request_id: str,
) -> HTTPException:
    """Construct a safe response-inspection error."""

    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={
            "code": "response_blocked",
            "message": (
                "The model response was blocked "
                "by AegisTwin security policy."
            ),
            "request_id": request_id,
        },
    )


# ==================================================
# AUTHENTICATED MODEL GENERATION
# ==================================================

@router.post(
    "/generate",
    response_model=ModelResponse,
)
async def generate_model(
    request: RuntimeModelRequest,
    http_request: Request,
    http_response: Response,
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

    # ==============================================
    # 1. CHECK POSTGRESQL RUNTIME FEATURE FLAG
    # ==============================================

    try:
        use_postgres = postgres_runtime_enabled()

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "runtime_configuration_error",
                "message": (
                    "The runtime is not configured correctly."
                ),
                "request_id": request_id,
            },
        ) from exc

    # ==============================================
    # 2. POSTGRESQL-BACKED INFERENCE
    # ==============================================

    if use_postgres:

        # Read the original client-supplied session ID.
        # Legacy authentication may generate a temporary
        # SES-* ID when this header is absent.
        requested_session_id = http_request.headers.get(
            "X-Aegis-Session-ID"
        )

        if requested_session_id is not None:
            requested_session_id = (
                requested_session_id.strip()
            )

        try:
            # Only open a database session when PostgreSQL
            # runtime is explicitly enabled.
            with SessionLocal() as db:

                result = await generate_postgres_response(
                    model_request=model_request,
                    provider_router=provider_router,
                    db=db,
                    requested_session_id=requested_session_id,
                )

        except RuntimeProviderError as exc:
            # Maintain existing sanitized provider errors.
            raise _provider_http_exception(
                exc,
                request_id,
            ) from exc

        except HTTPException:
            # Preserve safe errors from postgres_http.py.
            raise

        except Exception as exc:
            # Never fall back to legacy inference after
            # an unexpected PostgreSQL runtime failure.
            raise HTTPException(
                status_code=(
                    status.HTTP_503_SERVICE_UNAVAILABLE
                ),
                detail={
                    "code": "runtime_internal_error",
                    "message": (
                        "The runtime could not complete the request."
                    ),
                    "request_id": request_id,
                },
            ) from exc

        # Return the authorized PostgreSQL session UUID.
        http_response.headers[
            "X-Aegis-Session-ID"
        ] = result.session_id

        # Already inspected by run_postgres_inference().
        # Do not perform legacy inspection again.
        return result.response

    # ==============================================
    # 3. LEGACY PROVIDER INFERENCE
    # ==============================================

    try:
        response = await provider_router.generate(
            model_request
        )

    except RuntimeProviderError as exc:
        raise _provider_http_exception(
            exc,
            request_id,
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

    # ==============================================
    # 4. LEGACY POST-LLM RESPONSE INSPECTION
    # ==============================================
    #
    # PostgreSQL inference returned above.
    # Only legacy responses reach this section.
    #

    try:
        # Verify the provider returned the expected model
        # response for this particular request.
        if (
            not isinstance(response, ModelResponse)
            or response.request_id != request_id
            or response.provider != model_request.provider
            or response.model != model_request.model
        ):
            raise _blocked_response_exception(
                request_id
            )

        inspection = inspect_response(
            response.content
        )

        # ------------------------------------------
        # BLOCK
        # ------------------------------------------

        if inspection.action == ResponseAction.BLOCK:
            raise _blocked_response_exception(
                request_id
            )

        # ------------------------------------------
        # REDACT
        # ------------------------------------------

        if inspection.action == ResponseAction.REDACT:

            if not isinstance(
                inspection.content,
                str,
            ):
                raise _blocked_response_exception(
                    request_id
                )

            response = response.model_copy(
                update={
                    "content": inspection.content
                }
            )

        # ------------------------------------------
        # ALLOW
        # ------------------------------------------

        elif inspection.action == ResponseAction.ALLOW:

            # ALLOW must not silently modify the
            # original provider response.
            if (
                not isinstance(inspection.content, str)
                or inspection.content != response.content
            ):
                raise _blocked_response_exception(
                    request_id
                )

        # ------------------------------------------
        # UNKNOWN ACTION
        # ------------------------------------------

        else:
            # Unknown inspector decisions must fail closed.
            raise _blocked_response_exception(
                request_id
            )

    except HTTPException:
        raise

    except Exception:
        # Never release uninspected model content
        # after an unexpected inspector failure.
        raise _blocked_response_exception(
            request_id
        ) from None

    return response
