def ask_ai(prompt: str) -> str:
	from .manager import ask_ai as _ask_ai
	return _ask_ai(prompt)


def clear_ai_history() -> None:
	from .manager import clear_ai_history as _clear_ai_history
	_clear_ai_history()

__all__ = ["ask_ai", "clear_ai_history"]
