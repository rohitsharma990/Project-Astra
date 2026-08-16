from typing import Any, Dict, List


class ConversationManager:
    def __init__(self) -> None:
        self._history: List[Dict[str, Any]] = []

    def add_user_message(self, message: str) -> None:
        self._history.append({"role": "user", "content": message})

    def add_assistant_message(self, message: str) -> None:
        self._history.append({"role": "assistant", "content": message})

    def get_history(self) -> List[Dict[str, Any]]:
        return list(self._history)

    def clear(self) -> None:
        self._history.clear()
