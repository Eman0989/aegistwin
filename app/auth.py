"""Management API authentication and role-based access control."""

from __future__ import annotations

import hmac
import os
from dataclasses import dataclass
from enum import IntEnum

from fastapi import (
    Depends,
    Header,
    HTTPException,
    status,
)


VIEWER_KEY_ENV = (
    "AEGISTWIN_VIEWER_KEY"
)

SECURITY_KEY_ENV = (
    "AEGISTWIN_SECURITY_KEY"
)

ADMIN_KEY_ENV = (
    "AEGISTWIN_ADMIN_KEY"
)


class ManagementRole(
    IntEnum
):
    """Ordered management roles.

    Higher numeric values inherit permissions
    from lower roles.
    """

    VIEWER = 10
    SECURITY = 20
    ADMIN = 30


@dataclass(
    frozen=True
)
class ManagementPrincipal:
    """Authenticated management API identity."""

    role: ManagementRole
    credential_source: str = (
        "x-api-key"
    )

    @property
    def role_name(
        self,
    ) -> str:
        return (
            self.role.name.lower()
        )


def _configured_keys() -> dict[
    ManagementRole,
    str,
]:
    """Return configured management API keys.

    Empty environment variables are ignored.
    """

    raw_keys = {
        ManagementRole.VIEWER: (
            os.getenv(
                VIEWER_KEY_ENV,
                "",
            )
        ),
        ManagementRole.SECURITY: (
            os.getenv(
                SECURITY_KEY_ENV,
                "",
            )
        ),
        ManagementRole.ADMIN: (
            os.getenv(
                ADMIN_KEY_ENV,
                "",
            )
        ),
    }

    return {
        role: key.strip()
        for role, key
        in raw_keys.items()
        if key.strip()
    }


def _authenticate_key(
    api_key: str,
) -> ManagementPrincipal | None:
    """Resolve an API key to the strongest matching role."""

    configured = (
        _configured_keys()
    )

    # Check strongest role first.
    for role in (
        ManagementRole.ADMIN,
        ManagementRole.SECURITY,
        ManagementRole.VIEWER,
    ):
        expected = (
            configured.get(
                role
            )
        )

        if expected is None:
            continue

        if hmac.compare_digest(
            api_key,
            expected,
        ):
            return (
                ManagementPrincipal(
                    role=role
                )
            )

    return None


def _authentication_unavailable() -> HTTPException:
    return HTTPException(
        status_code=(
            status
            .HTTP_503_SERVICE_UNAVAILABLE
        ),
        detail=(
            "Management authentication is not "
            "configured. Set at least one AegisTwin "
            "management API key."
        ),
    )


def _authentication_required() -> HTTPException:
    return HTTPException(
        status_code=(
            status
            .HTTP_401_UNAUTHORIZED
        ),
        detail=(
            "A valid management API key is required."
        ),
        headers={
            "WWW-Authenticate": (
                "ApiKey"
            )
        },
    )


def _insufficient_role(
    required: ManagementRole,
) -> HTTPException:
    return HTTPException(
        status_code=(
            status
            .HTTP_403_FORBIDDEN
        ),
        detail=(
            "Insufficient management role. "
            f"Required role: "
            f"{required.name.lower()}."
        ),
    )


async def get_management_principal(
    x_api_key: str | None = Header(
        default=None,
        alias="X-API-Key",
    ),
) -> ManagementPrincipal:
    """Authenticate one management API request."""

    configured = (
        _configured_keys()
    )

    if not configured:
        raise (
            _authentication_unavailable()
        )

    if (
        x_api_key is None
        or not x_api_key.strip()
    ):
        raise (
            _authentication_required()
        )

    principal = (
        _authenticate_key(
            x_api_key.strip()
        )
    )

    if principal is None:
        raise (
            _authentication_required()
        )

    return principal


def _require_minimum_role(
    principal: ManagementPrincipal,
    required: ManagementRole,
) -> ManagementPrincipal:
    if (
        principal.role
        < required
    ):
        raise (
            _insufficient_role(
                required
            )
        )

    return principal


async def require_viewer(
    principal: ManagementPrincipal = Depends(
        get_management_principal
    ),
) -> ManagementPrincipal:
    """Allow viewer, security, and admin."""

    return (
        _require_minimum_role(
            principal,
            ManagementRole.VIEWER,
        )
    )


async def require_security(
    principal: ManagementPrincipal = Depends(
        get_management_principal
    ),
) -> ManagementPrincipal:
    """Allow security and admin."""

    return (
        _require_minimum_role(
            principal,
            ManagementRole.SECURITY,
        )
    )


async def require_admin(
    principal: ManagementPrincipal = Depends(
        get_management_principal
    ),
) -> ManagementPrincipal:
    """Allow only admin."""

    return (
        _require_minimum_role(
            principal,
            ManagementRole.ADMIN,
        )
    )