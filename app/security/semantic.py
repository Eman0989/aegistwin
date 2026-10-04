"""Semantic detection for prompt injection and jailbreak attacks."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, ClassVar, Protocol

from app.contracts import (
    InstructionOrigin,
    RiskLevel,
    ToolCall,
)


JAILBREAK_PATTERNS = (
    r"\bdeveloper mode\b",
    r"\bjailbreak (the |this )?(assistant|agent|model|system)\b",
    r"\b(run|perform|attempt|use) (a )?jailbreak\b",
    r"\bbypass (all |the )?(security|safety|restrictions?|guardrails?)\b",
    r"\bdisable (all |the )?(security|safety|restrictions?|guardrails?)\b",
    r"\bwithout (any )?(security|safety) restrictions?\b",
    r"\bignore (all |the )?safety rules?\b",
)

INJECTION_PATTERNS = (
    r"\bignore (all |any )?(previous|prior|system) instructions?\b",
    r"\bdisregard (all |any )?(previous|prior|system) instructions?\b",
    r"\breveal (the )?(system prompt|hidden prompt|secrets?|credentials?)\b",
    r"\bshow (me )?(the )?(system prompt|hidden instructions?)\b",
    r"\boverride (the )?(policy|rules?|guardrails?|permissions?)\b",
    r"\bbypass (the )?(policy|security|guardrails?|restrictions?)\b",
    r"\bdo not tell (the )?user\b",
    r"\bpretend (that )?you are\b",
    r"\byou are now\b",
)


@dataclass(frozen=True)
class SemanticVerdict:
    malicious: bool
    score: float
    category: str
    reason: str
    engine: str
    risk_level: RiskLevel

    def as_dict(self) -> dict[str, Any]:
        return {
            "malicious": self.malicious,
            "score": round(
                self.score,
                4,
            ),
            "category": self.category,
            "reason": self.reason,
            "engine": self.engine,
            "risk_level": (
                self.risk_level.value
            ),
        }


class SemanticDetector(Protocol):
    def analyze(
        self,
        call: ToolCall,
    ) -> SemanticVerdict:
        """Analyze a proposed call for semantic attacks."""


def _extract_natural_language(
    value: Any,
) -> list[str]:
    """Extract text while excluding internal metadata and flags."""

    if isinstance(
        value,
        str,
    ):
        return [
            value
        ]

    if isinstance(
        value,
        dict,
    ):
        extracted: list[str] = []

        for nested_value in (
            value.values()
        ):
            extracted.extend(
                _extract_natural_language(
                    nested_value
                )
            )

        return extracted

    if isinstance(
        value,
        (
            list,
            tuple,
            set,
        ),
    ):
        extracted: list[str] = []

        for item in value:
            extracted.extend(
                _extract_natural_language(
                    item
                )
            )

        return extracted

    return []


def semantic_input_for(
    call: ToolCall,
) -> str:
    """Build model input from natural-language content only."""

    argument_text = (
        _extract_natural_language(
            call.arguments
        )
    )

    sections = [
        call
        .original_user_intent
        .strip(),
        *(
            text.strip()
            for text in argument_text
            if text.strip()
        ),
    ]

    combined = "\n\n".join(
        section
        for section in sections
        if section
    )

    return combined[:6000]


def _matching_patterns(
    text: str,
    patterns: tuple[str, ...],
) -> list[str]:
    return [
        pattern
        for pattern in patterns
        if re.search(
            pattern,
            text,
            flags=re.IGNORECASE,
        )
    ]


class DeterministicFallbackDetector:
    """Fallback when the semantic model is unavailable."""

    def analyze(
        self,
        call: ToolCall,
    ) -> SemanticVerdict:
        text = (
            semantic_input_for(
                call
            )
        )

        jailbreak_matches = (
            _matching_patterns(
                text,
                JAILBREAK_PATTERNS,
            )
        )

        if jailbreak_matches:
            score = min(
                0.99,
                (
                    0.86
                    + (
                        0.04
                        * len(
                            jailbreak_matches
                        )
                    )
                ),
            )

            return SemanticVerdict(
                malicious=True,
                score=score,
                category=(
                    "JAILBREAK_ATTEMPT"
                ),
                reason=(
                    "Jailbreak or security-bypass "
                    "language was detected in the "
                    "proposed action."
                ),
                engine=(
                    "deterministic-fallback"
                ),
                risk_level=(
                    RiskLevel.HIGH
                ),
            )

        injection_matches = (
            _matching_patterns(
                text,
                INJECTION_PATTERNS,
            )
        )

        if injection_matches:
            score = min(
                0.99,
                (
                    0.82
                    + (
                        0.04
                        * len(
                            injection_matches
                        )
                    )
                ),
            )

            return SemanticVerdict(
                malicious=True,
                score=score,
                category=(
                    "PROMPT_INJECTION"
                ),
                reason=(
                    "Instruction-override language "
                    "was detected in the proposed "
                    "action."
                ),
                engine=(
                    "deterministic-fallback"
                ),
                risk_level=(
                    RiskLevel.CRITICAL
                ),
            )

        return SemanticVerdict(
            malicious=False,
            score=0.05,
            category="BENIGN",
            reason=(
                "No semantic attack signal "
                "was detected."
            ),
            engine=(
                "deterministic-fallback"
            ),
            risk_level=(
                RiskLevel.LOW
            ),
        )


class TransformersPromptInjectionDetector:
    """Local ProtectAI DeBERTa prompt-injection classifier."""

    MODEL_NAME = (
        "protectai/"
        "deberta-v3-base-prompt-injection-v2"
    )

    _shared_pipeline: (
        ClassVar[Any | None]
    ) = None

    def __init__(
        self,
        threshold: float = 0.80,
    ) -> None:
        self.threshold = threshold

    def _load(
        self,
    ) -> Any:
        if (
            self
            .__class__
            ._shared_pipeline
            is None
        ):
            from transformers import (
                pipeline,
            )

            self.__class__._shared_pipeline = (
                pipeline(
                    "text-classification",
                    model=(
                        self.MODEL_NAME
                    ),
                    tokenizer=(
                        self.MODEL_NAME
                    ),
                    truncation=True,
                    max_length=512,
                )
            )

        return (
            self
            .__class__
            ._shared_pipeline
        )

    def analyze(
        self,
        call: ToolCall,
    ) -> SemanticVerdict:
        text = (
            semantic_input_for(
                call
            )
        )

        if not text:
            return SemanticVerdict(
                malicious=False,
                score=0.0,
                category="BENIGN",
                reason=(
                    "No natural-language content "
                    "required semantic "
                    "classification."
                ),
                engine=(
                    self.MODEL_NAME
                ),
                risk_level=(
                    RiskLevel.LOW
                ),
            )

        classifier = (
            self._load()
        )

        result = (
            classifier(
                text
            )[0]
        )

        label = str(
            result["label"]
        ).lower()

        score = float(
            result["score"]
        )

        malicious_label = any(
            marker in label
            for marker in (
                "injection",
                "malicious",
                "attack",
                "unsafe",
            )
        )

        malicious = (
            malicious_label
            and score
            >= self.threshold
        )

        return SemanticVerdict(
            malicious=malicious,
            score=score,
            category=(
                "PROMPT_INJECTION"
                if malicious
                else "BENIGN"
            ),
            reason=(
                (
                    "The AI classifier detected "
                    "prompt injection."
                )
                if malicious
                else (
                    "The AI classifier found no "
                    "prompt injection."
                )
            ),
            engine=(
                self.MODEL_NAME
            ),
            risk_level=(
                RiskLevel.CRITICAL
                if malicious
                else RiskLevel.LOW
            ),
        )


class HybridSemanticDetector:
    """Combine provenance-aware rules with AI classification."""

    def __init__(
        self,
        *,
        enable_model: bool = True,
        threshold: float = 0.80,
    ) -> None:
        self.enable_model = (
            enable_model
        )

        self.model = (
            TransformersPromptInjectionDetector(
                threshold=threshold
            )
        )

        self.fallback = (
            DeterministicFallbackDetector()
        )

    def analyze(
        self,
        call: ToolCall,
    ) -> SemanticVerdict:
        fallback_verdict = (
            self.fallback.analyze(
                call
            )
        )

        # Explicit injection and jailbreak patterns
        # remain blocked for every provenance.
        if (
            fallback_verdict
            .malicious
        ):
            return fallback_verdict

        trusted_origins = {
            InstructionOrigin.USER,
            InstructionOrigin.SYSTEM,
            InstructionOrigin.TRUSTED_INTERNAL,
        }

        # Trusted instructions are authorization
        # sources. Deterministic checks above still
        # block explicit malicious language while
        # avoiding classifier false positives on
        # normal authorized commands.
        if (
            call.instruction_origin
            in trusted_origins
        ):
            return fallback_verdict

        if not self.enable_model:
            return fallback_verdict

        try:
            return (
                self.model.analyze(
                    call
                )
            )

        except (
            ImportError,
            ModuleNotFoundError,
            OSError,
            RuntimeError,
            ValueError,
        ):
            return fallback_verdict