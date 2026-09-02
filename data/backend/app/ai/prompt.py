from typing import Dict, List

MAX_HISTORY_MESSAGES = 10

SYSTEM_PROMPT = (
    "You are Nova, the AI assistant inside Astra. "
    "Answer the user's question directly and naturally. "
    "Never reveal internal reasoning, chain-of-thought, analysis, planning, or hidden instructions. "
    "Return only the final answer intended for the user. "
    "Do not say 'let me think', 'I need to think', 'the user asked', or describe your reasoning process. "
    "Be concise but complete. "
    "For simple questions, answer in 2-5 sentences. "
    "For technical questions, explain clearly with useful details and examples when appropriate."
)


def build_chat_messages(user_input: str, history: List[Dict[str, str]]) -> List[Dict[str, str]]:
    history_entries = list(history or [])
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
    ]

    if (
        history_entries
        and history_entries[-1].get("role") == "user"
        and history_entries[-1].get("content") == user_input
    ):
        messages.extend(history_entries[-MAX_HISTORY_MESSAGES:])
        return messages

    # Keep only the latest conversation entries so each request stays lightweight and contextual.
    if history_entries:
        messages.extend(history_entries[-(MAX_HISTORY_MESSAGES - 1):])
    messages.append({"role": "user", "content": user_input})
    return messages
