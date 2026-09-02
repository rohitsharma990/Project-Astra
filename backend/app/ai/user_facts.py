"""
User facts storage - stores explicit user statements about themselves.

SAFETY: Only stores facts explicitly stated by the user.
Never infers, invents, or assumes personal information.
Never stores passwords, API keys, tokens, or sensitive credentials.
"""

import json
import logging
import re
from pathlib import Path
from typing import Dict, Any, Optional

from ..config import DATA_DIR

logger = logging.getLogger(__name__)

USER_FACTS_FILE = DATA_DIR / "user_facts.json"

# Sensitive keywords that should NEVER be stored as facts
BLOCKED_KEYWORDS = {
    "password", "token", "key", "secret", "credential", "api",
    "ssn", "social security", "credit card", "card number",
    "pin", "password", "passphrase", "auth", "apikey",
}
SUPPORTED_FACT_KEYS = {"name", "preferred_name", "profession", "project", "preference"}


class UserFacts:
    """
    Stores explicit user facts extracted from conversation.
    
    Supported facts:
    - name: User's name
    - preferred_name: How user wants to be called
    - profession: User's job/role
    - project: What user is working on
    - preferences: Explicit preferences stated by user
    """
    
    def __init__(self):
        self._facts: Dict[str, Any] = {}
        self._load_from_disk()
    
    @staticmethod
    def _ensure_storage():
        """Create data directory and empty facts file if needed."""
        try:
            USER_FACTS_FILE.parent.mkdir(exist_ok=True)
            if not USER_FACTS_FILE.exists():
                with open(USER_FACTS_FILE, "w", encoding="utf-8") as f:
                    json.dump({}, f, indent=2)
        except Exception as e:
            logger.warning(f"Could not create facts storage: {e}")
    
    def _load_from_disk(self) -> None:
        """Load facts from persistent storage."""
        try:
            self._ensure_storage()
            with open(USER_FACTS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    self._facts = data
                else:
                    self._facts = {}
                    logger.warning("Facts file has invalid format, starting fresh")
        except FileNotFoundError:
            self._facts = {}
        except Exception as e:
            logger.warning(f"Could not load facts from disk: {e}. Starting with empty facts.")
            self._facts = {}
    
    def _save_to_disk(self) -> None:
        """Persist facts to storage."""
        try:
            self._ensure_storage()
            with open(USER_FACTS_FILE, "w", encoding="utf-8") as f:
                json.dump(self._facts, f, indent=2)
        except Exception as e:
            logger.error(f"Could not save facts to disk: {e}")
    
    @staticmethod
    def _is_sensitive(value: str) -> bool:
        """Check if value contains sensitive keywords."""
        value_lower = str(value).lower()
        return any(re.search(rf"\b{re.escape(keyword)}\b", value_lower) for keyword in BLOCKED_KEYWORDS)
    
    def set_fact(self, key: str, value: str) -> bool:
        """
        Store a user fact.
        
        Args:
            key: Fact name (e.g., 'name', 'profession')
            value: Fact value (e.g., 'Rohit', 'Software Engineer')
        
        Returns:
            True if stored, False if blocked (sensitive)
        """
        if not key or not value:
            return False

        key_clean = str(key).lower().strip().replace(" ", "_")
        if key_clean not in SUPPORTED_FACT_KEYS or self._is_sensitive(key_clean):
            return False
        
        # Safety: reject sensitive values
        if self._is_sensitive(value):
            logger.warning(f"Blocked storage of sensitive fact: {key}")
            return False
        
        value_clean = str(value).strip()
        
        self._facts[key_clean] = value_clean
        self._save_to_disk()
        logger.info(f"Stored fact: {key_clean} = {value_clean}")
        return True
    
    def get_fact(self, key: str) -> Optional[str]:
        """Retrieve a stored fact by key."""
        if not key:
            return None
        key_clean = str(key).lower().strip().replace(" ", "_")
        return self._facts.get(key_clean)
    
    def has_fact(self, key: str) -> bool:
        """Check if a fact exists."""
        if not key:
            return False
        key_clean = str(key).lower().strip().replace(" ", "_")
        return key_clean in self._facts
    
    def remove_fact(self, key: str) -> bool:
        """Remove a fact by key."""
        if not key:
            return False
        key_clean = str(key).lower().strip().replace(" ", "_")
        if key_clean in self._facts:
            del self._facts[key_clean]
            self._save_to_disk()
            logger.info(f"Removed fact: {key_clean}")
            return True
        return False
    
    def get_all_facts(self) -> Dict[str, str]:
        """Return all stored facts."""
        return dict(self._facts)
    
    def clear_all(self) -> None:
        """Clear all facts."""
        self._facts.clear()
        self._save_to_disk()
        logger.info("All user facts cleared")
    
    def get_facts_summary(self) -> str:
        """Return a human-readable summary of facts."""
        if not self._facts:
            return "No facts recorded."
        
        lines = []
        for key, value in self._facts.items():
            display_key = key.replace("_", " ").title()
            lines.append(f"- {display_key}: {value}")
        
        return "\n".join(lines)


# Global instance
_user_facts = UserFacts()


def set_user_fact(key: str, value: str) -> bool:
    """Store a user fact."""
    return _user_facts.set_fact(key, value)


def get_user_fact(key: str) -> Optional[str]:
    """Retrieve a user fact."""
    return _user_facts.get_fact(key)


def has_user_fact(key: str) -> bool:
    """Check if fact exists."""
    return _user_facts.has_fact(key)


def remove_user_fact(key: str) -> bool:
    """Remove a user fact."""
    return _user_facts.remove_fact(key)


def get_all_user_facts() -> Dict[str, str]:
    """Get all facts."""
    return _user_facts.get_all_facts()


def clear_user_facts() -> None:
    """Clear all facts."""
    _user_facts.clear_all()


def get_user_facts_summary() -> str:
    """Get human-readable facts summary."""
    return _user_facts.get_facts_summary()


def get_user_facts_object() -> UserFacts:
    """Get the UserFacts object for testing/advanced use."""
    return _user_facts
