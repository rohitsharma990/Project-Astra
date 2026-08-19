import json
import logging
import time
from typing import Any, Dict, List, Optional

import requests

from .config import config
from .prompt import SYSTEM_PROMPT

logger = logging.getLogger(__name__)


class OllamaClient:
    def __init__(self) -> None:
        self.api_url = config.api_url
        self.model = config.model
        self.timeout = config.timeout

    def ask(self, user_input: str, history: Optional[List[Dict[str, str]]] = None) -> str:
        # Keep the latest 10 conversation turns and cap sizes to avoid huge prompts.
        MAX_HISTORY_MESSAGES = 10
        MAX_TOTAL_CHARS = 4000
        MAX_MESSAGE_CHARS = 1000

        history_list = list(history or [])
        if (
            history_list
            and history_list[-1].get("role") == "user"
            and history_list[-1].get("content") == user_input
        ):
            recent_history = history_list[-MAX_HISTORY_MESSAGES:]
        else:
            recent_history = history_list[-(MAX_HISTORY_MESSAGES - 1):]
            recent_history.append({"role": "user", "content": user_input})

        # Truncate individual messages to a reasonable size (keep the tail of messages)
        trimmed_history: List[Dict[str, str]] = []
        for m in recent_history:
            content = m.get("content", "")
            if len(content) > MAX_MESSAGE_CHARS:
                content = content[-MAX_MESSAGE_CHARS:]
            trimmed_history.append({"role": m.get("role", "user"), "content": content})

        # Build final messages: single system prompt and all recent context, including the current user prompt once.
        messages: List[Dict[str, str]] = [
            {"role": "system", "content": SYSTEM_PROMPT},
        ]
        messages.extend(trimmed_history)

        # Enforce a total character budget by dropping oldest history messages if needed
        def total_chars(msgs: List[Dict[str, str]]) -> int:
            return sum(len(m.get("content", "")) for m in msgs)

        while total_chars(messages) > MAX_TOTAL_CHARS and len(messages) > 2:
            # preserve system (0) and user (last); remove the oldest history entry at index 1
            messages.pop(1)

        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "think": False,
            "options": {"num_predict": 256},
        }

        logger.info("AI provider: ollama")
        logger.info("AI model: %s", self.model)
        logger.info("AI URL: %s", self.api_url)
        logger.info("AI timeout: %s", self.timeout)
        logger.info("History messages sent: %s", max(0, len(messages) - 2))
        prompt_length = sum(len(m.get("content", "")) for m in messages)
        logger.info("Prompt length: %s characters", prompt_length)

        start_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        logger.info("AI request started at %s to %s (model=%s timeout=%s)", start_time, self.api_url, self.model, self.timeout)

        try:
            start = time.perf_counter()
            response = requests.post(
                self.api_url,
                json=payload,
                timeout=self.timeout,
            )
            response.raise_for_status()
            elapsed = time.perf_counter() - start
            logger.info("AI request completed in %.2f seconds", elapsed)
            completion_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
            logger.info("AI request completed at %s", completion_time)
        except requests.exceptions.ConnectTimeout as err:
            raise RuntimeError(
                "Nova cannot connect to Ollama. Make sure Ollama is running."
            ) from err
        except requests.exceptions.ConnectionError as err:
            raise RuntimeError(
                "Nova cannot connect to Ollama. Make sure Ollama is running."
            ) from err
        except requests.exceptions.Timeout as err:
            raise RuntimeError(
                "Nova AI took too long to respond."
            ) from err
        except requests.exceptions.HTTPError as err:
            status = err.response.status_code if err.response is not None else None
            response_body = None
            try:
                response_body = err.response.json()
            except Exception:
                if err.response is not None:
                    response_body = err.response.text

            # Read response body and surface details without leaking secrets
            detail = None
            if isinstance(response_body, dict):
                detail = response_body.get("error") or response_body.get("message")
            else:
                detail = str(response_body)

            raise RuntimeError(
                f"Nova AI received an error from Ollama (status {status}): {detail or 'No details provided.'}"
            ) from err
        except requests.exceptions.RequestException as err:
            raise RuntimeError(
                "Nova cannot connect to Ollama. Make sure Ollama is running."
            ) from err

        try:
            data = response.json()
        except json.JSONDecodeError as err:
            raise RuntimeError(
                "Nova received an invalid response from Ollama."
            ) from err

        # log elapsed if not already logged
        logger.info("AI response time logged.")

        return self._extract_assistant_message(data)

    def _extract_assistant_message(self, data: Dict[str, Any]) -> str:
        if not isinstance(data, dict):
            raise RuntimeError(
                "Nova AI received an unexpected response format from Ollama."
            )

        if "error" in data:
            error_message = data.get("error")
            raise RuntimeError(
                f"Nova AI received an error from Ollama: {error_message or 'Unknown error'}."
            )

        message = data.get("message")
        if not message or not isinstance(message, dict):
            raise RuntimeError(
                "Nova received an invalid response from Ollama."
            )

        content = message.get("content")
        if not content or not isinstance(content, str):
            raise RuntimeError(
                "Nova received an empty response from Ollama."
            )

        return content
