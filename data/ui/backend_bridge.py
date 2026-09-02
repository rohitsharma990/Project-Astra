"""Threaded adapter between the companion UI and the existing backend runtime."""
from __future__ import annotations

import sys
import threading
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, QThreadPool, Signal, Slot, QRunnable

BACKEND_ROOT = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.runtime import BackendRuntime  # noqa: E402
from app import speaker  # noqa: E402
from app import ui as backend_ui  # noqa: E402


class _JobSignals(QObject):
    done = Signal(object)


class _Job(QRunnable):
    def __init__(self, fn, done):
        super().__init__()
        self.fn = fn
        self.signals = _JobSignals()
        self.signals.done.connect(done)

    def run(self):
        try:
            self.signals.done.emit(self.fn())
        except Exception as exc:
            self.signals.done.emit({"mode": "error", "response": str(exc)})


class BackendBridge(QObject):
    response = Signal(dict)
    status = Signal(dict)
    event = Signal(dict)

    def __init__(self):
        super().__init__()
        self.runtime = BackendRuntime()
        self.pool = QThreadPool.globalInstance()
        self._process_lock = threading.Lock()

    @Slot()
    def startup(self):
        def start():
            result = self.runtime.startup()
            return {"ai": result.ai, "agent": result.agent, "memory": result.memory, "tts": result.tts, "voice": result.voice}
        self.pool.start(_Job(start, self._startup_done))

    @Slot(dict)
    def _startup_done(self, payload):
        self.status.emit(payload)

    @Slot(str)
    def ask(self, text: str):
        self.event.emit({"state": "thinking"})

        def process():
            emitted: list[str] = []
            original_assistant = backend_ui.assistant_message
            original_speak_assistant = backend_ui.speak_assistant_reply

            def capture_assistant(message, *args, **kwargs):
                emitted.append(str(message))
                return original_assistant(message, *args, **kwargs)

            def capture_speak_assistant(message, *args, **kwargs):
                emitted.append(str(message))
                self.event.emit({"type": "state", "state": "speaking"})
                result = original_speak_assistant(message, *args, **kwargs)
                self.event.emit({"type": "state", "state": "idle"})
                return result

            # Parser commands historically report through the CLI UI. Capture
            # that existing output while preserving its TTS and console behavior.
            with self._process_lock:
                backend_ui.assistant_message = capture_assistant
                backend_ui.speak_assistant_reply = capture_speak_assistant
                try:
                    result = self.runtime.process(text)
                finally:
                    backend_ui.assistant_message = original_assistant
                    backend_ui.speak_assistant_reply = original_speak_assistant

            if result.get("mode") == "normal" and emitted:
                result = {**result, "response": emitted[-1]}
            if result.get("mode") == "normal" and not result.get("response"):
                history = self.runtime.get_conversation()
                if history and history[-1].get("role") == "assistant":
                    result = {**result, "response": history[-1].get("content", "")}
            if result.get("mode") == "agent" and result.get("response"):
                self.event.emit({"state": "speaking"})
                speaker.speak(result["response"], block=True, force=False)
            return result

        self.pool.start(_Job(process, self._response_done))

    @Slot(dict)
    def _response_done(self, result):
        if result.get("status") == "approval_required":
            self.event.emit({"state": "approval"})
        elif result.get("mode") == "error" or result.get("status") == "failed":
            self.event.emit({"state": "error"})
        elif result.get("status") == "success":
            self.event.emit({"state": "happy"})
        else:
            self.event.emit({"state": "idle"})
        self.response.emit(result)

    @Slot(str)
    def approve(self, plan_id: str):
        self.pool.start(_Job(lambda: self.runtime.approve_action(plan_id), self._action_done))

    @Slot(str)
    def reject(self, plan_id: str):
        self.pool.start(_Job(lambda: self.runtime.reject_action(plan_id), self._action_done))

    @Slot()
    def toggle_microphone(self):
        def toggle():
            self.event.emit({"state": "listening"})
            return {"voice": self.runtime.toggle_microphone()}
        self.pool.start(_Job(toggle, self._action_done))

    @Slot()
    def listen_once(self):
        """Capture one Vosk utterance, then reuse the normal runtime request path."""
        self.event.emit({"type": "state", "state": "listening"})

        def listen_and_queue():
            from app import voice

            if not voice.open_stream():
                return {"mode": "error", "response": "Microphone unavailable."}
            try:
                text = voice.listen().strip()
            finally:
                voice.shutdown_voice()
            if not text:
                return {"mode": "empty", "response": ""}
            self.event.emit({"type": "transcript", "text": text})
            self.ask(text)
            return {"mode": "voice", "response": ""}

        self.pool.start(_Job(listen_and_queue, self._action_done))

    @Slot(bool)
    def set_tts(self, enabled: bool):
        self.pool.start(_Job(lambda: {"tts": self.runtime.set_tts_enabled(enabled)}, self._action_done))

    @Slot(dict)
    def _action_done(self, result):
        self.event.emit({"state": "idle"})
        self.response.emit(result)

    def shutdown(self):
        self.pool.waitForDone(5000)
        self.runtime.shutdown()
