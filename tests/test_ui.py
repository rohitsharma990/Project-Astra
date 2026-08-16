import io
import sys
from pathlib import Path
from unittest.mock import call, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import ui


def test_conversation_messages_format_correctly():
    buffer = io.StringIO()

    with patch("sys.stdout", buffer):
        ui.user_message("Open Chrome")
        ui.assistant_message("Opening Chrome...")

    output = buffer.getvalue()
    assert "🎤 You   : Open Chrome" in output
    assert "🤖 Nova : Opening Chrome..." in output


def test_assistant_message_uses_single_blocking_tts_call():
    with patch("app.ui.speak") as speak_mock:
        ui.assistant_message("What is Java?", speak_force=True)

    speak_mock.assert_called_once_with("What is Java?", block=True, force=True)


def test_assistant_message_forces_tts_even_without_explicit_override():
    with patch("app.ui.speak") as speak_mock:
        ui.assistant_message("What is Python?", speak_force=False)

    speak_mock.assert_called_once_with("What is Python?", block=True, force=True)


def test_speak_assistant_reply_converts_to_string_before_speaking():
    with patch("app.ui.speaker.speak") as speak_mock:
        ui.speak_assistant_reply({"answer": "Python is fun."})

    speak_mock.assert_called_once_with("{'answer': 'Python is fun.'}", block=True, force=True)


def test_consecutive_assistant_messages_each_speak_once():
    with patch("app.ui.speak") as speak_mock:
        for message in ["What is Python?", "What is Java?", "What is C++?"]:
            ui.assistant_message(message, speak_force=True)

    assert speak_mock.call_args_list == [
        call("What is Python?", block=True, force=True),
        call("What is Java?", block=True, force=True),
        call("What is C++?", block=True, force=True),
    ]
