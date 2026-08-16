import logging
import threading

import pyttsx3

logger = logging.getLogger(__name__)

_enabled = True
_lock = threading.Lock()


def _female_voice(engine):
    voices = engine.getProperty("voices") or []

    # Prefer Microsoft Zira
    for voice in voices:
        if "zira" in voice.name.lower():
            return voice

    # Other common female voices
    keywords = ("female", "cortana", "victoria", "samantha", "hazel", "eva")

    for voice in voices:
        if any(word in voice.name.lower() for word in keywords):
            return voice

    # English fallback
    for voice in voices:
        if "english" in voice.name.lower():
            return voice

    return voices[0] if voices else None


def speak(text: str, block: bool = True, force: bool = False):
    """Speak the given text using Windows TTS."""

    global _enabled

    if not text:
        return

    if not _enabled and not force:
        return

    text = str(text).strip()

    if not text:
        return

    # Keep only one TTS operation at a time
    with _lock:
        com_initialized = False
        engine = None

        try:
            import pythoncom

            pythoncom.CoInitialize()
            com_initialized = True

            engine = pyttsx3.init()

            engine.setProperty("rate", 160)
            engine.setProperty("volume", 0.9)

            voice = _female_voice(engine)

            if voice:
                engine.setProperty("voice", voice.id)

            engine.say(text)
            engine.runAndWait()

        except Exception:
            logger.exception("TTS failed")

        finally:
            if engine:
                try:
                    engine.stop()
                except Exception:
                    pass

            if com_initialized:
                try:
                    import pythoncom
                    pythoncom.CoUninitialize()
                except Exception:
                    pass


def set_enabled(enabled: bool):
    global _enabled
    _enabled = bool(enabled)


def is_enabled() -> bool:
    return _enabled


__all__ = ["speak", "set_enabled", "is_enabled"]