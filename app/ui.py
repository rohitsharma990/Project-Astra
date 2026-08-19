from colorama import init, Fore, Style
import sys
import logging

logger = logging.getLogger(__name__)

try:
    if sys.stdout.encoding is None or sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from . import speaker
from .response import clean_response

init(autoreset=True)

HEAVY = "━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
DOUBLE = "════════════════════════════"
LIGHT = "────────────────────────────"


def _emit(message: str, color: str, prefix: str = "", tts: bool = False):
    replay = clean_response(message)
    print(color + prefix + Style.BRIGHT + replay)
    if tts:
        speak(replay, block=True, force=True)


def speak(text: str, block: bool = True, force: bool = True):
    replay = clean_response(text)
    logger.debug("UI speak() called with text=%s block=%s force=%s", replay[:100], block, force)
    if replay:
        speaker.speak(replay, block=True, force=True)
    return replay


def user_message(message: str):
    print(Fore.CYAN + Style.BRIGHT + f"🎤 You   : {message}")


def speak_assistant_reply(reply: object) -> str:
    replay = clean_response(reply)
    if not replay:
        return ""
    print(Fore.MAGENTA + Style.BRIGHT + f"🤖 Nova : {replay}")
    logger.debug("assistant reply converted to string for TTS: %s", replay[:100])
    speak(replay, block=True, force=True)
    return replay


def assistant_message(message: str, speak_force: bool = True):
    replay = str(message)
    logger.debug("assistant_message() called with speak_force=%s", speak_force)
    logger.debug("Calling speaker.speak() with AI response: %s", replay[:100])
    return speak_assistant_reply(replay)


def banner():
    """Print a compact, professional banner for the CLI."""
    print(Fore.CYAN + Style.BRIGHT + HEAVY)
    print(Fore.CYAN + Style.BRIGHT + "🤖  ASTRA — Command Line Assistant".center(len(HEAVY)))
    print(Fore.CYAN + Style.BRIGHT + DOUBLE)


def success(message: str, tts: bool = False):
    _emit(message, Fore.GREEN, "✅ ", tts=tts)


def error(message: str, tts: bool = False):
    replay = str(message)
    print(Fore.RED + "❌ " + Style.BRIGHT + replay, file=sys.stderr)
    if tts:
        speak(replay, block=True, force=True)


def warning(message: str, tts: bool = False):
    _emit(message, Fore.YELLOW, "⚠️  ", tts=tts)


def info(message: str, tts: bool = False):
    _emit(message, Fore.BLUE, "ℹ️  ", tts=tts)


def loading(message: str, tts: bool = False):
    """Non-blocking loading / progress message (keeps UI simple)."""
    _emit(message, Fore.CYAN, "… ", tts=tts)


def section(title: str):
    print(Fore.CYAN + Style.BRIGHT + LIGHT)
    print(Fore.CYAN + Style.BRIGHT + f" {title} ")
    print(Fore.CYAN + Style.BRIGHT + LIGHT)


def divider():
    print(Fore.CYAN + DOUBLE)


__all__ = [
    "banner",
    "success",
    "error",
    "warning",
    "info",
    "loading",
    "section",
    "divider",
    "user_message",
    "assistant_message",
    "speak_assistant_reply",
]
