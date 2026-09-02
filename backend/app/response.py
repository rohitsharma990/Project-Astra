"""Normalize provider output before it reaches the UI or text-to-speech."""

import re
from typing import Any


_THINKING_BLOCK = re.compile(r"<(?P<tag>think|thinking)>.*?</(?P=tag)>", re.IGNORECASE | re.DOTALL)
_INTERNAL_PREFIX = re.compile(
    r"^(?:final answer|answer|assistant)\s*[:\-]?\s*",
    re.IGNORECASE,
)
_REASONING_PREFIX = re.compile(
    r"^(?:let me think|let me consider|okay(?:,)? the user asked|"
    r"first(?:,)? i need to|i should mention|let me draft|one moment|"
    r"hold on|thinking)(?:[\s.,!;:\-]+)",
    re.IGNORECASE,
)
_META_PREAMBLE = re.compile(
    r"^(?:okay(?:,)?\s+the\s+user\s+asked.*?\.\s*)?"
    r"(?:let me think|let me consider|thinking)(?:[\s.,!;:\-]+)",
    re.IGNORECASE | re.DOTALL,
)


def clean_response(response: Any) -> str:
    """Return only usable, user-facing text from common provider responses."""
    if response is None:
        return ""

    if isinstance(response, dict):
        message = response.get("message")
        if isinstance(message, dict):
            response = message.get("content", "")
        else:
            response = response.get("content", response.get("response", ""))

    if response is None:
        return ""

    text = str(response).strip()
    if not text:
        return ""

    text = _THINKING_BLOCK.sub("", text).strip()
    text = re.sub(r"<\|(?:assistant|end)\|>", "", text, flags=re.IGNORECASE)
    text = _INTERNAL_PREFIX.sub("", text).strip()
    text = _META_PREAMBLE.sub("", text).strip()

    while True:
        cleaned = _REASONING_PREFIX.sub("", text, count=1).strip()
        if cleaned == text:
            break
        text = cleaned

    return text.strip()
