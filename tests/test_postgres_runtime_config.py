
"""Tests for PostgreSQL runtime feature configuration."""

import pytest

from app.gateway.postgres_runtime_config import (
    POSTGRES_RUNTIME_ENV,
    postgres_runtime_enabled,
)


def test_postgres_runtime_disabled_by_default(monkeypatch):
    monkeypatch.delenv(POSTGRES_RUNTIME_ENV, raising=False)

    assert postgres_runtime_enabled() is False


def test_postgres_runtime_accepts_true(monkeypatch):
    monkeypatch.setenv(POSTGRES_RUNTIME_ENV, "true")

    assert postgres_runtime_enabled() is True


def test_postgres_runtime_accepts_one(monkeypatch):
    monkeypatch.setenv(POSTGRES_RUNTIME_ENV, "1")

    assert postgres_runtime_enabled() is True


def test_postgres_runtime_accepts_false(monkeypatch):
    monkeypatch.setenv(POSTGRES_RUNTIME_ENV, "false")

    assert postgres_runtime_enabled() is False


def test_postgres_runtime_accepts_zero(monkeypatch):
    monkeypatch.setenv(POSTGRES_RUNTIME_ENV, "0")

    assert postgres_runtime_enabled() is False


@pytest.mark.parametrize(
    "value",
    ["enabled", "yes", "maybe", "2", ""],
)
def test_invalid_postgres_runtime_config_rejected(
    monkeypatch,
    value,
):
    monkeypatch.setenv(POSTGRES_RUNTIME_ENV, value)

    with pytest.raises(
        ValueError,
        match="Invalid PostgreSQL runtime configuration",
    ):
        postgres_runtime_enabled()
