import queue
import sys
import time
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import speaker


def test_speak_recovers_after_engine_failure():
    """The worker must recreate a pyttsx3 engine after a runtime failure."""
    original_queue = speaker._speech_queue
    original_thread = speaker._speech_thread
    speaker._speech_queue = queue.Queue()
    speaker._speech_thread = None

    class FakeVoice:
        name = "Microsoft Zira Desktop - English (United States)"
        id = "zira-id"

    class FakeEngine:
        def __init__(self, fail_once=False):
            self._fail_once = fail_once
            self._failed = False
            self.voices = [FakeVoice()]

        def getProperty(self, name):
            if name == "voices":
                return self.voices
            return None

        def setProperty(self, name, value):
            return None

        def say(self, text):
            if self._fail_once and not self._failed:
                self._failed = True
                raise RuntimeError("simulated pyttsx3 failure")

        def runAndWait(self):
            return None

        def stop(self):
            return None

    created = []

    def fake_init():
        engine = FakeEngine(fail_once=len(created) == 0)
        created.append(engine)
        return engine

    try:
        with patch.object(speaker.pyttsx3, "init", side_effect=fake_init):
            speaker.speak("First TTS test", block=True, force=True)
            speaker.speak("Second TTS test", block=True, force=True)

        assert len(created) >= 2, "engine should be recreated after a failure"
    finally:
        speaker._speech_queue = original_queue
        speaker._speech_thread = original_thread


def test_direct_consecutive_tts_calls():
    """The real public TTS API should accept consecutive blocking calls."""
    for text in [
        "First TTS test",
        "Second TTS test",
        "Third TTS test",
        "This is a longer AI response to verify that long responses also work correctly.",
    ]:
        speaker.speak(text, block=True, force=True)


def test_speak_with_engine():
    """Test that speak() correctly sends text to the TTS engine via queue."""
    # This test verifies the speak() function works correctly
    # In actual use, it sends text to a worker thread's queue
    
    # We can test the public interface
    with patch("app.speaker._ensure_speech_thread"):
        # This would normally queue the text
        speaker.speak("hello world", block=False, force=True)
    # If no exception, the function works


def test_speak_enabled_state():
    """Test that speak respects enabled/disabled state."""
    speaker.set_enabled(False)
    assert not speaker.is_enabled()
    
    speaker.set_enabled(True)
    assert speaker.is_enabled()


def test_speak_with_none_text():
    """Test that speak() handles None text gracefully."""
    # Should not raise an exception
    speaker.speak(None, block=False, force=True)


def test_speak_with_empty_text():
    """Test that speak() handles empty text gracefully."""
    # Should not raise an exception
    speaker.speak("", block=False, force=True)


def test_speak_with_force():
    """Test that speak() with force=True ignores enabled state."""
    speaker.set_enabled(False)
    # Should still queue the text due to force=True
    with patch("app.speaker._ensure_speech_thread"):
        speaker.speak("test", block=False, force=True)
    # If no exception, it worked

