from app.voice import listen, open_stream, shutdown_voice
from app.parser import parse_command
from app import ui
from Menu.menu import Menuloop
import app.speaker as speaker
from app import wake_word
from app.config import WAKE_WORD_ENABLED, WAKE_WORD_PHRASE

import logging
import queue
import threading

logger = logging.getLogger(__name__)

# Logging configuration:
# - INFO level: Shows important events and errors
# - DEBUG level: Hidden by default (useful for development)
# - WARNING level: System warnings
#
# TTS/Wake-word DEBUG logs are now hidden during normal operation.
# To see all debug logs during development, change these to DEBUG:

logging.getLogger("app.speaker").setLevel(logging.INFO)
logging.getLogger("app.wake_word").setLevel(logging.INFO)
logging.getLogger("app.voice").setLevel(logging.INFO)
logging.getLogger("comtypes").setLevel(logging.WARNING)
logging.getLogger("comtypes.client._code_cache").setLevel(logging.WARNING)
# Suppress verbose AI provider logs
logging.getLogger("app.ai.ollama").setLevel(logging.WARNING)



def _start_input_thread(cmd_queue: queue.Queue):
    def _reader():
        while True:
            try:
                text = input("> ")
            except Exception:
                # EOF or other input error
                break

            if text is None:
                continue

            text = text.strip()
            cmd_queue.put(text)

    t = threading.Thread(target=_reader, name="stdin-reader", daemon=True)
    t.start()
    return t


ui.banner()
ui.info("🎤 ASTRA Assistant Started")
ui.info("Type a command or press Enter to speak.")
ui.info("Say 'help' for menu or 'exit astra' to close.\n")

command_queue: "queue.Queue[str]" = queue.Queue()
_start_input_thread(command_queue)

# Start wake-word detector if enabled and available
if WAKE_WORD_ENABLED:
    started = wake_word.start()
    if not started or not wake_word.available():
        ui.error("Wake word is unavailable. Keyboard and manual voice input are still available.")
    else:
        ui.info(f"🎙️ Waiting for \"{WAKE_WORD_PHRASE}\"...")

try:
    while True:
        # First, prefer typed input
        try:
            command = command_queue.get(timeout=0.5)
        except queue.Empty:
            command = ""

        if command:
            ui.user_message(command)

            if command.lower() == "exit astra":
                ui.assistant_message("Good Bye 👋")
                break

            if command.lower() == "help":
                Menuloop()
                continue

            parse_command(command)
            continue

        # No typed command — check wake-word
        if WAKE_WORD_ENABLED and wake_word.available():
            # block until wake word or timeout
            detected = wake_word.wait_for_wake(timeout=0.5)
            if not detected:
                continue

            # Wake detected
            ui.info("🤖 Wake word detected!")

            # ========== MICROPHONE OWNERSHIP: WAKE WORD -> VOSK ==========
            # Stop wake listener and WAIT for microphone to be fully released
            logger.info("[ASTRA] Stopping wake-word detector to acquire microphone")
            wake_word.stop()
            
            # Ensure the stream is actually closed
            if not wake_word.wait_until_stopped(timeout=2.0):
                logger.warning("[ASTRA] Wake-word detector did not stop cleanly")
            
            logger.info("[ASTRA] Wake-word detector stopped, microphone ready")

            # Wake response - TTS will speak without wake detector listening
            logger.info("[ASTRA] Speaking wake response")
            speaker.speak("Yes?", block=True, force=True)
            logger.info("[ASTRA] Wake response completed")

            ui.loading("🎤 Listening...")

            # Now try to open Vosk stream for command listening
            if not open_stream():
                ui.error("Microphone unavailable.")
                logger.error("[ASTRA] Failed to open Vosk stream")
                # restart wake listener only if we failed
                logger.info("[ASTRA] Restarting wake-word detector")
                wake_word.start()
                continue

            logger.info("[ASTRA] Vosk stream opened, listening for command")
            
            try:
                command = listen().strip()
            except Exception as err:
                ui.error(f"Voice error: {err}")
                logger.exception("[ASTRA] Voice error during command listen")
                # restart wake listener
                logger.info("[ASTRA] Restarting wake-word detector")
                wake_word.start()
                continue

            # Close Vosk stream before processing
            logger.info("[ASTRA] Vosk listening complete, closing stream")
            from app.voice import _close_stream
            _close_stream()

            if not command:
                # restart wake listener
                logger.info("[ASTRA] No command received, restarting wake-word detector")
                wake_word.start()
                continue

            ui.user_message(command)

            if command.lower() == "exit astra":
                ui.assistant_message("Good Bye 👋")
                break

            if command.lower() == "help":
                Menuloop()
                # restart wake listener
                logger.info("[ASTRA] After menu, restarting wake-word detector")
                wake_word.start()
                continue

            parse_command(command)

            # After processing, resume wake listening
            logger.info("[ASTRA] Command processed, restarting wake-word detector")
            wake_word.start()

except KeyboardInterrupt:
    ui.success("\nGood Bye 👋")

finally:
    logger.info("[ASTRA] Shutting down Astra...")
    logger.info("[ASTRA] Stopping wake-word detector")
    wake_word.stop()
    logger.info("[ASTRA] Closing Vosk")
    shutdown_voice()
    logger.info("[ASTRA] Astra shutdown complete")