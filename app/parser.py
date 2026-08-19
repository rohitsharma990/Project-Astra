import re
from typing import Optional, Sequence

from .browser import (
    open_chrome, open_spotify, open_website,
    open_youtube, open_youtube_search
)
from .commands import (
    open_app, open_calculator, open_notepad, open_vs_code,
    show_date, show_day, show_time,
)
from .file_manager import create_file, create_folder
from .logger import log_command
from .memory import create_memory, delete_memory, list_memories, read_memory
from .notes import create_note, delete_note, list_notes, read_note
from .screenshot import take_screenshot as take_screenshot_action
from .system import get_battery_info, get_cpu_info, get_disk_info, get_ram_info, get_system_info
from .todo import complete_todo, create_todo, delete_todo, list_todos, read_todo
from .weather import get_weather
from .file_search import find_files
from .music import music_control
from .Volume_Control import mute, set_volume, unmute, volume_down, volume_up
from .System_Commands import shutdown, restart, lock_screen
from .ai import ask_ai, clear_ai_history
from . import ui


FILLER_WORDS = {
    "a", "an", "and", "application", "app", "can", "could", "for",
    "i", "kindly", "me", "my", "now", "please", "the", "to", "would", "you", "your"
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

TARGETS = {
    "chrome", "youtube", "spotify", "notepad",
    "calculator", "vscode", "google", "github", "gmail",
    "chatgpt", "instagram", "linkedin", "facebook",
    "reddit", "spotify"
}

GREETINGS = {"hi", "hello", "hey", "yo", "greetings"}
GREETING_PHRASES = {("good", "morning"), ("good", "afternoon"), ("good", "evening")}


def display_system_info(info: dict) -> None:
    ui.assistant_message("System information")
    summary = []

    for key, value in info.items():
        print(f"{key} : {value}\n")
        summary.append(f"{key} {value}")

    if summary:
        ui.assistant_message(", ".join(summary))


def _normalize_text(command: str) -> str:
    if not command:
        return ""

    text = command.lower().strip().replace("’", "'")
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()

    replacements = {
        "you tube": "youtube",
        "note pad": "notepad",
        "google chrome": "chrome",
        "visual studio code": "vscode",
        "vs code": "vscode",
        "what time is it": "time",
        "what's the time": "time",
        "what is today s date": "date",
        "what is the date today": "date",
        "what day is today": "day",
        "what day is it today": "day",
    }

    for old, new in replacements.items():
        text = re.sub(rf"\b{re.escape(old)}\b", new, text)

    words = [ALIASES.get(w, w) for w in text.split() if w not in FILLER_WORDS]

    while words and words[0] in LEADING_ACTION_WORDS:
        words.pop(0)

    return " ".join(words)


def _starts_with(words: Sequence[str], *expected: str) -> bool:
    return tuple(words[:len(expected)]) == expected


def _target(words: Sequence[str]) -> Optional[str]:
    for word in words:
        word = ALIASES.get(word, word)
        if word in TARGETS:
            return word
    return None


def _open_target(target: str) -> bool:
    actions = {
        "chrome": open_chrome,
        "youtube": open_youtube,
        "spotify": open_spotify,
        "notepad": open_notepad,
        "calculator": open_calculator,
        "vscode": open_vs_code,
    }

    if target in actions:
        actions[target]()
    elif target in TARGETS:
        open_website(target)
    else:
        open_app(target)

    return True


def _handle_notes(words):
    if _starts_with(words, "note") or (
        len(words) > 1 and words[0] in {"create", "make", "add", "new"} and words[1] == "note"
    ):
        create_note(" ".join(words[2:] if words[0] != "note" else words[1:]) or None)
        return True

    commands = {
        ("show", "notes"): list_notes,
        ("read", "note"): read_note,
        ("delete", "note"): delete_note,
    }

    for prefix, action in commands.items():
        if _starts_with(words, *prefix):
            action(" ".join(words[len(prefix):]) or None)
            return True

    return False


def _handle_memory(words):
    commands = {
        "remember": create_memory,
        ("show", "memories"): list_memories,
        ("read", "memory"): read_memory,
        ("delete", "memory"): delete_memory,
    }

    if words and words[0] == "remember":
        create_memory(" ".join(words[1:]) or None)
        return True

    for prefix, action in commands.items():
        if isinstance(prefix, tuple) and _starts_with(words, *prefix):
            action(" ".join(words[len(prefix):]) or None)
            return True

    if (
        _starts_with(words, "clear", "memory")
        or _starts_with(words, "clear", "history")
        or _starts_with(words, "forget", "conversation")
        or _starts_with(words, "forget", "memory")
    ):
        clear_ai_history()
        ui.assistant_message("Conversation memory cleared.")
        return True

    return False


def _handle_todo(words):
    commands = {
        ("show", "todos"): list_todos,
        ("read", "todo"): read_todo,
        ("delete", "todo"): delete_todo,
    }

    if _starts_with(words, "todo"):
        create_todo(" ".join(words[1:]) or None)
        return True

    if _starts_with(words, "done"):
        complete_todo(" ".join(words[1:]) or None)
        return True

    for prefix, action in commands.items():
        if _starts_with(words, *prefix):
            action(" ".join(words[len(prefix):]) or None)
            return True

    return False


def _handle_file_search(words):
    if words and words[0] == "find" and len(words) > 1:
        find_files(" ".join(words[1:]))
        return True

    if len(words) > 2 and words[0] == "search" and words[1] in {"file", "files"}:
        find_files(" ".join(words[2:]))
        return True

    return False


def _handle_music(words):
    if not words:
        return False

    if words[0] == "play":
        query = " ".join(words[1:]).strip()

        if not query or query in {"music", "song", "songs", "playlist", "album", "track"}:
            music_control("play")
        elif any(x in words[1:] for x in {"music", "song", "songs", "playlist", "album", "track"}):
            open_youtube_search(query)
        else:
            return False

        return True

    if words[0] == "music" and len(words) > 1:
        open_youtube_search(" ".join(words[1:]))
        return True

    if words[0] in {"pause", "stop"}:
        music_control(words[0])
        return True

    if words[0] in {"next", "previous"} and any(
        x in words for x in {"song", "songs", "track", "music"}
    ):
        music_control(words[0])
        return True

    return False


def _handle_volume(words):
    if not words:
        return False

    try:
        if words[0] in {"mute", "unmute"}:
            action = mute if words[0] == "mute" else unmute
            action()
            ui.assistant_message(f"Volume {'muted' if words[0] == 'mute' else 'unmuted'}.")
            return True

        direction_actions = {
            "up": volume_up,
            "increase": volume_up,
            "louder": volume_up,
            "down": volume_down,
            "decrease": volume_down,
            "quieter": volume_down,
        }
        if words[0] == "volume" and len(words) > 1 and words[1] in direction_actions:
            level = direction_actions[words[1]]()
            ui.assistant_message(f"Volume set to {level}%.")
            return True

        if "volume" not in words:
            return False

        number = next((word for word in words if word.isdigit()), None)
        if number is None:
            if words[0] in {"set", "volume"}:
                ui.error("Please specify a volume between 0 and 100.")
                return True
            return False

        level = int(number)
        if not 0 <= level <= 100:
            ui.error("Volume must be between 0 and 100.")
            return True

        set_volume(level)
        ui.assistant_message(f"Volume set to {level}%.")
        return True
    except Exception as err:
        ui.error(str(err))
        return True


def _handle_system(words):
    actions = {
        "shutdown": shutdown,
        "restart": restart,
        "lock": lock_screen,
    }

    if words and words[0] in actions:
        actions[words[0]]()
        return True

    return False


def _handle_speak(words):
    if not words or words[0] != "speak":
        return False

    text = " ".join(words[1:]).strip()
    ui.assistant_message(
        text or "I am ready to speak. Tell me what you want me to say.",
        speak_force=True,
    )
    return True


def _handle_greeting(words):
    if not words:
        return False

    if words[0] in GREETINGS:
        ui.assistant_message("Hello! How can I help you today?")
        return True

    if tuple(words[:2]) in GREETING_PHRASES:
        ui.assistant_message("Good day! What can I do for you?")
        return True

    return False


def parse_command(command: str) -> None:
    if not command:
        return

    explicit_open = bool(re.match(r"^\s*(?:open|launch|start|run)\b", command, re.IGNORECASE))
    normalized = _normalize_text(command)
    words = normalized.split()

    if not words:
        return

    log_command(normalized)

    handlers = (
        _handle_notes,
        _handle_memory,
        _handle_todo,
        _handle_file_search,
        _handle_volume,
        _handle_music,
        _handle_system,
        _handle_speak,
        _handle_greeting,
    )

    for handler in handlers:
        if handler(words):
            return

    target = _target(words)
    if target:
        _open_target(target)
        return

    if explicit_open and words:
        open_app(" ".join(words))
        return

    if words[0] == "search":
        if len(words) > 1:
            from .google_search import google_search
            google_search(" ".join(words[1:]))
        else:
            ui.error("Please tell me what to search.")
        return

    simple_commands = {
        "time": show_time,
        "date": show_date,
        "day": show_day,
        "screenshot": take_screenshot_action,
        "ss": take_screenshot_action,
        "battery": lambda: display_system_info(get_battery_info()),
        "cpu": lambda: display_system_info(get_cpu_info()),
        "ram": lambda: display_system_info(get_ram_info()),
        "disk": lambda: display_system_info(get_disk_info()),
    }

    if words[0] in simple_commands:
        simple_commands[words[0]]()
        return

    if words[0] == "system" and len(words) > 1 and words[1] == "info":
        display_system_info(get_system_info())
        return

    if words[0] == "weather":
        city = " ".join(words[1:])
        if city:
            get_weather(city)
        else:
            ui.error("Please tell me the city for weather information.")
        return

    if words[0] == "folder":
        create_folder(" ".join(words[1:]) or None)
        return

    if words[0] == "file":
        create_file(" ".join(words[1:]) or None)
        return

    ai_response = ask_ai(command)
    ui.speak_assistant_reply(str(ai_response))