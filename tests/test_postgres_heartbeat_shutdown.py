
"""Regression tests for lease-heartbeat cleanup during cancellation."""

import asyncio
import threading
from unittest.mock import patch
from uuid import uuid4

import pytest

from app.gateway.postgres_orchestrator import _lease_heartbeat
from app.gateway.postgres_request_lifecycle import PersistedRequest


@pytest.mark.asyncio
async def test_cancellation_waits_for_inflight_heartbeat_renewal():
    """Cancellation must not abandon a running lease renewal."""

    renewal_started = threading.Event()
    release_renewal = threading.Event()
    renewal_finished = threading.Event()

    persisted = PersistedRequest(
        request_id=uuid4(),
        tenant_id=uuid4(),
        agent_id=uuid4(),
        session_id=uuid4(),
        public_request_id="REQ-heartbeat-shutdown",
        lease_token="test-lease-token",
    )

    def slow_renewal(**kwargs):
        assert kwargs["request_id"] == persisted.request_id
        assert kwargs["lease_token"] == persisted.lease_token

        renewal_started.set()

        try:
            if not release_renewal.wait(timeout=5):
                raise TimeoutError(
                    "Heartbeat renewal was not released."
                )
            return True
        finally:
            renewal_finished.set()

    async def run_inference():
        async with _lease_heartbeat(
            persisted,
            worker_id="worker-test",
        ):
            # Represents an AI provider request still in progress.
            await asyncio.Event().wait()

    with (
        patch(
            "app.gateway.postgres_orchestrator.HEARTBEAT_SECONDS",
            0.01,
        ),
        patch(
            "app.gateway.postgres_orchestrator.renew_request_lease",
            side_effect=slow_renewal,
        ) as renew,
    ):
        inference_task = asyncio.create_task(run_inference())

        try:
            started = await asyncio.to_thread(
                renewal_started.wait,
                2,
            )
            assert started, "Heartbeat renewal never started."

            # Simulate server cancellation during DB renewal.
            inference_task.cancel()

            # Give the cancelled task a chance to enter cleanup.
            for _ in range(100):
                if inference_task.done():
                    break
                await asyncio.sleep(0)

            # The DB renewal is deliberately still blocked.
            # Cleanup must not finish before that renewal does.
            assert not inference_task.done(), (
                "Inference exited before its heartbeat "
                "renewal finished."
            )

        finally:
            release_renewal.set()

            finished = await asyncio.to_thread(
                renewal_finished.wait,
                2,
            )

            # Always attempt to clean up the inference task.
            if not inference_task.done():
                inference_task.cancel()

            try:
                await asyncio.wait_for(inference_task, timeout=2)
            except asyncio.CancelledError:
                pass

        assert finished, "Heartbeat DB operation did not finish."
        assert inference_task.cancelled()
        renew.assert_called_once()

@pytest.mark.asyncio
async def test_repeated_cancellation_during_heartbeat_renewal():
    """Repeated cancellation must not abandon an active DB renewal."""

    renewal_started = threading.Event()
    release_renewal = threading.Event()
    renewal_finished = threading.Event()

    persisted = PersistedRequest(
        request_id=uuid4(),
        tenant_id=uuid4(),
        agent_id=uuid4(),
        session_id=uuid4(),
        public_request_id="REQ-repeated-cancellation",
        lease_token="test-lease-token",
    )

    def slow_renewal(**kwargs):
        renewal_started.set()
        try:
            assert release_renewal.wait(timeout=5)
            return True
        finally:
            renewal_finished.set()

    async def inference():
        async with _lease_heartbeat(
            persisted,
            worker_id="worker-test",
        ):
            await asyncio.Event().wait()

    with (
        patch(
            "app.gateway.postgres_orchestrator.HEARTBEAT_SECONDS",
            0.01,
        ),
        patch(
            "app.gateway.postgres_orchestrator.renew_request_lease",
            side_effect=slow_renewal,
        ),
    ):
        task = asyncio.create_task(inference())

        try:
            assert await asyncio.to_thread(
                renewal_started.wait, 2
            )

            task.cancel()

            # Allow cleanup to begin without releasing
            # the database renewal.
            await asyncio.sleep(0)

            task.cancel()

            # Cancellation must not complete while
            # the synchronous renewal is still active.
            await asyncio.sleep(0)

            assert not task.done(), (
                "Repeated cancellation abandoned "
                "an in-flight database renewal."
            )

        finally:
            release_renewal.set()

            assert await asyncio.to_thread(
                renewal_finished.wait, 2
            )

            if not task.done():
                task.cancel()

            try:
                await asyncio.wait_for(task, timeout=2)
            except asyncio.CancelledError:
                pass
