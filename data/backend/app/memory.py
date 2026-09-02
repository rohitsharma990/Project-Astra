import json
from pathlib import Path
from datetime import datetime
from . import ui

MEMORY_FILE = Path("data/memory.json")


def ensure_memory_storage():
    MEMORY_FILE.parent.mkdir(exist_ok=True)

    if not MEMORY_FILE.exists():
        with open(MEMORY_FILE, "w", encoding="utf-8") as file:
            json.dump({}, file, indent=4)


def load_memory():
    ensure_memory_storage()

    with open(MEMORY_FILE, "r", encoding="utf-8") as file:
        data = json.load(file)

    if isinstance(data, list):
        return {item.get("title", str(index)): item for index, item in enumerate(data)}

    return data or {}


def save_memory(memory):
    with open(MEMORY_FILE, "w", encoding="utf-8") as file:
        json.dump(memory, file, indent=4)


# ---------------- Remember ----------------

def create_memory(title=None):
    memory = load_memory()

    if title is None:
        title = input("Memory Title : ").strip()

    if not title:
        ui.error("Title cannot be empty.")
        return

    for existing_title in memory:
        if existing_title.lower() == title.lower():
            ui.error("Memory already exists.")
            return

    value = input("Details : ").strip()

    memory[title] = {
        "name": title,
        "details": value,
        "created_at": datetime.now().strftime("%d-%m-%Y %H:%M:%S"),
    }

    save_memory(memory)
    ui.success("Memory Saved Successfully.")


# ---------------- Show ----------------

def list_memories():
    memory = load_memory()

    if not memory:
        ui.info("No Memories Found.")
        return

    ui.assistant_message(f"I found {len(memory)} saved memories.")
    print("\n========== MEMORIES ==========")

    for title in memory:
        print(f"• {title}")

    print("==============================\n")


# ---------------- Read ----------------

def read_memory(title=None):
    memory = load_memory()

    if title is None:
        title = input("Memory Title : ").strip()

    for existing_title, item in memory.items():
        if existing_title.lower() == title.lower():
            ui.assistant_message(f"Here is your memory titled {existing_title}.")
            print("\n========== MEMORY ==========")
            print(f"Title      : {existing_title}")
            print(f"Details    : {item.get('details', item.get('value', ''))}")
            print(f"Created At : {item.get('created_at', '')}")
            print("============================\n")
            return

    ui.error("Memory Not Found.")


# ---------------- Delete ----------------

def delete_memory(title=None):
    memory = load_memory()

    if title is None:
        title = input("Memory Title : ").strip()

    for existing_title in list(memory.keys()):
        if existing_title.lower() == title.lower():
            del memory[existing_title]
            save_memory(memory)
            ui.success("Memory Deleted Successfully.")
            return

    ui.error("Memory Not Found.")