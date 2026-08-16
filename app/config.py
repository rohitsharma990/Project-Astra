import os

# Wake word configuration
WAKE_WORD_ENABLED = os.getenv("WAKE_WORD_ENABLED", "true").lower() in ("1", "true", "yes")
WAKE_WORD_PHRASE = os.getenv("WAKE_WORD_PHRASE", "hey astra").strip().lower()
# Placeholder threshold (not used by Vosk fallback but configurable)
try:
    WAKE_WORD_THRESHOLD = float(os.getenv("WAKE_WORD_THRESHOLD", "0.5"))
except Exception:
    WAKE_WORD_THRESHOLD = 0.5

# Audio settings (match app.voice defaults)
TARGET_SAMPLE_RATE = int(os.getenv("TARGET_SAMPLE_RATE", "16000"))
