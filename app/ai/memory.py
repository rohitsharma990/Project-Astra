from typing import List, Dict, Any


class AIMemory:
    def __init__(self) -> None:
        self._conversation_history: List[Dict[str, Any]] = []

    def add_message(self, role: str, content: str) -> None:
        self._conversation_history.append({"role": role, "content": content})

    def get_history(self) -> List[Dict[str, Any]]:
        return list(self._conversation_history)

    def clear(self) -> None:
        self._conversation_history.clear()
