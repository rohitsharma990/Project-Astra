"""Backend application lifecycle and the single typed-input response boundary."""

from __future__ import annotations

import importlib.util
import logging
from dataclasses import dataclass
from typing import Any

from . import speaker, wake_word
from .config import (
    AGENT_MODEL,
    AI_MODEL,
    LOG_LEVEL,
    OLLAMA_BASE_URL,
    SPEECH_RECOGNITION_ENABLED,
    TTS_ENABLED,
    WAKE_WORD_ENABLED,
)
from .voice import open_stream, shutdown_voice

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BackendStatus:
    ai: str
    agent: str
    memory: str
    tts: str
    voice: str

    def lines(self) -> list[str]:
        return [
            "ASTRA BACKEND",
            f"AI: {self.ai}",
            f"AGENT: {self.agent}",
            f"MEMORY: {self.memory}",
            f"TTS: {self.tts}",
            f"VOICE: {self.voice}",
        ]


def configure_logging() -> None:
    logging.getLogger("comtypes.client._code_cache").setLevel(logging.WARNING)
    logging.getLogger("app.ai").setLevel(logging.WARNING)
    logging.basicConfig(
        level=getattr(logging, LOG_LEVEL, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


class BackendRuntime:
    """Own startup checks, request routing, and graceful shutdown."""

    def __init__(self) -> None:
        from .agent.agent import AstraAgent

        self.agent = AstraAgent()
        self.status = BackendStatus("UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN")

    def startup(self) -> BackendStatus:
        configure_logging()
        try:
            provider = __import__("os").getenv("AI_PROVIDER", "ollama").lower()
            installed_models = (
                self._query_installed_models(f"{OLLAMA_BASE_URL}/api/tags")
                if provider == "ollama"
                else {}
            )
            if provider != "ollama":
                ai_status = "READY"
                agent_status = "READY"
            elif installed_models is None:
                ai_status = "OFFLINE"
                agent_status = "OFFLINE"
            else:
                # Report exact model presence; never silently substitute models.
                ai_status = (
                    f"READY ({AI_MODEL})"
                    if AI_MODEL in installed_models
                    else f"MODEL MISSING ({AI_MODEL} not installed)"
                )
                agent_status = (
                    f"READY ({AGENT_MODEL})"
                    if AGENT_MODEL in installed_models
                    else f"PLANNER UNAVAILABLE ({AGENT_MODEL} not installed)"
                )
        except Exception:
            logger.exception("AI availability check failed")
            ai_status = "OFFLINE"
            agent_status = "OFFLINE"

        try:
            from .ai.user_facts import get_all_user_facts
            get_all_user_facts()
            memory_status = "READY"
        except Exception:
            logger.exception("Memory availability check failed")
            memory_status = "OFFLINE"

        tts_status = "READY" if TTS_ENABLED and self._tts_available() else "OFFLINE"
        speaker.set_enabled(tts_status == "READY")
        voice_status = "DISABLED"
        if SPEECH_RECOGNITION_ENABLED:
            voice_status = "READY" if open_stream() else "OFFLINE"
            shutdown_voice()
        if WAKE_WORD_ENABLED and not wake_word.available():
            logger.warning("Wake word requested but unavailable")

        self.status = BackendStatus(ai_status, agent_status, memory_status, tts_status, voice_status)
        logger.info("Backend startup complete: %s", self.status)
        return self.status

    @staticmethod
    def _query_installed_models(api_url: str) -> dict[str, str] | None:
        """Return installed Ollama model names, or None when Ollama is unreachable."""
        try:
            import requests
            response = requests.get(api_url, timeout=2.0)
            response.raise_for_status()
            data = response.json()
        except Exception:
            return None

        models: dict[str, str] = {}
        if isinstance(data, dict):
            entries = data.get("models") or []
            for entry in entries:
                if isinstance(entry, dict):
                    name = str(entry.get("name", "")).strip()
                    if name:
                        models[name] = name
                        # Allow tagless references such as "llava" for "llava:latest".
                        models.setdefault(name.split(":")[0], name)
        return models

    @staticmethod
    def _tts_available() -> bool:
        return all(importlib.util.find_spec(name) is not None for name in ("pyttsx3", "pythoncom"))

    def process(self, user_input: str) -> dict[str, Any]:
        """Process one input without creating a second response/TTS path."""
        cleaned = (user_input or "").strip()
        if not cleaned:
            return {"mode": "empty", "response": ""}

        try:
            from .agent.router import handle_agent_request, route
            decision = route(cleaned)
            if decision["mode"] == "agent":
                result = handle_agent_request(cleaned, agent=self.agent)
                return result
            from .parser import parse_command
            parse_command(cleaned)
            return {"mode": "normal", "response": "handled"}
        except Exception:
            logger.exception("Input processing failed")
            return {
                "mode": "error",
                "response": "I couldn't complete that request safely.",
            }

    def approve_action(self, plan_id: str) -> dict[str, Any]:
        return self.agent.approve_plan(plan_id)

    def reject_action(self, plan_id: str) -> dict[str, Any]:
        self.agent.reject_plan(plan_id)
        return {"status": "rejected", "plan_id": plan_id}

    def get_conversation(self) -> list[dict[str, Any]]:
        from .ai.manager import _manager

        return _manager.get_conversation_history()

    def set_tts_enabled(self, enabled: bool) -> str:
        speaker.set_enabled(enabled)
        self.status = BackendStatus(
            self.status.ai,
            self.status.agent,
            self.status.memory,
            "READY" if enabled and self._tts_available() else "OFFLINE",
            self.status.voice,
        )
        return self.status.tts

    def toggle_microphone(self) -> str:
        if not SPEECH_RECOGNITION_ENABLED:
            return "DISABLED"
        from . import voice

        if voice.input_stream is not None:
            shutdown_voice()
            state = "OFF"
        else:
            state = "READY" if open_stream() else "OFFLINE"
        self.status = BackendStatus(self.status.ai, self.status.agent, self.status.memory, self.status.tts, state)
        return state

    def shutdown(self) -> None:
        logger.info("Shutting down Astra backend")
        try:
            wake_word.stop()
        finally:
            shutdown_voice()
            speaker.shutdown()
            logger.info("Astra backend stopped")


__all__ = ["BackendRuntime", "BackendStatus", "configure_logging"]
