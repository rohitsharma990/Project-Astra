from typing import Any, Dict, List

MAX_HISTORY = 10


class ConversationManager:
    def __init__(self) -> None:
        self._history: List[Dict[str, Any]] = []

    def _trim_history(self) -> None:
        if len(self._history) > MAX_HISTORY:
            self._history = self._history[-MAX_HISTORY:]

    def add_user_message(self, message: str) -> None:
        if message is None:
            return
        self._history.append({"role": "user", "content": str(message)})
        self._trim_history()

    def add_assistant_message(self, message: str) -> None:
        if message is None:
            return
        self._history.append({"role": "assistant", "content": str(message)})
        self._trim_history()

    def get_history(self) -> List[Dict[str, Any]]:
        return list(self._history[-MAX_HISTORY:])

    def clear(self) -> None:
        self._history.clear()
