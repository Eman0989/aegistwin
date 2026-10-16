
"""PostgreSQL-backed inference and response inspection."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from sqlalchemy.orm import Session

from app.contracts import ModelRequest, ModelResponse
from app.gateway.postgres_request_lifecycle import (
    start_request,
    finish_request,
)
from app.gateway.postgres_session_manager import (
    manage_postgres_session,
)
from app.providers.errors import ProviderError
from app.security.llm_response_inspector import (
    ResponseAction,
    inspect_response,
)


class ProviderProtocol(Protocol):
    async def generate(
        self,
        request: ModelRequest,
    ) -> ModelResponse:
        ...


class ResponseBlockedError(Exception):
    """The generated response cannot be released."""


@dataclass(frozen=True)
class OrchestrationResult:
    response: ModelResponse
    session_id: str


async def run_postgres_inference(
    *,
    model_request: ModelRequest,
    provider_router: ProviderProtocol,
    db: Session,
    requested_session_id: str | None,
) -> OrchestrationResult:
    """Execute one authorized and audited model request."""

    # ==============================================
    # 1. AUTHORIZE OR CREATE POSTGRESQL SESSION
    # ==============================================

    managed = manage_postgres_session(
        identity=model_request.trusted_context,
        db=db,
        requested_session_id=requested_session_id,
    )

    # Replace the legacy session ID with the
    # authorized PostgreSQL UUID.
    authorized_request = model_request.model_copy(
        update={
            "trusted_context": managed.identity,
        }
    )

    # ==============================================
    # 2. CREATE PENDING DATABASE REQUEST
    # ==============================================

    persisted = start_request(
        identity=managed.identity,
        public_request_id=authorized_request.request_id,
        provider=authorized_request.provider,
        model=authorized_request.model,
        db=db,
    )

    # Commit session and pending request together.
    # Provider inference must not begin if this fails.
    db.commit()

    # ==============================================
    # 3. PROVIDER INFERENCE
    # ==============================================

    try:
        response = await provider_router.generate(
            authorized_request
        )

    except ProviderError as exc:
        finish_request(
            request=persisted,
            outcome="failed",
            error_code=exc.code,
        )
        raise

    except Exception:
        finish_request(
            request=persisted,
            outcome="failed",
            error_code="provider_error",
        )
        raise

    # ==============================================
    # 4. VERIFY PROVIDER RESPONSE INTEGRITY
    # ==============================================

    if (
        not isinstance(response, ModelResponse)
        or response.request_id != authorized_request.request_id
        or response.provider != authorized_request.provider
        or response.model != authorized_request.model
    ):
        finish_request(
            request=persisted,
            outcome="blocked",
        )

        raise ResponseBlockedError(
            "The model response failed integrity validation."
        )

    # ==============================================
    # 5. INSPECT GENERATED MODEL CONTENT
    # ==============================================

    try:
        inspection = inspect_response(
            response.content
        )

    except Exception:
        # Never release uninspected content.
        finish_request(
            request=persisted,
            outcome="blocked",
        )

        raise ResponseBlockedError(
            "The model response was blocked by security policy."
        ) from None

    # ==============================================
    # 6. BLOCK
    # ==============================================

    if inspection.action == ResponseAction.BLOCK:
        finish_request(
            request=persisted,
            outcome="blocked",
        )

        raise ResponseBlockedError(
            "The model response was blocked by security policy."
        )

    # ==============================================
    # 7. REDACT
    # ==============================================

    if inspection.action == ResponseAction.REDACT:
        if not isinstance(inspection.content, str):
            finish_request(
                request=persisted,
                outcome="blocked",
            )

            raise ResponseBlockedError(
                "The model response was blocked by security policy."
            )

        response = response.model_copy(
            update={
                "content": inspection.content,
            }
        )

    # ==============================================
    # 8. ALLOW
    # ==============================================

    elif inspection.action == ResponseAction.ALLOW:
        # ALLOW must preserve the exact original text.
        if (
            not isinstance(inspection.content, str)
            or inspection.content != response.content
        ):
            finish_request(
                request=persisted,
                outcome="blocked",
            )

            raise ResponseBlockedError(
                "The model response failed inspection validation."
            )

    # ==============================================
    # 9. REJECT UNKNOWN INSPECTION ACTIONS
    # ==============================================

    else:
        finish_request(
            request=persisted,
            outcome="blocked",
        )

        raise ResponseBlockedError(
            "The model response was blocked by security policy."
        )

    # ==============================================
    # SECURITY: VALIDATE PROVIDER USAGE METRICS
    # ==============================================

    usage = response.usage

    def valid_token_count(value):
        return (
            value is None
            or (
                type(value) is int
                and value >= 0
            )
        )

    if (
        not isinstance(usage, dict)
        or not valid_token_count(usage.get("input_tokens"))
        or not valid_token_count(usage.get("output_tokens"))
        or (
            not isinstance(response.latency_ms, (int, float))
            or isinstance(response.latency_ms, bool)
            or not __import__("math").isfinite(response.latency_ms)
            or response.latency_ms < 0
        )
    ):
        finish_request(
            request=persisted,
            outcome="blocked",
        )

        raise ResponseBlockedError(
            "The model response failed usage validation."
        )

    # ==============================================
    # 10. COMPLETE POSTGRESQL AUDIT RECORD
    # ==============================================

    # IMPORTANT:
    # This block must remain OUTSIDE all
    # ALLOW / REDACT / BLOCK conditions.
    #
    # Both successful and redacted responses
    # must be persisted before release.

    finish_request(
        request=persisted,
        outcome="completed",
        latency_ms=response.latency_ms,
        input_tokens=response.usage.get("input_tokens"),
        output_tokens=response.usage.get("output_tokens"),
    )

    # ==============================================
    # 11. RETURN AUTHORIZED RESPONSE
    # ==============================================

    return OrchestrationResult(
        response=response,
        session_id=str(managed.session_id),
    )
