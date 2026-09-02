"""
Conversation memory context builder.

Provides controlled, minimal context from recent conversation and user facts
for injection into AI prompts. Avoids dumping unlimited history.
"""

import logging
import re
from typing import Dict, List
from .conversation import ConversationManager
from .user_facts import get_all_user_facts, set_user_fact, has_user_fact

logger = logging.getLogger(__name__)


class ConversationMemoryContext:
    """
    Manages conversation context and fact extraction.
    
    Responsibilities:
    - Format recent conversation for context injection
    - Extract simple user facts from conversation
    - Integrate with UserFacts persistence
    - Provide minimal, controlled context to prompts
    """
    
    def __init__(self, conversation_manager: ConversationManager):
        self.conversation = conversation_manager
        self._fact_patterns = {
            "preferred_name": r"(?:call me|prefer to be called|you can call me)\s+([A-Za-z][A-Za-z' -]{0,98}?)(?:[.,!?]|$)",
            "name": r"(?:my name is|i'm called)\s+([A-Za-z][A-Za-z' -]{0,98}?)(?:[.,!?]|$)",
            "profession": r"(?:i work as|my profession is|i am a|i'm a)\s+([A-Za-z][A-Za-z' -]{0,98}?)(?:[.,!?]|$)",
            "project": r"(?:project is|working on)\s+([A-Za-z][A-Za-z' -]{0,98}?)(?:[.,!?]|$)",
            "preference": r"(?:i prefer|my preference is)\s+([A-Za-z][A-Za-z' -]{0,98}?)(?:[.,!?]|$)",
        }
    
    def _extract_facts_from_message(self, message: str) -> Dict[str, str]:
        """
        Attempt to extract simple user facts from a message.
        
        Only extracts if pattern matches. Never infers.
        Returns extracted facts or empty dict if none found.
        """
        extracted = {}
        
        for fact_type, pattern in self._fact_patterns.items():
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                value = match.group(1).strip()
                if fact_type == "project":
                    called_match = re.search(r"project(?: called| named)\s+(.+)$", value, re.IGNORECASE)
                    if called_match:
                        value = called_match.group(1).strip()
                if value and len(value) < 100:  # Sanity check: not too long
                    extracted[fact_type] = value

        simple_name = re.search(r"\bi am\s+([A-Z][A-Za-z' -]{0,98}?)(?:[.,!?]|$)", message)
        if simple_name and "name" not in extracted:
            extracted["name"] = simple_name.group(1).strip()
        
        return extracted
    
    def extract_and_store_facts(self, user_message: str) -> None:
        """
        Extract facts from user message and store in UserFacts if not already known.
        
        This is safe because:
        1. Only patterns that match explicit statements are extracted
        2. Never overwrites existing facts
        3. Uses UserFacts blocking for sensitive data
        """
        try:
            extracted = self._extract_facts_from_message(user_message)
            for fact_type, value in extracted.items():
                if not has_user_fact(fact_type):
                    set_user_fact(fact_type, value)
                    logger.info(f"Auto-extracted fact: {fact_type} = {value}")
        except Exception as e:
            logger.debug(f"Fact extraction failed (non-critical): {e}")
    
    def get_recent_conversation_context(self, max_exchanges: int = 3) -> str:
        """
        Get recent conversation formatted for context injection.
        
        Args:
            max_exchanges: Maximum number of recent exchanges to include
        
        Returns:
            Formatted string suitable for prompt injection, or empty string.
        """
        history = self.conversation.get_history()
        if not history:
            return ""
        
        # Take last N exchanges (user + assistant pairs)
        recent = history[-(max_exchanges * 2):]
        if not recent:
            return ""
        
        lines = ["RECENT CONVERSATION:"]
        for msg in recent:
            role = msg.get("role", "").title()
            content = msg.get("content", "").strip()
            if content:
                lines.append(f"{role}: {content}")
        
        return "\n".join(lines) if len(lines) > 1 else ""
    
    def get_user_facts_context(self) -> str:
        """
        Get known user facts formatted for context injection.
        
        Returns:
            Formatted string of facts, or empty string if no facts.
        """
        facts = get_all_user_facts()
        if not facts:
            return ""
        
        lines = ["KNOWN USER FACTS:"]
        for key, value in facts.items():
            display_key = key.replace("_", " ").title()
            lines.append(f"  - {display_key}: {value}")
        
        return "\n".join(lines)
    
    def get_full_context(self) -> str:
        """
        Get combined conversation + facts context for prompt injection.
        
        Returns controlled, minimal context suitable for embedding in prompts.
        """
        parts = []
        
        conv_context = self.get_recent_conversation_context()
        if conv_context:
            parts.append(conv_context)
        
        facts_context = self.get_user_facts_context()
        if facts_context:
            parts.append(facts_context)
        
        if not parts:
            return ""
        
        return "\n\n".join(parts)
    
    def should_inject_context(self, message: str) -> bool:
        """
        Determine if memory context should be injected.
        
        Context is injected for questions about the user or references to
        recent conversation, but not for all queries.
        """
        message_lower = message.lower()
        
        # Inject for questions about user
        if any(phrase in message_lower for phrase in [
            "what do you know about me",
            "what is my name",
            "my name",
            "my project",
            "what project",
            "what do you remember",
            "do you remember",
            "what profession",
        ]):
            return True

        # Resolve short follow-ups only when there is conversation to resolve.
        if self.conversation.get_history() and re.search(r"\b(it|that|this|they)\b", message_lower):
            return True
        
        return False

    def get_explicit_fact_response(self, message: str) -> str | None:
        """Return a factual response for supported personal-fact questions."""
        message_lower = message.lower().strip()
        fact_queries = {
            "name": ("what is my name", "what's my name", "who am i"),
            "profession": ("what is my profession", "what do i do"),
            "project": ("what is my project", "what project am i working on"),
            "favorite color": ("what is my favorite color", "what's my favorite color"),
        }
        for key, phrases in fact_queries.items():
            if any(message_lower == phrase or message_lower.startswith(f"{phrase}?") for phrase in phrases):
                value = get_all_user_facts().get(key)
                if key == "name" and not value:
                    value = get_all_user_facts().get("preferred_name")
                if value:
                    label = "name" if key == "name" else key
                    return f"Your {label} is {value}."
                if key == "favorite color":
                    return "I don't have that information."
                return f"I don't know your {key} yet."
        return None
