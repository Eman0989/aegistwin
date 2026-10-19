
"""Standalone PostgreSQL recovery worker for expired AegisTwin requests.

Run continuously:
    python -m app.infrastructure.recovery_worker

Run one cycle:
    python -m app.infrastructure.recovery_worker --once

Recovery transitions expired leased requests to "recovered".
It never retries inference or calls an LLM provider.
"""

from __future__ import annotations

import argparse
import logging
import math
import signal
import threading
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError

from app.infrastructure.database import SessionLocal
from app.infrastructure.models import AgentRequest
from app.infrastructure.persistence import recover_expired_requests


logger = logging.getLogger("aegistwin.recovery")


@dataclass(frozen=True)
class RecoveryStats:
    tenants_scanned: int
    requests_recovered: int


def _validate_limit(value: int, name: str) -> None:
    if type(value) is not int or not 1 <= value <= 1000:
        raise ValueError(
            f"{name} must be an integer between 1 and 1000."
        )


def discover_expired_tenants(
    limit: int = 100,
    after_tenant_id: UUID | None = None,
) -> list[UUID]:
    """Discover tenants with expired leases using cursor pagination.

    When a cursor is provided, scan tenant UUIDs greater
    than the cursor first. Then wrap around to lower UUIDs.

    This prevents a persistent backlog in the first tenants
    from permanently starving later tenants.
    """

    _validate_limit(limit, "tenant limit")

    if (
        after_tenant_id is not None
        and not isinstance(after_tenant_id, UUID)
    ):
        raise ValueError("Invalid tenant cursor.")

    filters = (
        AgentRequest.status == "pending",
        AgentRequest.lease_token.is_not(None),
        AgentRequest.lease_expires_at.is_not(None),
        AgentRequest.lease_expires_at
        <= func.clock_timestamp(),
    )

    with SessionLocal() as db:

        def fetch(
            extra_condition=None,
            count: int = limit,
        ) -> list[UUID]:
            conditions = filters

            if extra_condition is not None:
                conditions = conditions + (extra_condition,)

            statement = (
                select(AgentRequest.tenant_id)
                .where(*conditions)
                .distinct()
                .order_by(AgentRequest.tenant_id)
                .limit(count)
            )

            return list(
                db.execute(statement).scalars().all()
            )

        if after_tenant_id is None:
            return fetch()

        tenants = fetch(
            AgentRequest.tenant_id > after_tenant_id
        )

        if len(tenants) < limit:
            remaining = limit - len(tenants)

            tenants.extend(
                fetch(
                    AgentRequest.tenant_id <= after_tenant_id,
                    count=remaining,
                )
            )

        return tenants


def _execute_recovery(
    tenants: list[UUID],
    *,
    batch_size: int,
) -> int:
    """Recover each tenant independently."""

    recovered_count = 0

    for tenant_id in tenants:
        try:
            recovered_ids = recover_expired_requests(
                tenant_id=tenant_id,
                limit=batch_size,
            )

        except SQLAlchemyError:
            logger.error(
                "Recovery failed for a tenant; continuing."
            )
            continue

        recovered_count += len(recovered_ids)

    return recovered_count


def run_recovery_cycle(
    *,
    batch_size: int = 100,
    tenant_limit: int = 100,
    after_tenant_id: UUID | None = None,
) -> RecoveryStats:
    """Execute one bounded recovery cycle."""

    _validate_limit(batch_size, "batch size")
    _validate_limit(tenant_limit, "tenant limit")

    if after_tenant_id is None:
        tenants = discover_expired_tenants(
            limit=tenant_limit,
        )
    else:
        tenants = discover_expired_tenants(
            limit=tenant_limit,
            after_tenant_id=after_tenant_id,
        )

    recovered_count = _execute_recovery(
        tenants,
        batch_size=batch_size,
    )

    return RecoveryStats(
        tenants_scanned=len(tenants),
        requests_recovered=recovered_count,
    )


class RecoveryWorker:
    """Periodically recover expired PostgreSQL requests."""

    def __init__(
        self,
        *,
        interval_seconds: float = 15.0,
        batch_size: int = 100,
        tenant_limit: int = 100,
    ):
        if (
            isinstance(interval_seconds, bool)
            or not isinstance(interval_seconds, (int, float))
            or not math.isfinite(interval_seconds)
            or not 1 <= interval_seconds <= 3600
        ):
            raise ValueError(
                "Recovery interval must be between "
                "1 and 3600 seconds."
            )

        _validate_limit(batch_size, "batch size")
        _validate_limit(tenant_limit, "tenant limit")

        self.interval_seconds = float(interval_seconds)
        self.batch_size = batch_size
        self.tenant_limit = tenant_limit

        self.last_tenant_id: UUID | None = None
        self._stop_event = threading.Event()

    def stop(self) -> None:
        """Request graceful shutdown."""

        self._stop_event.set()

    def run_once(self) -> RecoveryStats:
        """Run one recovery cycle and advance the tenant cursor.

        The cursor is advanced only after discovery succeeds.
        """

        if self.last_tenant_id is None:
            tenants = discover_expired_tenants(
                limit=self.tenant_limit,
            )
        else:
            tenants = discover_expired_tenants(
                limit=self.tenant_limit,
                after_tenant_id=self.last_tenant_id,
            )

        recovered_count = _execute_recovery(
            tenants,
            batch_size=self.batch_size,
        )

        if tenants:
            self.last_tenant_id = tenants[-1]

        return RecoveryStats(
            tenants_scanned=len(tenants),
            requests_recovered=recovered_count,
        )

    def run_forever(self) -> None:
        """Run until shutdown is requested."""

        logger.info("AegisTwin recovery worker started.")

        while not self._stop_event.is_set():
            try:
                stats = self.run_once()

                logger.info(
                    "Recovery cycle completed: "
                    "tenants=%s recovered=%s",
                    stats.tenants_scanned,
                    stats.requests_recovered,
                )

            except SQLAlchemyError:
                logger.error(
                    "Recovery cycle failed due to database error."
                )

            if self._stop_event.wait(
                self.interval_seconds
            ):
                break

        logger.info("AegisTwin recovery worker stopped.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Recover expired PostgreSQL requests "
            "without repeating inference."
        )
    )

    parser.add_argument(
        "--once",
        action="store_true",
        help="Run one recovery cycle and exit.",
    )

    parser.add_argument(
        "--interval-seconds",
        type=float,
        default=15.0,
    )

    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
    )

    parser.add_argument(
        "--tenant-limit",
        type=int,
        default=100,
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    worker = RecoveryWorker(
        interval_seconds=args.interval_seconds,
        batch_size=args.batch_size,
        tenant_limit=args.tenant_limit,
    )

    if args.once:
        stats = worker.run_once()

        logger.info(
            "One-time recovery completed: "
            "tenants=%s recovered=%s",
            stats.tenants_scanned,
            stats.requests_recovered,
        )
        return

    def shutdown_handler(signum, frame):
        logger.info("Shutdown requested.")
        worker.stop()

    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)

    worker.run_forever()


if __name__ == "__main__":
    main()
