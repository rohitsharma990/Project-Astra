from typing import Callable, List, Dict


class GroqClient:
    def ask(self, user_input: str, history: List[Dict[str, str]]) -> str:
        raise NotImplementedError("Groq support is not implemented yet.")
