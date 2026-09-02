import os
from datetime import datetime
from . import ui

try:
    import pyautogui
except ModuleNotFoundError:
    pyautogui = None


def take_screenshot():
    if pyautogui is None:
        ui.error("Screenshot feature requires pyautogui. Install it with: pip install pyautogui")
        return

    # Create a directory to save screenshots if it doesn't exist
    screenshot_dir = "screenshots"
    os.makedirs(screenshot_dir, exist_ok=True)

    # Generate a filename based on the current date and time
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    screenshot_filename = f"screenshot_{timestamp}.png"
    screenshot_path = os.path.join(screenshot_dir, screenshot_filename)

    # Take the screenshot and save it to the specified path
    screenshot = pyautogui.screenshot()
    screenshot.save(screenshot_path)

    ui.success(f"Screenshot saved as {screenshot_path}")