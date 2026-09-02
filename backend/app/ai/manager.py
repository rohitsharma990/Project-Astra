import logging
from typing import Callable, Dict, Any

from .config import config
from .conversation import ConversationManager
from .conversation_memory import ConversationMemoryContext
from .openrouter import OpenRouterClient
from .ollama import OllamaClient
from .groq import GroqClient
from .gemini import GeminiClient
from ..response import clean_response

logger = logging.getLogger(__name__)


class AIManager:
    def __init__(self) -> None:
        self._conversation = ConversationManager()
        self._memory_context = ConversationMemoryContext(self._conversation)
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
        # Prepare prompt with optional memory context injection
        enriched_prompt = prompt
        explicit_fact_response = self._memory_context.get_explicit_fact_response(prompt)
        if explicit_fact_response is not None:
            self._conversation.add_user_message(prompt)
            self._conversation.add_assistant_message(explicit_fact_response)
            logger.debug("Answered explicit personal-fact query from persistent memory")
            return explicit_fact_response
        if self._memory_context.should_inject_context(prompt):
            context = self._memory_context.get_full_context()
            if context:
                enriched_prompt = (
                    "Use the following verified context when it directly answers the user. "
                    "Never invent or infer personal facts.\n\n"
                    f"{context}\n\nUser query: {prompt}"
                )
                logger.debug("Memory context injected into prompt")
        
        history = self._conversation.get_history()

        try:
            response = self._provider(enriched_prompt, history)
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

        cleaned_response = clean_response(response)
        if explicit_fact_response:
            cleaned_response = explicit_fact_response
        if not cleaned_response:
            logger.warning("AI provider returned an empty response; conversation history was not updated.")
            return "Nova AI did not return a valid response. Please try again."

        # Store messages and extract facts
        self._conversation.add_user_message(prompt)
        self._conversation.add_assistant_message(cleaned_response)
        
        # Extract facts from user message for future reference
        try:
            self._memory_context.extract_and_store_facts(prompt)
        except Exception as e:
            logger.debug(f"Fact extraction failed: {e}")
        
        return cleaned_response

    def get_conversation_history(self) -> list:
        return self._conversation.get_history()

    def clear_history(self) -> None:
        self._conversation.clear()
    
    def get_user_facts(self) -> Dict[str, str]:
        """Get all known user facts."""
        from .user_facts import get_all_user_facts
        return get_all_user_facts()
    
    def get_user_fact(self, key: str) -> Any:
        """Get a specific user fact."""
        from .user_facts import get_user_fact
        return get_user_fact(key)
    
    def clear_user_facts(self) -> None:
        """Clear all user facts."""
        from .user_facts import clear_user_facts
        clear_user_facts()
    
    def remove_user_fact(self, key: str) -> bool:
        """Remove a specific fact."""
        from .user_facts import remove_user_fact
        return remove_user_fact(key)


_manager = AIManager()


def ask_ai(prompt: str) -> str:
    return _manager.ask_ai(prompt)


def clear_ai_history() -> None:
    _manager.clear_history()


def get_user_facts() -> Dict[str, str]:
    """Get all known user facts."""
    return _manager.get_user_facts()


def get_user_fact(key: str) -> Any:
    """Get a specific user fact."""
    return _manager.get_user_fact(key)


def clear_user_facts() -> None:
    """Clear all user facts."""
    _manager.clear_user_facts()


def remove_user_fact(key: str) -> bool:
    """Remove a specific fact."""
    return _manager.remove_user_fact(key)
