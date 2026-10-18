
"""Unit tests for the AegisTwin PostgreSQL recovery worker."""

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy.exc import OperationalError

from app.infrastructure.recovery_worker import (
    RecoveryStats,
    RecoveryWorker,
    discover_expired_tenants,
    run_recovery_cycle,
)


# ==========================================================
# INPUT VALIDATION
# ==========================================================


@pytest.mark.parametrize(
    "limit",
    [0, -1, 1001, True, 1.5, "100"],
)
def test_invalid_tenant_limit_is_rejected(limit):
    with pytest.raises(ValueError):
        discover_expired_tenants(limit=limit)


@pytest.mark.parametrize(
    "batch_size",
    [0, -1, 1001, True, 1.5, "100"],
)
def test_invalid_batch_size_is_rejected(batch_size):
    with pytest.raises(ValueError):
        run_recovery_cycle(batch_size=batch_size)


@pytest.mark.parametrize(
    "interval",
    [0, -1, 3601, True, "15", float("nan"), float("inf")],
)
def test_invalid_worker_interval_is_rejected(interval):
    with pytest.raises(ValueError):
        RecoveryWorker(interval_seconds=interval)


def test_worker_rejects_invalid_limits():
    with pytest.raises(ValueError):
        RecoveryWorker(batch_size=0)

    with pytest.raises(ValueError):
        RecoveryWorker(tenant_limit=1001)


@pytest.mark.parametrize(
    "cursor",
    ["not-a-uuid", 123, True, 1.5],
)
def test_invalid_tenant_cursor_is_rejected(cursor):
    with pytest.raises(ValueError):
        discover_expired_tenants(
            limit=10,
            after_tenant_id=cursor,
        )


# ==========================================================
# TENANT DISCOVERY
# ==========================================================


def test_discover_expired_tenants_uses_database():
    tenant_a = uuid4()
    tenant_b = uuid4()

    database_session = MagicMock()

    database_session.execute.return_value.scalars.return_value.all.return_value = [
        tenant_a,
        tenant_b,
    ]

    with patch(
        "app.infrastructure.recovery_worker.SessionLocal"
    ) as session_local:
        session_local.return_value.__enter__.return_value = (
            database_session
        )

        result = discover_expired_tenants(limit=20)

    assert result == [tenant_a, tenant_b]
    database_session.execute.assert_called_once()


def test_discovery_uses_cursor_when_provided():
    cursor = uuid4()
    tenant = uuid4()

    database_session = MagicMock()

    database_session.execute.return_value.scalars.return_value.all.return_value = [
        tenant,
    ]

    with patch(
        "app.infrastructure.recovery_worker.SessionLocal"
    ) as session_local:
        session_local.return_value.__enter__.return_value = (
            database_session
        )

        result = discover_expired_tenants(
            limit=1,
            after_tenant_id=cursor,
        )

    assert result == [tenant]
    database_session.execute.assert_called_once()


def test_discovery_wraps_after_last_tenant():
    cursor = uuid4()
    tenant = uuid4()

    database_session = MagicMock()

    database_session.execute.return_value.scalars.return_value.all.side_effect = [
        [],
        [tenant],
    ]

    with patch(
        "app.infrastructure.recovery_worker.SessionLocal"
    ) as session_local:
        session_local.return_value.__enter__.return_value = (
            database_session
        )

        result = discover_expired_tenants(
            limit=1,
            after_tenant_id=cursor,
        )

    assert result == [tenant]
    assert database_session.execute.call_count == 2


# ==========================================================
# RECOVERY CYCLE
# ==========================================================


def test_recovery_cycle_counts_recovered_requests():
    tenant_a = uuid4()
    tenant_b = uuid4()

    recovered_a = [uuid4(), uuid4()]
    recovered_b = [uuid4()]

    with (
        patch(
            "app.infrastructure.recovery_worker."
            "discover_expired_tenants",
            return_value=[tenant_a, tenant_b],
        ) as discover,
        patch(
            "app.infrastructure.recovery_worker."
            "recover_expired_requests",
            side_effect=[recovered_a, recovered_b],
        ) as recover,
    ):
        stats = run_recovery_cycle(
            batch_size=10,
            tenant_limit=20,
        )

    assert stats == RecoveryStats(
        tenants_scanned=2,
        requests_recovered=3,
    )

    discover.assert_called_once_with(limit=20)

    assert recover.call_count == 2

    assert recover.call_args_list[0].kwargs == {
        "tenant_id": tenant_a,
        "limit": 10,
    }

    assert recover.call_args_list[1].kwargs == {
        "tenant_id": tenant_b,
        "limit": 10,
    }


def test_recovery_cycle_passes_cursor():
    cursor = uuid4()
    tenant = uuid4()

    with (
        patch(
            "app.infrastructure.recovery_worker."
            "discover_expired_tenants",
            return_value=[tenant],
        ) as discover,
        patch(
            "app.infrastructure.recovery_worker."
            "recover_expired_requests",
            return_value=[],
        ),
    ):
        run_recovery_cycle(
            after_tenant_id=cursor,
        )

    discover.assert_called_once_with(
        limit=100,
        after_tenant_id=cursor,
    )


def test_empty_cycle_recovers_nothing():
    with patch(
        "app.infrastructure.recovery_worker."
        "discover_expired_tenants",
        return_value=[],
    ):
        stats = run_recovery_cycle()

    assert stats.tenants_scanned == 0
    assert stats.requests_recovered == 0


# ==========================================================
# WORKER LIFECYCLE
# ==========================================================


def test_worker_runs_one_cycle():
    """Worker discovers, recovers, and remembers the last tenant."""

    tenant = uuid4()

    worker = RecoveryWorker(
        batch_size=25,
        tenant_limit=10,
    )

    with (
        patch(
            "app.infrastructure.recovery_worker."
            "discover_expired_tenants",
            return_value=[tenant],
        ) as discover,
        patch(
            "app.infrastructure.recovery_worker."
            "recover_expired_requests",
            return_value=[uuid4(), uuid4()],
        ) as recover,
    ):
        result = worker.run_once()

    assert result == RecoveryStats(
        tenants_scanned=1,
        requests_recovered=2,
    )

    assert worker.last_tenant_id == tenant

    discover.assert_called_once_with(limit=10)

    recover.assert_called_once_with(
        tenant_id=tenant,
        limit=25,
    )


def test_worker_rotates_across_tenants():
    """Subsequent cycles must resume after the last scanned tenant."""

    tenant_a = uuid4()
    tenant_b = uuid4()
    tenant_c = uuid4()

    worker = RecoveryWorker(
        tenant_limit=1,
    )

    with (
        patch(
            "app.infrastructure.recovery_worker."
            "discover_expired_tenants",
            side_effect=[
                [tenant_a],
                [tenant_b],
                [tenant_c],
            ],
        ) as discover,
        patch(
            "app.infrastructure.recovery_worker."
            "recover_expired_requests",
            return_value=[],
        ),
    ):
        worker.run_once()
        worker.run_once()
        worker.run_once()

    assert discover.call_count == 3

    assert discover.call_args_list[0].kwargs == {
        "limit": 1,
    }

    assert discover.call_args_list[1].kwargs == {
        "limit": 1,
        "after_tenant_id": tenant_a,
    }

    assert discover.call_args_list[2].kwargs == {
        "limit": 1,
        "after_tenant_id": tenant_b,
    }

    assert worker.last_tenant_id == tenant_c


def test_worker_can_stop():
    worker = RecoveryWorker()

    assert not worker._stop_event.is_set()

    worker.stop()

    assert worker._stop_event.is_set()


def test_worker_stops_after_requested_shutdown():
    worker = RecoveryWorker(interval_seconds=1)

    with patch.object(
        worker,
        "run_once",
        side_effect=lambda: (
            worker.stop()
            or RecoveryStats(0, 0)
        ),
    ) as cycle:
        worker.run_forever()

    cycle.assert_called_once()


# ==========================================================
# DATABASE FAILURE HANDLING
# ==========================================================


def test_database_failure_does_not_crash_worker():
    worker = RecoveryWorker(interval_seconds=1)

    database_error = OperationalError(
        "SELECT expired requests",
        {},
        Exception("private database details"),
    )

    with (
        patch.object(
            worker,
            "run_once",
            side_effect=database_error,
        ) as cycle,
        patch.object(
            worker._stop_event,
            "wait",
            return_value=True,
        ),
    ):
        worker.run_forever()

    cycle.assert_called_once()


def test_worker_retries_after_database_failure():
    worker = RecoveryWorker(interval_seconds=1)

    database_error = OperationalError(
        "SELECT expired requests",
        {},
        Exception("temporary outage"),
    )

    calls = 0

    def cycle():
        nonlocal calls
        calls += 1

        if calls == 1:
            raise database_error

        worker.stop()

        return RecoveryStats(
            tenants_scanned=1,
            requests_recovered=2,
        )

    with (
        patch.object(
            worker,
            "run_once",
            side_effect=cycle,
        ),
        patch.object(
            worker._stop_event,
            "wait",
            return_value=False,
        ),
    ):
        worker.run_forever()

    assert calls == 2


def test_one_tenant_failure_does_not_block_other_tenants():
    """A failure for Tenant A must not stop Tenant B's recovery."""

    tenant_a = uuid4()
    tenant_b = uuid4()

    database_error = OperationalError(
        "UPDATE requests",
        {},
        Exception("private database error"),
    )

    with (
        patch(
            "app.infrastructure.recovery_worker."
            "discover_expired_tenants",
            return_value=[tenant_a, tenant_b],
        ),
        patch(
            "app.infrastructure.recovery_worker."
            "recover_expired_requests",
            side_effect=[
                database_error,
                [uuid4(), uuid4()],
            ],
        ) as recover,
    ):
        stats = run_recovery_cycle()

    assert stats.tenants_scanned == 2
    assert stats.requests_recovered == 2

    assert recover.call_count == 2

    assert (
        recover.call_args_list[0].kwargs["tenant_id"]
        == tenant_a
    )

    assert (
        recover.call_args_list[1].kwargs["tenant_id"]
        == tenant_b
    )
