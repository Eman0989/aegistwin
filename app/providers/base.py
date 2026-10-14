
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from app.agents.base import AgentMessage, AgentTurn


class LLMProvider(ABC):
    """Common interface for LLM providers."""

    @abstractmethod
    async def generate(
        self,
        messages: list[AgentMessage],
    ) -> AgentTurn:
        """Generate one model response."""

    @abstractmethod
    def stream(
        self,
        messages: list[AgentMessage],
    ) -> AsyncIterator[str]:
        """Stream model-generated text."""

    @abstractmethod
    async def health_check(self) -> bool:
        """Check model availability."""
