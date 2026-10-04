"""Shared pytest configuration for AegisTwin."""

from __future__ import annotations

import pytest

from app.auth import (
    ManagementPrincipal,
    ManagementRole,
    require_admin,
    require_security,
    require_viewer,
)
from app.main import app


async def _test_admin_principal() -> ManagementPrincipal:
    """Provide trusted admin identity for legacy regression tests."""

    return ManagementPrincipal(
        role=ManagementRole.ADMIN,
        credential_source="pytest-override",
    )


@pytest.fixture(
    autouse=True,
)
def management_auth_override() -> None:
    """Bypass management auth for existing regression tests.

    Dedicated RBAC API tests explicitly remove these overrides
    so they exercise the real authentication path.
    """

    app.dependency_overrides[
        require_viewer
    ] = _test_admin_principal

    app.dependency_overrides[
        require_security
    ] = _test_admin_principal

    app.dependency_overrides[
        require_admin
    ] = _test_admin_principal

    yield

    app.dependency_overrides.pop(
        require_viewer,
        None,
    )

    app.dependency_overrides.pop(
        require_security,
        None,
    )

    app.dependency_overrides.pop(
        require_admin,
        None,
    )