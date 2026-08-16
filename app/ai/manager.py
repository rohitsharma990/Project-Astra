import logging
from typing import Callable, Dict, Any

from .config import config
from .conversation import ConversationManager
from .openrouter import OpenRouterClient
from .ollama import OllamaClient
from .groq import GroqClient
from .gemini import GeminiClient

logger = logging.getLogger(__name__)


class AIManager:
    def __init__(self) -> None:
        self._conversation = ConversationManager()
        self._provider = self._create_provider()
        logger.info("AI provider: %s", config.provider)
        logger.info("AI model: %s", config.model)
        logger.info("AI URL: %s", config.api_url)
        logger.info("AI timeout: %s", config.timeout)

    def _create_provider(self) -> Callable[[str, list], str]:
        provider = config.provider.lower()
        if provider == "ollama":
            client = OllamaClient()
            return client.ask

        if provider == "openrouter":
            client = OpenRouterClient()
            return client.ask

        if provider == "groq":
            return self._unsupported_provider("Groq")

        if provider == "gemini":
            return self._unsupported_provider("Gemini")

        return self._unsupported_provider(provider)

    def _unsupported_provider(self, name: str) -> Callable[[str, list], str]:
        def provider(prompt: str, history: list[dict]) -> str:
            raise ValueError(
                f"{name} support is not implemented. Please use AI_PROVIDER=ollama or AI_PROVIDER=openrouter."
            )

        return provider

    def ask_ai(self, prompt: str) -> str:
        history = self._conversation.get_history()

        try:
            response = self._provider(prompt, history)
        except ValueError as err:
            return f"Nova AI cannot answer that right now: {err}"
        except RuntimeError as err:
            logger.exception("AI request failed")
            return (
                f"Nova AI is temporarily unavailable. {err} "
                "Please check your AI provider settings and ensure the service is running."
            )
        except Exception as err:
            logger.exception("AI request failed")
            return (
                "Nova AI is temporarily unavailable. Please try again in a moment."
            )

        self._conversation.add_user_message(prompt)
        self._conversation.add_assistant_message(response)
        return response

    def get_conversation_history(self) -> list:
        return self._conversation.get_history()

    def clear_history(self) -> None:
        self._conversation.clear()


_manager = AIManager()


def ask_ai(prompt: str) -> str:
    return _manager.ask_ai(prompt)
