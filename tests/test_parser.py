import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import parser


class ParserTests(unittest.TestCase):
    def test_open_command_normalizes_common_phrases(self):
        with patch.object(parser, "open_youtube") as open_youtube_mock, patch("app.parser.ui.assistant_message"):
            parser.parse_command("Please open YouTube for me")

        open_youtube_mock.assert_called_once_with()

    def test_open_command_extracts_target_website_from_sentence(self):
        with patch.object(parser, "open_website") as open_website_mock, patch("app.parser.ui.assistant_message"):
            parser.parse_command("open github for me")

        open_website_mock.assert_called_once_with("github")

    def test_aliases_route_to_the_correct_app(self):
        with patch.object(parser, "open_chrome") as open_chrome_mock, patch("app.parser.ui.assistant_message"):
            parser.parse_command("browser")

        open_chrome_mock.assert_called_once_with()

    def test_find_file_command_invokes_file_search(self):
        with patch.object(parser, "find_files") as find_files_mock, patch("app.parser.ui.assistant_message"):
            parser.parse_command("find report")

        find_files_mock.assert_called_once_with("report")

    def test_search_file_command_invokes_file_search(self):
        with patch.object(parser, "find_files") as find_files_mock, patch("app.parser.ui.assistant_message"):
            parser.parse_command("search file report")

        find_files_mock.assert_called_once_with("report")

    def test_play_music_command_invokes_music_control(self):
        with patch.object(parser, "music_control") as music_control_mock, patch("app.parser.ui.assistant_message"):
            parser.parse_command("play music")

        music_control_mock.assert_called_once_with("play")

    def test_system_shutdown_command_invokes_shutdown(self):
        with patch.object(parser, "shutdown") as shutdown_mock, patch("app.parser.ui.assistant_message"):
            parser.parse_command("shutdown")

        shutdown_mock.assert_called_once_with()

    def test_unknown_question_routes_to_ai_fallback(self):
        with patch.object(parser, "ask_ai", return_value="Nova answer") as ask_ai_mock, patch("app.parser.ui.assistant_message"):
            parser.parse_command("what is python")

        ask_ai_mock.assert_called_once_with("what is python")

    def test_short_unknown_command_routes_to_ai(self):
        with patch.object(parser, "ask_ai", return_value="Nova answer") as ask_ai_mock, patch("app.parser.ui.assistant_message"):
            parser.parse_command("python")

        ask_ai_mock.assert_called_once_with("python")

    def test_greeting_responds_locally(self):
        with patch("app.parser.ui.assistant_message") as assistant_message_mock:
            parser.parse_command("hi")

        assistant_message_mock.assert_called_once_with("Hello! How can I help you today?")

    def test_speak_command_responds_immediately(self):
        with patch("app.parser.ui.assistant_message") as assistant_message_mock:
            parser.parse_command("speak hello world")

        assistant_message_mock.assert_called_once_with("hello world", speak_force=True)


if __name__ == "__main__":
    unittest.main()
