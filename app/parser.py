import re
from typing import Optional, Sequence

from .browser import (
    open_chrome,
    open_spotify,
    open_website,
    open_youtube,
    open_youtube_search,
)
from .commands import open_app, open_calculator, open_notepad, open_vs_code, show_time
from .file_manager import create_file, create_folder
from .logger import log_command
from .memory import create_memory, delete_memory, list_memories, read_memory
from .notes import create_note, delete_note, list_notes, read_note
from .screenshot import take_screenshot as take_screenshot_action
from .system import (
    get_battery_info,
    get_cpu_info,
    get_disk_info,
    get_ram_info,
    get_system_info,
)
from .todo import (
    complete_todo,
    create_todo,
    delete_todo,
    list_todos,
    read_todo,
)
from .weather import get_weather
from .file_search import find_files
from .music import music_control
from .system_control import shutdown, restart, lock, sleep
from .ai import ask_ai, clear_ai_history
from . import ui


FILLER_WORDS = {
    "a",
    "an",
    "and",
    "application",
    "app",
    "can",
    "could",
    "for",
    "i",
    "kindly",
    "me",
    "my",
    "now",
    "please",
    "the",
    "to",
    "would",
    "you",
    "your",
}

LEADING_ACTION_WORDS = {"open", "launch", "start", "run", "begin", "initiate"}
ALIASES = {
    "browser": "chrome",
    "yt": "youtube",
    "calc": "calculator",
    "ss": "screenshot",
    "time": "time",
    "weather": "weather",
}
KNOWN_APP_TARGETS = {"chrome", "youtube", "spotify", "notepad", "calculator", "vscode"}
KNOWN_WEBSITE_TARGETS = {
    "google",
    "youtube",
    "github",
    "gmail",
    "chatgpt",
    "instagram",
    "linkedin",
    "facebook",
    "reddit",
    "spotify",
    "chrome",
    "notepad",
    "calculator",
    "vscode",
}

GREETINGS = {
    "hi",
    "hello",
    "hey",
    "yo",
    "greetings",
}

GREETING_PHRASES = {
    ("good", "morning"),
    ("good", "afternoon"),
    ("good", "evening"),
}


def display_system_info(info: dict) -> None:
    """Display system information using the shared UI helpers."""
    ui.assistant_message("System information")
    summary: list[str] = []
    for key, value in info.items():
        print(f"{key} : {value}\n")
        summary.append(f"{key} {value}")
    if summary:
        ui.assistant_message(", ".join(summary))


def _normalize_text(command: str) -> str:
    """Normalize speech input into a cleaner, comparable command string."""
    if not command:
        return ""

    normalized = command.lower().strip()
    normalized = normalized.replace("’", "'")
    normalized = re.sub(r"[^a-z0-9\s]", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()

    replacements = {
        "you tube": "youtube",
        "note pad": "notepad",
        "google chrome": "chrome",
        "visual studio code": "vscode",
        "vs code": "vscode",
        "what time is it": "time",
        "what's the time": "time",
    }

    for source, target in replacements.items():
        normalized = re.sub(r"\b" + re.escape(source) + r"\b", target, normalized)

    words = [word for word in normalized.split() if word not in FILLER_WORDS]
    words = [ALIASES.get(word, word) for word in words]

    while words and words[0] in LEADING_ACTION_WORDS:
        words.pop(0)

    return " ".join(words).strip()


def _starts_with(words: Sequence[str], *expected: str) -> bool:
    return len(words) >= len(expected) and tuple(words[: len(expected)]) == expected


def _extract_target(words: Sequence[str]) -> Optional[str]:
    """Find the intended website or app from a natural-language command."""
    candidates = [word for word in words if word not in {"for", "me"}]
    if not candidates:
        return None

    for word in candidates:
        if word in KNOWN_APP_TARGETS or word in KNOWN_WEBSITE_TARGETS:
            return word

    for word in reversed(candidates):
        alias = ALIASES.get(word)
        if alias and (alias in KNOWN_APP_TARGETS or alias in KNOWN_WEBSITE_TARGETS):
            return alias

    return None


def _handle_notes(words: Sequence[str]) -> bool:
    if _starts_with(words, "note"):
        title = " ".join(words[1:]).strip() or None
        create_note(title)
        return True

    if _starts_with(words, "show", "notes"):
        list_notes()
        return True

    if _starts_with(words, "read", "note"):
        title = " ".join(words[2:]).strip() or None
        read_note(title)
        return True

    if _starts_with(words, "delete", "note"):
        title = " ".join(words[2:]).strip() or None
        delete_note(title)
        return True

    if len(words) >= 2 and words[0] in {"create", "make", "add", "new"} and words[1] == "note":
        title = " ".join(words[2:]).strip() or None
        create_note(title)
        return True

    return False


def _handle_memory(words: Sequence[str]) -> bool:
    if _starts_with(words, "remember"):
        title = " ".join(words[1:]).strip() or None
        create_memory(title)
        return True

    if _starts_with(words, "show", "memories"):
        list_memories()
        return True

    if _starts_with(words, "read", "memory"):
        title = " ".join(words[2:]).strip() or None
        read_memory(title)
        return True

    if _starts_with(words, "delete", "memory"):
        title = " ".join(words[2:]).strip() or None
        delete_memory(title)
        return True

    if _starts_with(words, "clear", "memory") or _starts_with(words, "clear", "history"):
        clear_ai_history()
        ui.assistant_message("Conversation memory cleared.")
        return True

    if _starts_with(words, "forget", "conversation") or _starts_with(words, "forget", "memory"):
        clear_ai_history()
        ui.assistant_message("Conversation memory cleared.")
        return True

    return False


def _handle_todo(words: Sequence[str]) -> bool:
    if _starts_with(words, "todo"):
        title = " ".join(words[1:]).strip() or None
        create_todo(title)
        return True

    if _starts_with(words, "show", "todos"):
        list_todos()
        return True

    if _starts_with(words, "read", "todo"):
        title = " ".join(words[2:]).strip() or None
        read_todo(title)
        return True

    if _starts_with(words, "done"):
        title = " ".join(words[1:]).strip() or None
        complete_todo(title)
        return True

    if _starts_with(words, "delete", "todo"):
        title = " ".join(words[2:]).strip() or None
        delete_todo(title)
        return True

    return False


def _handle_file_search(words: Sequence[str]) -> bool:
    if not words:
        return False

    if words[0] == "find" and len(words) > 1:
        query = " ".join(words[1:]).strip()
        find_files(query)
        return True

    if words[0] == "search" and len(words) > 2 and words[1] in {"file", "files"}:
        query = " ".join(words[2:]).strip()
        find_files(query)
        return True

    return False


def _handle_music_control(words: Sequence[str]) -> bool:
    if not words:
        return False

    if words[0] == "play":
        if len(words) == 1:
            music_control("play")
            return True

        query = " ".join(words[1:]).strip()
        if not query or query in {"music", "song", "songs", "playlist", "album", "track"}:
            music_control("play")
            return True

        if any(word in {"music", "song", "songs", "playlist", "album", "track"} for word in words[1:]):
            open_youtube_search(query)
            return True

        return False

    if words[0] == "music" and len(words) > 1:
        open_youtube_search(" ".join(words[1:]).strip())
        return True

    if words[0] in {"pause", "stop"} and (len(words) == 1 or words[1] in {"music", "song", "songs", "track"}):
        music_control(words[0])
        return True

    if words[0] in {"next", "previous"} and any(
        word in {"song", "songs", "track", "music"} for word in words[1:]
    ):
        music_control(words[0])
        return True

    return False


def _handle_system_control(words: Sequence[str]) -> bool:
    if not words:
        return False

    if words[0] == "shutdown":
        shutdown()
        return True

    if words[0] == "restart":
        restart()
        return True

    if words[0] == "lock":
        lock()
        return True

    if words[0] == "sleep":
        sleep()
        return True

    return False


def _handle_open_command(words: Sequence[str]) -> bool:
    if not words:
        return False

    target = _extract_target(words)
    if not target:
        return False

    if target == "chrome":
        open_chrome()
    elif target == "youtube":
        open_youtube()
    elif target == "spotify":
        open_spotify()
    elif target == "notepad":
        open_notepad()
    elif target in {"calculator", "calc"}:
        open_calculator()
    elif target in {"vscode", "vs code"}:
        open_vs_code()
    elif target in KNOWN_WEBSITE_TARGETS:
        open_website(target)
    else:
        open_app(target)
    return True


def _handle_speak_command(words: Sequence[str]) -> bool:
    if not words or words[0] != "speak":
        return False

    message = " ".join(words[1:]).strip()
    if message:
        ui.assistant_message(message, speak_force=True)
    else:
        ui.assistant_message(
            "I am ready to speak. Tell me what you want me to say.",
            speak_force=True,
        )
    return True


def _handle_greeting(words: Sequence[str]) -> bool:
    if not words:
        return False

    if words[0] in GREETINGS and all(word in FILLER_WORDS for word in words[1:]):
        ui.assistant_message("Hello! How can I help you today?")
        return True

    if len(words) >= 2 and tuple(words[:2]) in GREETING_PHRASES:
        ui.assistant_message("Good day! What can I do for you?")
        return True

    return False


def _handle_short_commands(words: Sequence[str]) -> bool:
    if not words:
        return False

    target = _extract_target(words)
    if not target:
        return False

    if target == "chrome":
        open_chrome()
        return True

    if target == "youtube":
        open_youtube()
        return True

    if target == "spotify":
        open_spotify()
        return True

    if target == "notepad":
        open_notepad()
        return True

    if target in {"calculator", "calc"}:
        open_calculator()
        return True

    if target in {"vscode", "vs code"}:
        open_vs_code()
        return True

    if target in KNOWN_WEBSITE_TARGETS:
        open_website(target)
        return True

    return False


def parse_command(command: str) -> None:
    """Parse a natural-language command and dispatch it to the correct handler."""
    if not command:
        return

    normalized_command = _normalize_text(command)
    words = normalized_command.split()

    if not words:
        return

    log_command(normalized_command)

    if _handle_notes(words):
        return

    if _handle_memory(words):
        return

    if _handle_todo(words):
        return

    if _handle_file_search(words):
        return

    if _handle_music_control(words):
        return

    if _handle_system_control(words):
        return

    if _handle_open_command(words):
        return

    if _handle_speak_command(words):
        return

    if _handle_greeting(words):
        return

    if words[0] == "search":
        query = " ".join(words[1:]).strip()
        if query:
            from .google_search import google_search
            google_search(query)
        else:
            ui.error("Please tell me what to search.")
        return

    if words[0] == "time":
        show_time()
        return

    if words[0] == "folder":
        folder_name = " ".join(words[1:]).strip() or None
        create_folder(folder_name)
        return

    if words[0] == "file":
        file_name = " ".join(words[1:]).strip() or None
        create_file(file_name)
        return

    if words[0] == "screenshot" or words[0] == "ss":
        take_screenshot_action()
        return

    if words[0] == "battery":
        display_system_info(get_battery_info())
        return

    if words[0] == "cpu":
        display_system_info(get_cpu_info())
        return

    if words[0] == "ram":
        display_system_info(get_ram_info())
        return

    if words[0] == "disk":
        display_system_info(get_disk_info())
        return

    if words[0] == "system" and len(words) > 1 and words[1] == "info":
        display_system_info(get_system_info())
        return

    if words[0] == "weather":
        city = " ".join(words[1:]).strip()
        if city:
            get_weather(city)
        else:
            ui.error("Please tell me the city for weather information.")
        return

    if _handle_short_commands(words):
        return

    ai_response = ask_ai(command)
    replay = str(ai_response)
    ui.speak_assistant_reply(replay)
