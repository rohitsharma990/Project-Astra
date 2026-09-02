from pathlib import Path
from datetime import datetime

LOG_FILE = Path("Logs/astra.log")


def log_command(command):

    # Create Logs folder if it doesn't exist
    LOG_FILE.parent.mkdir(exist_ok=True)

    # Current date & time
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Save command
    with open(LOG_FILE, "a", encoding="utf-8") as file:
        file.write(f"{now} - {command}\n")