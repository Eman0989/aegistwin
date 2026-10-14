
from app.agents.base import AgentMessage, AgentTurn
from app.providers.base import LLMProvider
from app.providers.ollama import OllamaProvider
from app.providers.openai_compatible import OpenAICompatibleProvider


class ProviderRouter:
    """Route model requests to configured LLM providers."""

    def __init__(
        self,
        providers: dict[str, LLMProvider] | None = None,
    ):
        # Ollama works locally by default.
        self.providers = (
            providers
            if providers is not None
            else {"ollama": OllamaProvider()}
        )

    def register(
        self,
        name: str,
        provider: LLMProvider,
    ) -> None:
        """Register another configured model provider."""
        self.providers[name] = provider

    async def generate(
        self,
        provider: str,
        messages: list[AgentMessage],
    ) -> AgentTurn:
        """Generate a response using the selected provider."""

        selected = self.providers.get(provider)

        if selected is None:
            raise ValueError(
                f"Unsupported provider: {provider}"
            )

        return await selected.generate(messages)

    async def health_check(
        self,
        provider: str,
    ) -> bool:
        """Check the selected provider's availability."""

        selected = self.providers.get(provider)

        if selected is None:
            raise ValueError(
                f"Unsupported provider: {provider}"
            )

        return await selected.health_check()
