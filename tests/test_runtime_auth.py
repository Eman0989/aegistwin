import asyncio

import pytest
from fastapi import HTTPException

from app.gateway.runtime_auth import (
    RUNTIME_AGENT_ID_ENV,
    RUNTIME_API_KEY_ENV,
    RUNTIME_TENANT_ID_ENV,
    RUNTIME_USER_ID_ENV,
    get_runtime_identity,
)


def _configure_runtime_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        RUNTIME_API_KEY_ENV,
        "test-runtime-key",
    )
    monkeypatch.setenv(
        RUNTIME_TENANT_ID_ENV,
        "tenant-demo",
    )
    monkeypatch.setenv(
        RUNTIME_USER_ID_ENV,
        "user-demo",
    )
    monkeypatch.setenv(
        RUNTIME_AGENT_ID_ENV,
        "agent-demo",
    )


def test_runtime_auth_requires_configuration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(
        RUNTIME_API_KEY_ENV,
        raising=False,
    )

    with pytest.raises(
        HTTPException
    ) as exc_info:
        asyncio.run(
            get_runtime_identity(
                x_aegis_api_key="anything",
                x_aegis_session_id="session-1",
            )
        )

    assert (
        exc_info.value.status_code
        == 503
    )


def test_runtime_auth_rejects_invalid_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_runtime_identity(
        monkeypatch
    )

    with pytest.raises(
        HTTPException
    ) as exc_info:
        asyncio.run(
            get_runtime_identity(
                x_aegis_api_key="wrong-key",
                x_aegis_session_id="session-1",
            )
        )

    assert (
        exc_info.value.status_code
        == 401
    )


def test_runtime_auth_builds_trusted_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_runtime_identity(
        monkeypatch
    )

    identity = asyncio.run(
        get_runtime_identity(
            x_aegis_api_key="test-runtime-key",
            x_aegis_session_id="session-123",
        )
    )

    assert identity.tenant_id == "tenant-demo"
    assert identity.user_id == "user-demo"
    assert identity.agent_id == "agent-demo"
    assert identity.session_id == "session-123"
    assert identity.permissions == set()
    assert (
        identity.credential_source
        == "runtime_api_key"
    )


def test_runtime_auth_generates_session_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_runtime_identity(
        monkeypatch
    )

    identity = asyncio.run(
        get_runtime_identity(
            x_aegis_api_key="test-runtime-key",
            x_aegis_session_id=None,
        )
    )

    assert identity.session_id.startswith(
        "SES-"
    )