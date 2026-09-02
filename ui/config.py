"""UI-only persistent settings for the desktop companion."""
from __future__ import annotations

import json
from pathlib import Path

UI_ROOT = Path(__file__).resolve().parent
MODEL_PATH = UI_ROOT / "models" / "ai_ohto.glb"
SETTINGS_PATH = UI_ROOT / "settings.json"
DEFAULTS = {
    "x": 80,
    "y": 120,
    "width": 360,
    "height": 520,
    "scale": 1.0,
    "always_on_top": True,
    "edge_behavior": False,
}


def load_settings() -> dict:
    try:
        raw = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
        return {**DEFAULTS, **raw}
    except (OSError, ValueError, TypeError):
        return dict(DEFAULTS)


def save_settings(settings: dict) -> None:
    SETTINGS_PATH.write_text(json.dumps({**DEFAULTS, **settings}, indent=2), encoding="utf-8")
