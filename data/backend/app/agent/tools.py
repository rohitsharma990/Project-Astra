from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict

from app.browser import open_website as browser_open_website
from app.browser import open_youtube_search as browser_open_youtube_search
from app.file_manager import create_file as file_create_file
from app.file_manager import create_folder as file_create_folder
from app.file_search import find_files as file_find_files
from app.notes import create_note as notes_create_note
from app.notes import list_notes as notes_list_notes
from app.todo import create_todo as todo_create_todo
from app.todo import list_todos as todo_list_todos
from app.weather import fetch_weather as weather_fetch_weather
from app.config import DATA_DIR, FILES_DIR


def _contains_unsafe_code(value: str) -> bool:
    text = value or ""
    unsafe_tokens = (
        "__import__",
        "eval(",
        "exec(",
        "os.system",
        "subprocess",
        ";",
        "&&",
        "||",
        "`",
        "$(",
        "import ",
        "from ",
        "<",
        ">",
    )
    return any(token in text for token in unsafe_tokens)


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    input_schema: Dict[str, Any]
    func: Callable[..., Any]
    safety_level: str = "safe"  # "safe" or "requires_approval"


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: Dict[str, ToolSpec] = {}

    def register(self, name: str, description: str, input_schema: Dict[str, Any], func: Callable[..., Any], safety_level: str = "safe") -> ToolSpec:
        cleaned_name = str(name or "").strip()
        if not cleaned_name:
            raise ValueError("Tool name cannot be empty.")
        if self.has_tool(cleaned_name):
            raise ValueError(f"Tool already registered: {cleaned_name}")
        if _contains_unsafe_code(cleaned_name):
            raise ValueError(f"Unsafe tool name rejected: {cleaned_name}")
        
        if safety_level not in ("safe", "requires_approval"):
            raise ValueError(f"Invalid safety_level: {safety_level}. Must be 'safe' or 'requires_approval'.")

        tool = ToolSpec(name=cleaned_name, description=description, input_schema=input_schema, func=func, safety_level=safety_level)
        self._tools[cleaned_name] = tool
        return tool

    def has_tool(self, name: str) -> bool:
        return str(name).strip() in self._tools

    def get_tool(self, name: str) -> ToolSpec:
        cleaned_name = str(name or "").strip()
        if not self.has_tool(cleaned_name):
            raise ValueError(f"Unknown tool: {cleaned_name}")
        return self._tools[cleaned_name]

    def list_tools(self) -> list[ToolSpec]:
        return list(self._tools.values())


def _echo(text: str) -> str:
    return text


def _uppercase(text: str) -> str:
    return str(text).upper()


def _lowercase(text: str) -> str:
    return str(text).lower()


def _length(text: str) -> int:
    return len(str(text))


def _safe_create_note(title: str, content: Any) -> dict[str, Any]:
    normalized_title = str(title or "").strip()
    if not normalized_title:
        raise ValueError("Note title cannot be empty.")
    if isinstance(content, (dict, list)):
        # Reference-resolved structured results are stored as readable JSON.
        normalized_content = json.dumps(content, ensure_ascii=False)
    else:
        normalized_content = str(content or "").strip()
    if not normalized_content:
        raise ValueError("Note content cannot be empty.")

    notes_path = DATA_DIR / "notes.json"
    notes_path.parent.mkdir(exist_ok=True)
    if notes_path.exists():
        with notes_path.open("r", encoding="utf-8") as fh:
            notes = json.load(fh)
    else:
        notes = {}

    notes[normalized_title] = normalized_content
    with notes_path.open("w", encoding="utf-8") as fh:
        json.dump(notes, fh, indent=4)

    return {"title": normalized_title, "content": normalized_content}


def _safe_create_todo(title: str) -> dict[str, str | bool]:
    normalized_title = str(title or "").strip()
    if not normalized_title:
        raise ValueError("Todo title cannot be empty.")

    todos_path = DATA_DIR / "todos.json"
    todos_path.parent.mkdir(exist_ok=True)
    if todos_path.exists():
        with todos_path.open("r", encoding="utf-8") as fh:
            todos = json.load(fh)
    else:
        todos = {}

    if normalized_title in todos:
        raise ValueError(f"Todo already exists: {normalized_title}")

    todos[normalized_title] = False
    with todos_path.open("w", encoding="utf-8") as fh:
        json.dump(todos, fh, indent=4)

    return {"title": normalized_title, "status": "pending"}


def _safe_find_files(query: str) -> list[str]:
    cleaned = str(query or "").strip()
    if not cleaned:
        raise ValueError("Search query cannot be empty.")

    results: list[str] = []
    for root in [FILES_DIR, Path.cwd()]:
        path = root.resolve()
        if not path.exists():
            continue
        for folder, _, filenames in os.walk(path):
            for filename in filenames:
                if cleaned.lower() in filename.lower():
                    results.append(str(Path(folder) / filename))
    return results[:25]


def _safe_get_weather(city: str) -> dict[str, Any]:
    """Fetch real weather data for plan steps.

    Raises a clear configuration error when WEATHER_API_KEY is missing so
    plans fail honestly instead of fabricating or masking the problem.
    """
    cleaned = str(city or "").strip()
    if not cleaned:
        raise ValueError("City cannot be empty.")
    return weather_fetch_weather(cleaned)


def _safe_open_website(site: Any) -> dict[str, Any]:
    if isinstance(site, dict):
        return {"site": site}

    cleaned = str(site or "").strip().lower()
    if not cleaned:
        raise ValueError("Website name cannot be empty.")

    browser_open_website(cleaned)
    return {"site": cleaned}


def _safe_open_youtube_search(query: str) -> dict[str, Any]:
    cleaned = str(query or "").strip()
    if not cleaned:
        raise ValueError("Search query cannot be empty.")

    browser_open_youtube_search(cleaned)
    return {"query": cleaned, "source": "youtube"}


def _safe_create_file(name: str, content: str) -> dict[str, str]:
    normalized_name = str(name or "").strip()
    if not normalized_name:
        raise ValueError("File name cannot be empty.")
    file_create_file(normalized_name)
    file_path = FILES_DIR / normalized_name
    if file_path.exists() and content is not None:
        file_path.write_text(str(content), encoding="utf-8")
    return {"name": normalized_name, "status": "created"}


def _safe_create_folder(name: str) -> dict[str, str]:
    normalized_name = str(name or "").strip()
    if not normalized_name:
        raise ValueError("Folder name cannot be empty.")
    file_create_folder(normalized_name)
    return {"name": normalized_name, "status": "created"}


def _safe_list_notes() -> list[str]:
    notes_path = DATA_DIR / "notes.json"
    if not notes_path.exists():
        return []
    with notes_path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    return list(data.keys())


def _safe_list_todos() -> list[str]:
    todos_path = DATA_DIR / "todos.json"
    if not todos_path.exists():
        return []
    with todos_path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    return list(data.keys())


def default_registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(
        "echo",
        "Return the provided text exactly as given.",
        {
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
            "additionalProperties": False,
        },
        _echo,
        safety_level="safe",
    )
    registry.register(
        "uppercase",
        "Convert the provided text to uppercase.",
        {
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
            "additionalProperties": False,
        },
        _uppercase,
        safety_level="safe",
    )
    registry.register(
        "lowercase",
        "Convert the provided text to lowercase.",
        {
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
            "additionalProperties": False,
        },
        _lowercase,
        safety_level="safe",
    )
    registry.register(
        "length",
        "Return the length of the provided text.",
        {
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
            "additionalProperties": False,
        },
        _length,
        safety_level="safe",
    )
    registry.register(
        "create_note",
        "Create a note with a title and content.",
        {
            "type": "object",
            "properties": {"title": {"type": "string"}, "content": {"type": "string"}},
            "required": ["title", "content"],
            "additionalProperties": False,
        },
        _safe_create_note,
        safety_level="requires_approval",
    )
    registry.register(
        "create_todo",
        "Create a todo item with a title.",
        {
            "type": "object",
            "properties": {"title": {"type": "string"}},
            "required": ["title"],
            "additionalProperties": False,
        },
        _safe_create_todo,
        safety_level="requires_approval",
    )
    registry.register(
        "find_files",
        "Search the Files directory or project tree for matching names.",
        {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
            "additionalProperties": False,
        },
        _safe_find_files,
        safety_level="safe",
    )
    registry.register(
        "get_weather",
        "Fetch the weather for a city using the existing weather API wrapper.",
        {
            "type": "object",
            "properties": {"city": {"type": "string"}},
            "required": ["city"],
            "additionalProperties": False,
        },
        _safe_get_weather,
        safety_level="safe",
    )
    registry.register(
        "open_website",
        "Open a known website in the default browser.",
        {
            "type": "object",
            "properties": {"site": {"type": "string"}},
            "required": ["site"],
            "additionalProperties": False,
        },
        _safe_open_website,
        safety_level="safe",
    )
    registry.register(
        "open_youtube_search",
        "Open a YouTube search for the provided query.",
        {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
            "additionalProperties": False,
        },
        _safe_open_youtube_search,
        safety_level="safe",
    )
    registry.register(
        "create_file",
        "Create a file in the Files directory with initial content.",
        {
            "type": "object",
            "properties": {"name": {"type": "string"}, "content": {"type": "string"}},
            "required": ["name"],
            "additionalProperties": False,
        },
        _safe_create_file,
        safety_level="requires_approval",
    )
    registry.register(
        "create_folder",
        "Create a folder in the Files directory.",
        {
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
            "additionalProperties": False,
        },
        _safe_create_folder,
        safety_level="requires_approval",
    )
    registry.register(
        "list_notes",
        "List all note titles currently stored by Astra.",
        {
            "type": "object",
            "properties": {},
            "required": [],
            "additionalProperties": False,
        },
        _safe_list_notes,
        safety_level="safe",
    )
    registry.register(
        "list_todos",
        "List all todo titles currently stored by Astra.",
        {
            "type": "object",
            "properties": {},
            "required": [],
            "additionalProperties": False,
        },
        _safe_list_todos,
        safety_level="safe",
    )
    return registry


__all__ = ["ToolRegistry", "ToolSpec", "default_registry"]
