
"""Configuration for PostgreSQL-backed commercial runtime."""

from __future__ import annotations

import os


POSTGRES_RUNTIME_ENV = "AEGISTWIN_POSTGRES_RUNTIME_ENABLED"


def postgres_runtime_enabled() -> bool:
    """Return whether database-backed runtime is explicitly enabled.

    Invalid values fail closed instead of silently enabling
    or disabling the configured runtime.
    """

    value = os.getenv(
        POSTGRES_RUNTIME_ENV,
        "false",
    ).strip().lower()

    if value in {"true", "1"}:
        return True

    if value in {"false", "0"}:
        return False

    raise ValueError(
        "Invalid PostgreSQL runtime configuration."
    )
