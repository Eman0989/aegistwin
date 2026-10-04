from __future__ import annotations

import os

import pytest
from fastapi import HTTPException

from app.auth import (
    ADMIN_KEY_ENV,
    SECURITY_KEY_ENV,
    VIEWER_KEY_ENV,
    ManagementRole,
    get_management_principal,
    require_admin,
    require_security,
    require_viewer,
)


@pytest.fixture(
    autouse=True,
)
def clear_management_keys(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for key_name in (
        VIEWER_KEY_ENV,
        SECURITY_KEY_ENV,
        ADMIN_KEY_ENV,
    ):
        monkeypatch.delenv(
            key_name,
            raising=False,
        )


@pytest.mark.asyncio
async def test_authentication_fails_closed_when_no_keys_configured() -> None:
    with pytest.raises(
        HTTPException
    ) as exc_info:
        await get_management_principal(
            None
        )

    assert (
        exc_info.value.status_code
        == 503
    )

    assert (
        "not configured"
        in exc_info.value.detail.lower()
    )


@pytest.mark.asyncio
async def test_missing_key_returns_401(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        VIEWER_KEY_ENV,
        "viewer-secret",
    )

    with pytest.raises(
        HTTPException
    ) as exc_info:
        await get_management_principal(
            None
        )

    assert (
        exc_info.value.status_code
        == 401
    )


@pytest.mark.asyncio
async def test_invalid_key_returns_401(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        VIEWER_KEY_ENV,
        "viewer-secret",
    )

    with pytest.raises(
        HTTPException
    ) as exc_info:
        await get_management_principal(
            "wrong-secret"
        )

    assert (
        exc_info.value.status_code
        == 401
    )


@pytest.mark.asyncio
async def test_viewer_key_authenticates_as_viewer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        VIEWER_KEY_ENV,
        "viewer-secret",
    )

    principal = (
        await get_management_principal(
            "viewer-secret"
        )
    )

    assert (
        principal.role
        == ManagementRole.VIEWER
    )

    assert (
        principal.role_name
        == "viewer"
    )


@pytest.mark.asyncio
async def test_security_key_authenticates_as_security(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        SECURITY_KEY_ENV,
        "security-secret",
    )

    principal = (
        await get_management_principal(
            "security-secret"
        )
    )

    assert (
        principal.role
        == ManagementRole.SECURITY
    )


@pytest.mark.asyncio
async def test_admin_key_authenticates_as_admin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        ADMIN_KEY_ENV,
        "admin-secret",
    )

    principal = (
        await get_management_principal(
            "admin-secret"
        )
    )

    assert (
        principal.role
        == ManagementRole.ADMIN
    )


@pytest.mark.asyncio
async def test_viewer_requirement_accepts_all_roles(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        VIEWER_KEY_ENV,
        "viewer-secret",
    )

    monkeypatch.setenv(
        SECURITY_KEY_ENV,
        "security-secret",
    )

    monkeypatch.setenv(
        ADMIN_KEY_ENV,
        "admin-secret",
    )

    viewer = (
        await get_management_principal(
            "viewer-secret"
        )
    )

    security = (
        await get_management_principal(
            "security-secret"
        )
    )

    admin = (
        await get_management_principal(
            "admin-secret"
        )
    )

    assert (
        await require_viewer(
            viewer
        )
    ).role == ManagementRole.VIEWER

    assert (
        await require_viewer(
            security
        )
    ).role == ManagementRole.SECURITY

    assert (
        await require_viewer(
            admin
        )
    ).role == ManagementRole.ADMIN


@pytest.mark.asyncio
async def test_security_requirement_rejects_viewer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        VIEWER_KEY_ENV,
        "viewer-secret",
    )

    viewer = (
        await get_management_principal(
            "viewer-secret"
        )
    )

    with pytest.raises(
        HTTPException
    ) as exc_info:
        await require_security(
            viewer
        )

    assert (
        exc_info.value.status_code
        == 403
    )

    assert (
        "security"
        in exc_info.value.detail.lower()
    )


@pytest.mark.asyncio
async def test_security_requirement_accepts_security_and_admin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        SECURITY_KEY_ENV,
        "security-secret",
    )

    monkeypatch.setenv(
        ADMIN_KEY_ENV,
        "admin-secret",
    )

    security = (
        await get_management_principal(
            "security-secret"
        )
    )

    admin = (
        await get_management_principal(
            "admin-secret"
        )
    )

    assert (
        await require_security(
            security
        )
    ).role == ManagementRole.SECURITY

    assert (
        await require_security(
            admin
        )
    ).role == ManagementRole.ADMIN


@pytest.mark.asyncio
async def test_admin_requirement_rejects_lower_roles(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        VIEWER_KEY_ENV,
        "viewer-secret",
    )

    monkeypatch.setenv(
        SECURITY_KEY_ENV,
        "security-secret",
    )

    viewer = (
        await get_management_principal(
            "viewer-secret"
        )
    )

    security = (
        await get_management_principal(
            "security-secret"
        )
    )

    with pytest.raises(
        HTTPException
    ) as viewer_error:
        await require_admin(
            viewer
        )

    assert (
        viewer_error.value.status_code
        == 403
    )

    with pytest.raises(
        HTTPException
    ) as security_error:
        await require_admin(
            security
        )

    assert (
        security_error.value.status_code
        == 403
    )


@pytest.mark.asyncio
async def test_admin_requirement_accepts_admin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        ADMIN_KEY_ENV,
        "admin-secret",
    )

    admin = (
        await get_management_principal(
            "admin-secret"
        )
    )

    result = (
        await require_admin(
            admin
        )
    )

    assert (
        result.role
        == ManagementRole.ADMIN
    )


@pytest.mark.asyncio
async def test_duplicate_key_resolves_to_strongest_role(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        VIEWER_KEY_ENV,
        "shared-secret",
    )

    monkeypatch.setenv(
        ADMIN_KEY_ENV,
        "shared-secret",
    )

    principal = (
        await get_management_principal(
            "shared-secret"
        )
    )

    assert (
        principal.role
        == ManagementRole.ADMIN
    )