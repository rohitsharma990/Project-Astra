"""CLI entry point for the Astra backend."""

from __future__ import annotations

import queue
import threading

from app import ui
from app.config import WAKE_WORD_ENABLED, WAKE_WORD_PHRASE
from app.runtime import BackendRuntime


def _start_input_thread(commands: queue.Queue[str]) -> None:
    def read_input() -> None:
        while True:
            try:
                commands.put(input("> ").strip())
            except (EOFError, KeyboardInterrupt):
                commands.put("exit astra")
                return

    threading.Thread(target=read_input, name="stdin-reader", daemon=True).start()


def run() -> None:
    runtime = BackendRuntime()
    status = runtime.startup()
    ui.banner()
    for line in status.lines():
        ui.info(line)
    ui.info("Type a command or press Enter to speak.")
    ui.info("Say 'help' for menu or 'exit astra' to close.\n")

    commands: queue.Queue[str] = queue.Queue()
    _start_input_thread(commands)
    try:
        if WAKE_WORD_ENABLED:
            from app import wake_word
            if wake_word.start():
                ui.info(f'Waiting for "{WAKE_WORD_PHRASE}"...')
            else:
                ui.warning("Wake word is unavailable. Keyboard input is still available.")

        while True:
            command = commands.get()
            if not command:
                continue
            ui.user_message(command)
            if command.lower() == "exit astra":
                ui.assistant_message("Good Bye", speak_force=status.tts == "READY")
                break
            result = runtime.process(command)
            if result.get("mode") == "agent" and result.get("response"):
                ui.assistant_message(result["response"], speak_force=status.tts == "READY")
            elif result.get("mode") == "error":
                ui.error(result["response"], tts=True)
    except KeyboardInterrupt:
        ui.success("Good Bye")
    finally:
        runtime.shutdown()


if __name__ == "__main__":
    run()
