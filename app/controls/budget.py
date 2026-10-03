"""Per-session resource and execution budgets."""

from dataclasses import asdict, dataclass
from math import isfinite
from typing import Any


@dataclass(frozen=True)
class BudgetResult:
    allowed: bool
    reason: str


@dataclass(frozen=True)
class BudgetUsage:
    tool_calls: int = 0
    external_http_calls: int = 0
    estimated_cost: float = 0.0

    agent_turns: int = 0
    input_tokens: int = 0
    output_tokens: int = 0

    model_runtime_ms: float = 0.0
    execution_duration_ms: float = 0.0


class BudgetManager:
    """Check and account for per-session resource limits."""

    EXTERNAL_HTTP_TOOL = "external_http"

    def __init__(
        self,
        *,
        max_tool_calls: int = 100,
        max_external_http_calls: int = 10,
        max_estimated_cost: float = 100.0,
        max_agent_turns: int = 20,
        max_input_tokens: int = 100_000,
        max_output_tokens: int = 50_000,
        max_execution_duration_ms: float = 300_000.0,
        max_model_runtime_ms: float = 240_000.0,
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

        self._validate_limit(
            "max_agent_turns",
            max_agent_turns,
        )

        self._validate_limit(
            "max_input_tokens",
            max_input_tokens,
        )

        self._validate_limit(
            "max_output_tokens",
            max_output_tokens,
        )

        self._validate_non_negative_number(
            max_execution_duration_ms,
            "max_execution_duration_ms",
        )

        self._validate_non_negative_number(
            max_model_runtime_ms,
            "max_model_runtime_ms",
        )

        self.max_tool_calls = (
            max_tool_calls
        )

        self.max_external_http_calls = (
            max_external_http_calls
        )

        self.max_estimated_cost = (
            max_estimated_cost
        )

        self.max_agent_turns = (
            max_agent_turns
        )

        self.max_input_tokens = (
            max_input_tokens
        )

        self.max_output_tokens = (
            max_output_tokens
        )

        self.max_execution_duration_ms = (
            max_execution_duration_ms
        )

        self.max_model_runtime_ms = (
            max_model_runtime_ms
        )

        self._usage: dict[
            str,
            BudgetUsage,
        ] = {}

    def check(
        self,
        session_id: str,
        tool_name: str,
        estimated_cost: float = 0.0,
    ) -> BudgetResult:
        """Check a proposed tool execution without consuming it."""

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
                    "for this session would be "
                    "exceeded."
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
                    "Maximum estimated cost for "
                    "this session would be exceeded."
                ),
            )

        return BudgetResult(
            True,
            (
                "Within configured session "
                "tool and cost budget."
            ),
        )

    def consume(
        self,
        session_id: str,
        tool_name: str,
        estimated_cost: float = 0.0,
    ) -> BudgetResult:
        """Consume one tool execution from the session budget."""

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
            agent_turns=(
                usage.agent_turns
            ),
            input_tokens=(
                usage.input_tokens
            ),
            output_tokens=(
                usage.output_tokens
            ),
            model_runtime_ms=(
                usage.model_runtime_ms
            ),
            execution_duration_ms=(
                usage.execution_duration_ms
            ),
        )

        return result

    def check_agent_turn(
        self,
        session_id: str,
        *,
        input_tokens: int = 0,
        output_tokens: int = 0,
        model_runtime_ms: float = 0.0,
        execution_duration_ms: float = 0.0,
    ) -> BudgetResult:
        """Check one proposed model/agent turn."""

        self._validate_limit(
            "input_tokens",
            input_tokens,
        )

        self._validate_limit(
            "output_tokens",
            output_tokens,
        )

        self._validate_non_negative_number(
            model_runtime_ms,
            "model_runtime_ms",
        )

        self._validate_non_negative_number(
            execution_duration_ms,
            "execution_duration_ms",
        )

        usage = self.snapshot(
            session_id
        )

        if (
            usage.agent_turns + 1
            > self.max_agent_turns
        ):
            return BudgetResult(
                False,
                (
                    "Maximum agent turns for this "
                    "session would be exceeded."
                ),
            )

        if (
            usage.input_tokens
            + input_tokens
            > self.max_input_tokens
        ):
            return BudgetResult(
                False,
                (
                    "Maximum input-token budget "
                    "for this session would be exceeded."
                ),
            )

        if (
            usage.output_tokens
            + output_tokens
            > self.max_output_tokens
        ):
            return BudgetResult(
                False,
                (
                    "Maximum output-token budget "
                    "for this session would be exceeded."
                ),
            )

        if (
            usage.model_runtime_ms
            + model_runtime_ms
            > self.max_model_runtime_ms
        ):
            return BudgetResult(
                False,
                (
                    "Maximum local-model runtime "
                    "for this session would be exceeded."
                ),
            )

        if (
            usage.execution_duration_ms
            + execution_duration_ms
            > self.max_execution_duration_ms
        ):
            return BudgetResult(
                False,
                (
                    "Maximum execution duration "
                    "for this session would be exceeded."
                ),
            )

        return BudgetResult(
            True,
            (
                "Within configured session "
                "agent resource budget."
            ),
        )

    def consume_agent_turn(
        self,
        session_id: str,
        *,
        input_tokens: int = 0,
        output_tokens: int = 0,
        model_runtime_ms: float = 0.0,
        execution_duration_ms: float = 0.0,
    ) -> BudgetResult:
        """Consume one agent/model turn from the resource budget."""

        result = (
            self.check_agent_turn(
                session_id,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                model_runtime_ms=(
                    model_runtime_ms
                ),
                execution_duration_ms=(
                    execution_duration_ms
                ),
            )
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
                usage.tool_calls
            ),
            external_http_calls=(
                usage.external_http_calls
            ),
            estimated_cost=(
                usage.estimated_cost
            ),
            agent_turns=(
                usage.agent_turns + 1
            ),
            input_tokens=(
                usage.input_tokens
                + input_tokens
            ),
            output_tokens=(
                usage.output_tokens
                + output_tokens
            ),
            model_runtime_ms=(
                usage.model_runtime_ms
                + model_runtime_ms
            ),
            execution_duration_ms=(
                usage.execution_duration_ms
                + execution_duration_ms
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
    ) -> dict[
        str,
        BudgetUsage,
    ]:
        return dict(
            self._usage
        )

    def limits_snapshot(
        self,
    ) -> dict[
        str,
        int | float,
    ]:
        return {
            "max_tool_calls": (
                self.max_tool_calls
            ),
            "max_external_http_calls": (
                self.max_external_http_calls
            ),
            "max_estimated_cost": (
                self.max_estimated_cost
            ),
            "max_agent_turns": (
                self.max_agent_turns
            ),
            "max_input_tokens": (
                self.max_input_tokens
            ),
            "max_output_tokens": (
                self.max_output_tokens
            ),
            "max_execution_duration_ms": (
                self.max_execution_duration_ms
            ),
            "max_model_runtime_ms": (
                self.max_model_runtime_ms
            ),
        }

    def usage_vs_limits(
        self,
        session_id: str,
    ) -> dict[
        str,
        dict[str, Any],
    ]:
        usage = self.snapshot(
            session_id
        )

        return {
            "tool_calls": {
                "used": usage.tool_calls,
                "limit": (
                    self.max_tool_calls
                ),
            },
            "external_http_calls": {
                "used": (
                    usage.external_http_calls
                ),
                "limit": (
                    self.max_external_http_calls
                ),
            },
            "estimated_cost": {
                "used": (
                    usage.estimated_cost
                ),
                "limit": (
                    self.max_estimated_cost
                ),
            },
            "agent_turns": {
                "used": (
                    usage.agent_turns
                ),
                "limit": (
                    self.max_agent_turns
                ),
            },
            "input_tokens": {
                "used": (
                    usage.input_tokens
                ),
                "limit": (
                    self.max_input_tokens
                ),
            },
            "output_tokens": {
                "used": (
                    usage.output_tokens
                ),
                "limit": (
                    self.max_output_tokens
                ),
            },
            "model_runtime_ms": {
                "used": (
                    usage.model_runtime_ms
                ),
                "limit": (
                    self.max_model_runtime_ms
                ),
            },
            "execution_duration_ms": {
                "used": (
                    usage.execution_duration_ms
                ),
                "limit": (
                    self.max_execution_duration_ms
                ),
            },
        }

    def usage_dict(
        self,
        session_id: str,
    ) -> dict[str, Any]:
        return asdict(
            self.snapshot(
                session_id
            )
        )

    def update_limits(
        self,
        *,
        max_tool_calls: int | None = None,
        max_external_http_calls: int | None = None,
        max_estimated_cost: float | None = None,
        max_agent_turns: int | None = None,
        max_input_tokens: int | None = None,
        max_output_tokens: int | None = None,
        max_execution_duration_ms: float | None = None,
        max_model_runtime_ms: float | None = None,
    ) -> None:
        """Update limits while preserving existing usage."""

        if max_tool_calls is not None:
            self._validate_limit(
                "max_tool_calls",
                max_tool_calls,
            )

            self.max_tool_calls = (
                max_tool_calls
            )

        if (
            max_external_http_calls
            is not None
        ):
            self._validate_limit(
                "max_external_http_calls",
                max_external_http_calls,
            )

            self.max_external_http_calls = (
                max_external_http_calls
            )

        if (
            max_estimated_cost
            is not None
        ):
            self._validate_cost(
                max_estimated_cost,
                "max_estimated_cost",
            )

            self.max_estimated_cost = (
                max_estimated_cost
            )

        if max_agent_turns is not None:
            self._validate_limit(
                "max_agent_turns",
                max_agent_turns,
            )

            self.max_agent_turns = (
                max_agent_turns
            )

        if max_input_tokens is not None:
            self._validate_limit(
                "max_input_tokens",
                max_input_tokens,
            )

            self.max_input_tokens = (
                max_input_tokens
            )

        if max_output_tokens is not None:
            self._validate_limit(
                "max_output_tokens",
                max_output_tokens,
            )

            self.max_output_tokens = (
                max_output_tokens
            )

        if (
            max_execution_duration_ms
            is not None
        ):
            self._validate_non_negative_number(
                max_execution_duration_ms,
                "max_execution_duration_ms",
            )

            self.max_execution_duration_ms = (
                max_execution_duration_ms
            )

        if (
            max_model_runtime_ms
            is not None
        ):
            self._validate_non_negative_number(
                max_model_runtime_ms,
                "max_model_runtime_ms",
            )

            self.max_model_runtime_ms = (
                max_model_runtime_ms
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
            not isinstance(
                value,
                int,
            )
            or isinstance(
                value,
                bool,
            )
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
        BudgetManager._validate_non_negative_number(
            value,
            name,
        )

    @staticmethod
    def _validate_non_negative_number(
        value: float,
        name: str,
    ) -> None:
        if (
            isinstance(
                value,
                bool,
            )
            or not isinstance(
                value,
                (int, float),
            )
            or not isfinite(
                float(value)
            )
            or value < 0
        ):
            raise ValueError(
                f"{name} must be a finite, "
                "non-negative number."
            )