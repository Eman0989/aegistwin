
from app.agents.base import AgentMessage, AgentTurn
from app.providers.base import LLMProvider
from app.providers.ollama import OllamaProvider


class ProviderRouter:
    """Select the configured LLM provider."""

    def __init__(self):
        self.providers: dict[str, LLMProvider] = {
            "ollama": OllamaProvider()
        }

    async def generate(
        self,
        provider: str,
        messages: list[AgentMessage],
    ) -> AgentTurn:

        selected = self.providers.get(provider)

        if selected is None:
            raise ValueError(
                f"Unsupported provider: {provider}"
            )

        return await selected.generate(messages)
