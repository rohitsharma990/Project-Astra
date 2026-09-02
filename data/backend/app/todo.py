import json
from pathlib import Path

from . import ui

TODOS_FILE = Path("data/todos.json")


def ensure_todos_storage():
    TODOS_FILE.parent.mkdir(exist_ok=True)

    if not TODOS_FILE.exists():
        with open(TODOS_FILE, "w") as file:
            json.dump({}, file)


def load_todos():
    ensure_todos_storage()

    with open(TODOS_FILE, "r") as file:
        return json.load(file)


def save_todos(todos):
    with open(TODOS_FILE, "w") as file:
        json.dump(todos, file, indent=4)


# ---------------- Create ----------------

def create_todo(title=None):

    todos = load_todos()

    if title is None:
        title = input("Todo : ")

    if title in todos:
        ui.error("Todo already exists.")
        return False

    todos[title] = False

    save_todos(todos)

    ui.success("Todo Added.")
    return True


# ---------------- Show ----------------

def list_todos():

    todos = load_todos()

    if not todos:
        ui.info("No Todos Found.")
        return

    ui.assistant_message(f"I found {len(todos)} todos.")
    print("\n===== TODOS =====")

    for title, done in todos.items():

        status = "✅" if done else "❌"

        print(f"{status} {title}")


# ---------------- Read ----------------

def read_todo(title=None):

    todos = load_todos()

    if title is None:
        title = input("Todo : ")

    if title not in todos:
        ui.error("Todo Not Found.")
        return False

    status = "Completed" if todos[title] else "Pending"

    ui.assistant_message(f"Todo {title} is currently {status}.")
    print(f"\n{title}")
    print(f"Status : {status}")
    return True


# ---------------- Complete ----------------

def complete_todo(title=None):

    todos = load_todos()

    if title is None:
        title = input("Todo : ")

    if title not in todos:
        ui.error("Todo Not Found.")
        return False

    todos[title] = True

    save_todos(todos)

    ui.success("Todo Completed.")
    return True


# ---------------- Delete ----------------

def delete_todo(title=None):

    todos = load_todos()

    if title is None:
        title = input("Todo : ")

    if title not in todos:
        ui.error("Todo Not Found.")
        return False

    del todos[title]

    save_todos(todos)

    ui.success("Todo Deleted.")
    return True