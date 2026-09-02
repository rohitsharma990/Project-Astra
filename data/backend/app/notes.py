import json
from pathlib import Path

from . import ui

NOTES_FILE = Path("data/notes.json")


def ensure_notes_storage():
    NOTES_FILE.parent.mkdir(exist_ok=True)

    if not NOTES_FILE.exists():
        with open(NOTES_FILE, "w") as file:
            json.dump({}, file)


def load_notes():
    ensure_notes_storage()

    with open(NOTES_FILE, "r") as file:
        return json.load(file)


def save_notes(notes):
    with open(NOTES_FILE, "w") as file:
        json.dump(notes, file, indent=4)


# ---------------- Create ----------------

def create_note(title=None):

    notes = load_notes()

    if title is None:
        title = input("Title : ")

    if title in notes:
        ui.error("Note already exists.")
        return

    body = input("Write Note : ")

    notes[title] = body

    save_notes(notes)

    ui.success("Note Saved.")


# ---------------- Show ----------------

def list_notes():

    notes = load_notes()

    if not notes:
        ui.info("No Notes Found.")
        return

    ui.assistant_message(f"I found {len(notes)} notes.")
    print("\n===== NOTES =====")

    for title in notes:
        print(f"• {title}")


# ---------------- Read ----------------

def read_note(title=None):

    notes = load_notes()

    if title is None:
        title = input("Title : ")

    if title not in notes:
        ui.error("Note Not Found.")
        return

    ui.assistant_message(f"Reading note titled {title}.")
    print("\n==========")
    print(title)
    print("----------")
    print(notes[title])
    print("==========\n")


# ---------------- Delete ----------------

def delete_note(title=None):

    notes = load_notes()

    if title is None:
        title = input("Title : ")

    if title not in notes:
        ui.error("Note Not Found.")
        return

    del notes[title]

    save_notes(notes)

    ui.success("Note Deleted.")