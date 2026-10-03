"""Per-session in-memory tool usage budgets."""

from dataclasses import dataclass
from math import isfinite


@dataclass(frozen=True)
class BudgetResult:
    allowed: bool
    reason: str


@dataclass(frozen=True)
class BudgetUsage:
    tool_calls: int = 0
    external_http_calls: int = 0
    estimated_cost: float = 0.0


class BudgetManager:
    """Check and account for tool-call, external-call, and cost limits."""

    EXTERNAL_HTTP_TOOL = "external_http"

    def __init__(
        self,
        *,
        max_tool_calls: int = 100,
        max_external_http_calls: int = 10,
        max_estimated_cost: float = 100.0,
    ) -> None:
        self._validate_limit(
            "max_tool_calls",
            max_tool_calls,
        )
        self._validate_limit(
            "max_external_http_calls",
            max_external_http_calls,
        )
        self._validate_cost(
            max_estimated_cost,
            "max_estimated_cost",
        )

        self.max_tool_calls = max_tool_calls
        self.max_external_http_calls = (
            max_external_http_calls
        )
        self.max_estimated_cost = (
            max_estimated_cost
        )

        self._usage: dict[
            str,
            BudgetUsage,
        ] = {}

    def update_limits(
        self,
        *,
        max_tool_calls: int,
        max_external_http_calls: int,
        max_estimated_cost: float,
    ) -> None:
        """Update limits without deleting existing usage."""

        self._validate_limit(
            "max_tool_calls",
            max_tool_calls,
        )
        self._validate_limit(
            "max_external_http_calls",
            max_external_http_calls,
        )
        self._validate_cost(
            max_estimated_cost,
            "max_estimated_cost",
        )

        self.max_tool_calls = max_tool_calls
        self.max_external_http_calls = (
            max_external_http_calls
        )
        self.max_estimated_cost = (
            max_estimated_cost
        )

    def check(
        self,
        session_id: str,
        tool_name: str,
        estimated_cost: float = 0.0,
    ) -> BudgetResult:
        self._validate_cost(
            estimated_cost,
            "estimated_cost",
        )

        usage = self.snapshot(
            session_id
        )

        external_increment = int(
            tool_name
            == self.EXTERNAL_HTTP_TOOL
        )

        if (
            usage.tool_calls + 1
            > self.max_tool_calls
        ):
            return BudgetResult(
                False,
                (
                    "Maximum tool calls for this "
                    "session would be exceeded."
                ),
            )

        if (
            usage.external_http_calls
            + external_increment
            > self.max_external_http_calls
        ):
            return BudgetResult(
                False,
                (
                    "Maximum external HTTP calls "
                    "for this session would be exceeded."
                ),
            )

        if (
            usage.estimated_cost
            + estimated_cost
            > self.max_estimated_cost
        ):
            return BudgetResult(
                False,
                (
                    "Maximum estimated cost for this "
                    "session would be exceeded."
                ),
            )

        return BudgetResult(
            True,
            "Within configured session budget.",
        )

    def consume(
        self,
        session_id: str,
        tool_name: str,
        estimated_cost: float = 0.0,
    ) -> BudgetResult:
        result = self.check(
            session_id,
            tool_name,
            estimated_cost,
        )

        if not result.allowed:
            return result

        usage = self.snapshot(
            session_id
        )

        self._usage[
            session_id
        ] = BudgetUsage(
            tool_calls=(
                usage.tool_calls + 1
            ),
            external_http_calls=(
                usage.external_http_calls
                + int(
                    tool_name
                    == self.EXTERNAL_HTTP_TOOL
                )
            ),
            estimated_cost=(
                usage.estimated_cost
                + estimated_cost
            ),
        )

        return result

    def snapshot(
        self,
        session_id: str,
    ) -> BudgetUsage:
        return self._usage.get(
            session_id,
            BudgetUsage(),
        )

    def snapshots(
        self,
    ) -> dict[str, BudgetUsage]:
        return dict(
            self._usage
        )

    def reset(
        self,
        session_id: str | None = None,
    ) -> None:
        if session_id is None:
            self._usage.clear()
        else:
            self._usage.pop(
                session_id,
                None,
            )

    @staticmethod
    def _validate_limit(
        name: str,
        value: int,
    ) -> None:
        if (
            not isinstance(value, int)
            or value < 0
        ):
            raise ValueError(
                f"{name} must be a "
                "non-negative integer."
            )

    @staticmethod
    def _validate_cost(
        value: float,
        name: str,
    ) -> None:
        if (
            not isfinite(value)
            or value < 0
        ):
            raise ValueError(
                f"{name} must be a finite, "
                "non-negative number."
            )