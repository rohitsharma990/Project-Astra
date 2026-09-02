import subprocess

from .browser import open_spotify
from . import ui

SUPPORTED_ACTIONS = {"play", "pause", "next", "previous", "stop"}


def music_control(action: str) -> None:
    action = action.lower().strip()
    if not action:
        ui.error("Please provide a music control action.")
        return

    if action not in SUPPORTED_ACTIONS:
        ui.error(f"Unknown music control action: {action}")
        return

    if action == "play":
        ui.assistant_message("Playing music...")
        open_spotify()
        return

    ui.assistant_message(
        "Music control is limited right now. Please use your music app for pause, next, or previous commands."
    )
