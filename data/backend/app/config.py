import os
from pathlib import Path


_dotenv_path = Path(__file__).resolve().parents[1] / ".env"
if _dotenv_path.exists():
    try:
        from dotenv import load_dotenv
        load_dotenv(_dotenv_path, override=True)
    except ImportError:
        try:
            for raw_line in _dotenv_path.read_text(encoding="utf-8").splitlines():
                line = raw_line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ.setdefault(key.strip(), value.strip().strip("\"'"))
        except OSError:
            pass


BACKEND_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = BACKEND_ROOT / "data"
FILES_DIR = BACKEND_ROOT / "Files"
MODEL_DIR = BACKEND_ROOT / "models"


def _env_bool(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default

# Wake word configuration
WAKE_WORD_ENABLED = _env_bool("WAKE_WORD_ENABLED", False)
WAKE_WORD_PHRASE = os.getenv("WAKE_WORD_PHRASE", "hey astra").strip().lower()
# Placeholder threshold (not used by Vosk fallback but configurable)
try:
    WAKE_WORD_THRESHOLD = _env_float("WAKE_WORD_THRESHOLD", 0.5)
except (TypeError, ValueError):
    WAKE_WORD_THRESHOLD = 0.5

TTS_ENABLED = _env_bool("TTS_ENABLED", True)
SPEECH_RECOGNITION_ENABLED = _env_bool("SPEECH_RECOGNITION_ENABLED", True)
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").strip().upper()
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")

# Normal conversation AI model
AI_MODEL = os.getenv("AI_MODEL", "qwen3:1.7b").strip()

# Agent planner model used ONLY for structured task planning.
# AGENT_MODEL is the canonical setting; AGENT_PLANNER_MODEL remains a
# backward-compatible alias. The planner NEVER falls back to AI_MODEL.
AGENT_MODEL = (
    os.getenv("AGENT_MODEL")
    or os.getenv("AGENT_PLANNER_MODEL")
    or "qwen3:4b"
).strip()
AGENT_PLANNER_MODEL = AGENT_MODEL

# Backward compatibility: OLLAMA_MODEL maps to AI_MODEL
OLLAMA_MODEL = AI_MODEL

AI_TIMEOUT = _env_float("AI_TIMEOUT", 90.0)
AGENT_PLANNER_TIMEOUT = _env_float("AGENT_PLANNER_TIMEOUT", 45.0)
OLLAMA_TIMEOUT = AI_TIMEOUT

# Planner output token budget. Spec default is 128; qwen3:4b pretty-prints
# JSON under Ollama structured-output mode, so two-step plans need ~140
# tokens. Override via AGENT_PLANNER_NUM_PREDICT when planning truncates.
try:
    AGENT_PLANNER_NUM_PREDICT = int(os.getenv("AGENT_PLANNER_NUM_PREDICT", "128"))
except (TypeError, ValueError):
    AGENT_PLANNER_NUM_PREDICT = 128

# Audio settings (match app.voice defaults)
TARGET_SAMPLE_RATE = int(os.getenv("TARGET_SAMPLE_RATE", "16000"))
