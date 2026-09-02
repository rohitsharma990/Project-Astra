import ctypes
import subprocess


def _confirm(action: str) -> bool:
  answer = input(f"Do you wish to {action} your computer? (yes / no): ")
  return answer.strip().lower() == "yes"


def lock_screen():
  if _confirm("lock") and hasattr(ctypes, "windll"):
    ctypes.windll.user32.LockWorkStation()


def shutdown():
    if _confirm("shutdown"):
        subprocess.Popen(["shutdown", "/s", "/t", "1"])

def restart():
  if _confirm("restart"):
    subprocess.Popen(["shutdown", "/r", "/t", "1"])