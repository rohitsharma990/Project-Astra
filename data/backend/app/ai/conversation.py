import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)
DEFAULT_HISTORY_FILE = Path("data/conversation_memory.json")
MAX_HISTORY = 10


class ConversationManager:
    def __init__(self, storage_path: Optional[Path] = None, max_messages: int = MAX_HISTORY) -> None:
        self._storage_path = Path(storage_path or DEFAULT_HISTORY_FILE)
        self._max_messages = max(1, int(max_messages))
        self._history: List[Dict[str, Any]] = []
        self._load()

    def _load(self) -> None:
        try:
            with self._storage_path.open("r", encoding="utf-8") as file:
                data = json.load(file)
            if isinstance(data, list):
                self._history = [
                    item for item in data
                    if isinstance(item, dict)
                    and item.get("role") in {"user", "assistant"}
                    and isinstance(item.get("content"), str)
                ][-self._max_messages:]
        except FileNotFoundError:
            self._history = []
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            logger.warning("Conversation memory could not be loaded; starting empty")
            self._history = []

    def _save(self) -> None:
        try:
            self._storage_path.parent.mkdir(parents=True, exist_ok=True)
            temporary_path = self._storage_path.with_suffix(".tmp")
            with temporary_path.open("w", encoding="utf-8") as file:
                json.dump(self._history, file, indent=2)
            temporary_path.replace(self._storage_path)
        except OSError:
            logger.warning("Conversation memory could not be saved")

    def _trim_history(self) -> None:
        if len(self._history) > self._max_messages:
            self._history = self._history[-self._max_messages:]

    def add_user_message(self, message: str) -> None:
        if message is None:
            return
        self._history.append({"role": "user", "content": str(message)})
        self._trim_history()
        self._save()

    def add_assistant_message(self, message: str) -> None:
        if message is None:
            return
        self._history.append({"role": "assistant", "content": str(message)})
        self._trim_history()
        self._save()

    def get_history(self) -> List[Dict[str, Any]]:
        return list(self._history[-self._max_messages:])

    @property
    def length(self) -> int:
        return len(self._history)

    @property
    def size(self) -> int:
        return len(self._history)

    def __len__(self) -> int:
        return self.length

    def clear(self) -> None:
        self._history.clear()
        self._save()
