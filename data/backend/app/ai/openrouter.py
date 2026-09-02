import json
from typing import Any, Dict, Optional

import requests
from requests import RequestException

from .config import config
from .prompt import build_chat_messages


class OpenRouterClient:
    def __init__(self) -> None:
        self.api_url = config.api_url
        self.api_key = config.api_key
        self.model = config.model
        self.timeout = config.timeout

    def ask(self, user_input: str, history: Optional[list[dict]] = None) -> str:
        if not self.api_key:
            raise ValueError(
                "OpenRouter API key is not configured. Set AI_API_KEY in your environment."
            )

        payload = {
            "model": self.model,
            "messages": build_chat_messages(user_input, history or []),
            "temperature": 0.5,
            "max_tokens": 800,
        }

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        try:
            response = requests.post(
                self.api_url,
                headers=headers,
                json=payload,
                timeout=self.timeout,
            )
            response.raise_for_status()
        except requests.exceptions.Timeout as err:
            raise RuntimeError(
                "Nova cannot reach the AI service right now. The request timed out."
            ) from err
        except requests.exceptions.HTTPError as err:
            status = err.response.status_code if err.response is not None else None
            if status == 401 or status == 403:
                raise ValueError(
                    "Nova API key is invalid or missing. Please check AI_API_KEY."
                ) from err
            if status == 429:
                raise RuntimeError(
                    "Nova is being rate-limited. Please wait a moment and try again."
                ) from err
            raise RuntimeError(
                "Nova received an invalid response from the AI provider."
            ) from err
        except RequestException as err:
            raise RuntimeError(
                "Nova cannot connect to the AI provider. Check your internet connection."
            ) from err

        try:
            data = response.json()
        except json.JSONDecodeError as err:
            raise RuntimeError(
                "Nova received malformed JSON from the AI provider."
            ) from err

        if not data:
            raise RuntimeError("Received empty response from OpenRouter.")

        assistant_message = self._extract_assistant_message(data)
        return assistant_message

    def _extract_assistant_message(self, data: Dict[str, Any]) -> str:
        choices = data.get("choices")
        if not choices or not isinstance(choices, list):
            raise RuntimeError("Invalid response structure from OpenRouter.")

        first_choice = choices[0]
        message = first_choice.get("message")
        if not message or not isinstance(message, dict):
            raise RuntimeError("OpenRouter response missing assistant message.")

        content = message.get("content")
        if not content:
            raise RuntimeError("OpenRouter returned an empty assistant response.")

        return content
