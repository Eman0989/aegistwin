"""Deterministic enforcement of historical AI attack signatures."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.config import (
    HISTORICAL_ATTACK_SIGNATURES,
)
from app.contracts import (
    RiskLevel,
    ToolCall,
)


DEFAULT_FEED_PATH = (
    Path(__file__).resolve().parents[2]
    / "policies"
    / "historical_attack_feed.json"
)


@dataclass(
    frozen=True,
)
class HistoricalAttackVerdict:
    matched: bool
    signature_id: str | None
    reason: str
    risk_level: RiskLevel

    def as_dict(
        self,
    ) -> dict[str, Any]:
        return {
            "matched": self.matched,
            "signature_id": (
                self.signature_id
            ),
            "reason": self.reason,
            "risk_level": (
                self.risk_level.value
            ),
        }


@dataclass(
    frozen=True,
)
class HistoricalAttackSignature:
    signature_id: str
    severity: RiskLevel
    description: str
    patterns: tuple[str, ...]


def _extract_strings(
    value: Any,
) -> list[str]:
    if isinstance(
        value,
        str,
    ):
        return [value]

    if isinstance(
        value,
        dict,
    ):
        extracted: list[str] = []

        for key, nested_value in value.items():
            extracted.extend(
                _extract_strings(
                    key
                )
            )

            extracted.extend(
                _extract_strings(
                    nested_value
                )
            )

        return extracted

    if isinstance(
        value,
        (list, tuple, set),
    ):
        extracted: list[str] = []

        for item in value:
            extracted.extend(
                _extract_strings(
                    item
                )
            )

        return extracted

    return []


def historical_input_for(
    call: ToolCall,
) -> str:
    sections = [
        call.original_user_intent,
        call.tool_name,
        *(
            _extract_strings(
                call.arguments
            )
        ),
    ]

    return "\n".join(
        section
        for section in sections
        if section
    )


def load_historical_attack_feed(
    path: str | Path = DEFAULT_FEED_PATH,
) -> dict[
    str,
    HistoricalAttackSignature,
]:
    feed_path = Path(
        path
    )

    if not feed_path.is_file():
        raise FileNotFoundError(
            "Historical attack feed not found: "
            f"{feed_path}"
        )

    with feed_path.open(
        "r",
        encoding="utf-8",
    ) as feed_file:
        raw = json.load(
            feed_file
        )

    if not isinstance(
        raw,
        list,
    ):
        raise ValueError(
            "Historical attack feed must "
            "contain a JSON array."
        )

    signatures: dict[
        str,
        HistoricalAttackSignature,
    ] = {}

    for item in raw:
        if not isinstance(
            item,
            dict,
        ):
            raise ValueError(
                "Historical attack feed entries "
                "must be JSON objects."
            )

        signature_id = str(
            item["signature_id"]
        )

        severity = RiskLevel(
            str(
                item.get(
                    "severity",
                    "HIGH",
                )
            )
        )

        description = str(
            item.get(
                "description",
                signature_id,
            )
        )

        raw_patterns = item.get(
            "patterns",
            [],
        )

        if (
            not isinstance(
                raw_patterns,
                list,
            )
            or not raw_patterns
        ):
            raise ValueError(
                "Historical signature "
                f"'{signature_id}' must define "
                "at least one pattern."
            )

        signatures[
            signature_id
        ] = HistoricalAttackSignature(
            signature_id=signature_id,
            severity=severity,
            description=description,
            patterns=tuple(
                str(pattern)
                for pattern in raw_patterns
            ),
        )

    return signatures


class HistoricalAttackDetector:
    """Match active policy signatures against a proposed tool call."""

    def __init__(
        self,
        *,
        feed_path: str | Path = DEFAULT_FEED_PATH,
    ) -> None:
        self.feed_path = Path(
            feed_path
        )

        self._signatures = (
            load_historical_attack_feed(
                self.feed_path
            )
        )

    @property
    def signatures(
        self,
    ) -> dict[
        str,
        HistoricalAttackSignature,
    ]:
        return dict(
            self._signatures
        )

    def analyze(
        self,
        call: ToolCall,
    ) -> HistoricalAttackVerdict:
        text = historical_input_for(
            call
        )

        for signature_id in sorted(
            HISTORICAL_ATTACK_SIGNATURES
        ):
            signature = (
                self._signatures.get(
                    signature_id
                )
            )

            if signature is None:
                continue

            for pattern in (
                signature.patterns
            ):
                if re.search(
                    pattern,
                    text,
                    flags=re.IGNORECASE,
                ):
                    return (
                        HistoricalAttackVerdict(
                            matched=True,
                            signature_id=(
                                signature
                                .signature_id
                            ),
                            reason=(
                                "Historical attack "
                                "signature matched: "
                                f"{signature.description}"
                            ),
                            risk_level=(
                                signature
                                .severity
                            ),
                        )
                    )

        return HistoricalAttackVerdict(
            matched=False,
            signature_id=None,
            reason=(
                "No active historical attack "
                "signature matched."
            ),
            risk_level=RiskLevel.LOW,
        )