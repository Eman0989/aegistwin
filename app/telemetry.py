"""Process-local performance telemetry for gateway evaluations."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from math import ceil
from threading import Lock
from typing import Any

from app.contracts import DecisionAction


@dataclass
class RuntimeTelemetry:
    """Collect lightweight runtime decision and latency metrics."""

    _latencies_ms: list[float] = field(
        default_factory=list
    )
    _actions: Counter[str] = field(
        default_factory=Counter
    )
    _executed: int = 0
    _prevented: int = 0
    _lock: Lock = field(
        default_factory=Lock,
        repr=False,
    )

    def record(
        self,
        *,
        action: DecisionAction,
        executed: bool,
        latency_ms: float,
    ) -> None:
        if latency_ms < 0:
            raise ValueError(
                "latency_ms cannot be negative."
            )

        with self._lock:
            self._latencies_ms.append(
                float(latency_ms)
            )
            self._actions[action.value] += 1

            if executed:
                self._executed += 1
            else:
                self._prevented += 1

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            latencies = list(
                self._latencies_ms
            )
            actions = dict(self._actions)
            executed = self._executed
            prevented = self._prevented

        total = len(latencies)

        action_counts = {
            action.value: actions.get(
                action.value,
                0,
            )
            for action in DecisionAction
        }

        if not latencies:
            return {
                "evaluation_count": 0,
                "action_counts": action_counts,
                "executed_count": 0,
                "prevented_count": 0,
                "execution_rate": 0.0,
                "prevention_rate": 0.0,
                "latency_ms": {
                    "average": 0.0,
                    "p95": 0.0,
                    "minimum": 0.0,
                    "maximum": 0.0,
                },
            }

        ordered = sorted(latencies)

        p95_index = max(
            0,
            ceil(0.95 * total) - 1,
        )

        return {
            "evaluation_count": total,
            "action_counts": action_counts,
            "executed_count": executed,
            "prevented_count": prevented,
            "execution_rate": (
                executed / total
            ),
            "prevention_rate": (
                prevented / total
            ),
            "latency_ms": {
                "average": (
                    sum(latencies) / total
                ),
                "p95": ordered[p95_index],
                "minimum": ordered[0],
                "maximum": ordered[-1],
            },
        }

    def reset(self) -> None:
        with self._lock:
            self._latencies_ms.clear()
            self._actions.clear()
            self._executed = 0
            self._prevented = 0