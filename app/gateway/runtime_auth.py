"""Runtime authentication for customer AI agents."""

from __future__ import annotations

import hmac
import os
import re
from uuid import uuid4

from fastapi import Header, HTTPException, status

from app.contracts import TrustedIdentityContext


RUNTIME_API_KEY_ENV = "AEGISTWIN_RUNTIME_API_KEY"
RUNTIME_TENANT_ID_ENV = "AEGISTWIN_RUNTIME_TENANT_ID"
RUNTIME_USER_ID_ENV = "AEGISTWIN_RUNTIME_USER_ID"
RUNTIME_AGENT_ID_ENV = "AEGISTWIN_RUNTIME_AGENT_ID"


def _required_env(name: str) -> str:
    value = os.getenv(name, "").strip()

    if not value:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                f"Runtime authentication is not configured: "
                f"{name} is missing."
            ),
        )

    return value


async def get_runtime_identity(
    x_aegis_api_key: str | None = Header(
        default=None,
        alias="X-Aegis-API-Key",
    ),
    x_aegis_session_id: str | None = Header(
        default=None,
        alias="X-Aegis-Session-ID",
    ),
) -> TrustedIdentityContext:
    """Authenticate one AI-agent runtime request."""

    expected_key = _required_env(
        RUNTIME_API_KEY_ENV
    )

    # Validate the API key.
    if (
        x_aegis_api_key is None
        or not x_aegis_api_key.strip()
        or not hmac.compare_digest(
            x_aegis_api_key.strip(),
            expected_key,
        )
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=(
                "A valid AegisTwin runtime API key "
                "is required."
            ),
            headers={
                "WWW-Authenticate": "ApiKey"
            },
        )

    # Generate a new session ID if one was not provided.
    session_id = (
        x_aegis_session_id.strip()
        if x_aegis_session_id
        and x_aegis_session_id.strip()
        else f"SES-{uuid4().hex[:12]}"
    )

    # SECURITY: Validate session ID format and length.
    # This does not verify tenant or agent ownership.
    if not re.fullmatch(
        r"[A-Za-z0-9_-]{1,128}",
        session_id,
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid AegisTwin session ID.",
        )

    return TrustedIdentityContext(
        tenant_id=_required_env(
            RUNTIME_TENANT_ID_ENV
        ),
        user_id=_required_env(
            RUNTIME_USER_ID_ENV
        ),
        agent_id=_required_env(
            RUNTIME_AGENT_ID_ENV
        ),
        session_id=session_id,
        permissions=set(),
        credential_source="runtime_api_key",
    )
