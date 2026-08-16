import os
import subprocess
from . import ui


def shutdown():
    try:
        ui.assistant_message("Shutting down the system...")
        subprocess.Popen(["shutdown", "/s", "/t", "0"])
    except Exception as err:
        ui.error(f"Failed to shut down: {err}")


def restart():
    try:
        ui.assistant_message("Restarting the system...")
        subprocess.Popen(["shutdown", "/r", "/t", "0"])
    except Exception as err:
        ui.error(f"Failed to restart: {err}")


def lock():
    try:
        ui.assistant_message("Locking the system...")
        subprocess.Popen(["rundll32.exe", "user32.dll,LockWorkStation"])
    except Exception as err:
        ui.error(f"Failed to lock system: {err}")


def sleep():
    try:
        ui.assistant_message("Putting the system to sleep...")
        subprocess.Popen(["rundll32.exe", "powrprof.dll,SetSuspendState 0,1,0"])
    except Exception as err:
        ui.error(f"Failed to sleep: {err}")
