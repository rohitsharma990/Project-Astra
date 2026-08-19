import os
import subprocess
from pathlib import Path
from . import ui

START_MENU_PATHS = [
    Path(os.getenv("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs",
    Path(os.getenv("PROGRAMDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs",
]

def open_notepad():
    try:
        subprocess.Popen(["notepad.exe"])
    except Exception as err:
        ui.error(f"something went wrong {err}")

def open_calculator():
    try:
        subprocess.Popen(["calc.exe"])
    except Exception as err:
        ui.error(f"something went wrong {err}")

def show_time():
    try:
        import datetime
        now = datetime.datetime.now()
        ui.assistant_message(f"The current time is {now.strftime('%I:%M %p')}.")
    except Exception as err:
        ui.error(f"something went wrong {err}")


def show_date():
    try:
        import datetime
        today = datetime.date.today()
        ui.assistant_message(f"Today's date is {today.strftime('%B %d, %Y')}.")
    except Exception as err:
        ui.error(f"something went wrong {err}")


def show_day():
    try:
        import datetime
        today = datetime.date.today()
        ui.assistant_message(f"Today is {today.strftime('%A')}.")
    except Exception as err:
        ui.error(f"something went wrong {err}")

def open_vs_code():
    try:
        subprocess.Popen(["code"])
    except Exception as err:
        ui.error(f"something went wrong {err}")


def open_app(app_name: str):
    try:
        normalized = app_name.lower().strip().replace(" ", "")

        if normalized == "vscode":
            return open_vs_code()

        if normalized == "notepad":
            return open_notepad()

        if normalized in {"calculator", "calc"}:
            return open_calculator()

        shortcut_paths = []
        for start_menu in START_MENU_PATHS:
            if start_menu.exists():
                shortcut_paths.extend(start_menu.rglob("*.lnk"))

        for shortcut in shortcut_paths:
            name = shortcut.stem.lower().replace(" ", "")
            if normalized == name or normalized in name:
                ui.assistant_message(f"Opening {shortcut.stem}...")
                subprocess.Popen(["cmd", "/c", "start", "", str(shortcut)])
                return

        ui.error(f"Could not find an installed app named '{app_name}'.")
    except Exception as err:
        ui.error(f"something went wrong {err}")