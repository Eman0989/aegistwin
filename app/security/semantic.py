"""Semantic detection for prompt injection and jailbreak attacks."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Protocol

from app.contracts import InstructionOrigin, RiskLevel, ToolCall


UNTRUSTED_ORIGINS = {
    InstructionOrigin.WEB_UNTRUSTED,
    InstructionOrigin.DOCUMENT_UNTRUSTED,
    InstructionOrigin.EMAIL_UNTRUSTED,
    InstructionOrigin.MCP_TOOL_OUTPUT,
    InstructionOrigin.EXTERNAL_API,
}

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
    r"\bdeveloper mode\b",
    r"\bjailbreak\b",
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
            "score": round(self.score, 4),
            "category": self.category,
            "reason": self.reason,
            "engine": self.engine,
            "risk_level": self.risk_level.value,
        }


class SemanticDetector(Protocol):
    def analyze(self, call: ToolCall) -> SemanticVerdict:
        """Analyze a proposed tool call for semantic attacks."""


def _serialize(value: Any) -> str:
    try:
        return json.dumps(value, sort_keys=True, default=str)
    except TypeError:
        return str(value)


def semantic_input_for(call: ToolCall) -> str:
    arguments = _serialize(call.arguments)

    return (
        f"Original user intent:\n{call.original_user_intent[:2000]}\n\n"
        f"Instruction origin:\n{call.instruction_origin.value}\n\n"
        f"Proposed tool:\n{call.tool_name}\n\n"
        f"Proposed arguments:\n{arguments[:4000]}"
    )


class DeterministicFallbackDetector:
    """Safe fallback when the semantic model is unavailable."""

    def analyze(self, call: ToolCall) -> SemanticVerdict:
        text = semantic_input_for(call)

        matches = [
            pattern
            for pattern in INJECTION_PATTERNS
            if re.search(pattern, text, flags=re.IGNORECASE)
        ]

        untrusted = call.instruction_origin in UNTRUSTED_ORIGINS

        if matches:
            score = min(
                0.99,
                (0.82 if untrusted else 0.70)
                + (0.04 * len(matches)),
            )

            return SemanticVerdict(
                malicious=True,
                score=score,
                category=(
                    "PROMPT_INJECTION"
                    if untrusted
                    else "JAILBREAK_ATTEMPT"
                ),
                reason=(
                    "Instruction-override language was detected "
                    "in the proposed action."
                ),
                engine="deterministic-fallback",
                risk_level=(
                    RiskLevel.CRITICAL
                    if untrusted
                    else RiskLevel.HIGH
                ),
            )

        return SemanticVerdict(
            malicious=False,
            score=0.20 if untrusted else 0.05,
            category="BENIGN",
            reason="No semantic attack signal was detected.",
            engine="deterministic-fallback",
            risk_level=(
                RiskLevel.MEDIUM
                if untrusted
                else RiskLevel.LOW
            ),
        )


class TransformersPromptInjectionDetector:
    """Local AI classifier using ProtectAI's DeBERTa model."""

    MODEL_NAME = "protectai/deberta-v3-base-prompt-injection-v2"

    def __init__(self, threshold: float = 0.80) -> None:
        self.threshold = threshold
        self._pipeline: Any = None

    def _load(self) -> Any:
        if self._pipeline is None:
            from transformers import pipeline

            self._pipeline = pipeline(
                "text-classification",
                model=self.MODEL_NAME,
                tokenizer=self.MODEL_NAME,
                truncation=True,
                max_length=512,
            )

        return self._pipeline

    def analyze(self, call: ToolCall) -> SemanticVerdict:
        classifier = self._load()
        result = classifier(semantic_input_for(call))[0]

        label = str(result["label"]).lower()
        score = float(result["score"])

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
            and score >= self.threshold
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
                "The AI classifier detected prompt injection."
                if malicious
                else "The AI classifier found no prompt injection."
            ),
            engine=self.MODEL_NAME,
            risk_level=(
                RiskLevel.CRITICAL
                if malicious
                else RiskLevel.LOW
            ),
        )


class HybridSemanticDetector:
    """Prefer the AI model and fail safely to deterministic detection."""

    def __init__(
        self,
        *,
        enable_model: bool = True,
        threshold: float = 0.80,
    ) -> None:
        self.enable_model = enable_model
        self.model = TransformersPromptInjectionDetector(
            threshold=threshold
        )
        self.fallback = DeterministicFallbackDetector()

    def analyze(self, call: ToolCall) -> SemanticVerdict:
        if not self.enable_model:
            return self.fallback.analyze(call)

        try:
            return self.model.analyze(call)
        except (
            ImportError,
            ModuleNotFoundError,
            OSError,
            RuntimeError,
            ValueError,
        ):
            return self.fallback.analyze(call)