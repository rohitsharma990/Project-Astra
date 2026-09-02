import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import memory


class MemoryTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.memory_file = Path(self.tmpdir.name) / "memory.json"
        memory.MEMORY_FILE = self.memory_file

    def test_create_list_read_and_delete_memory(self):
        with patch("builtins.input", return_value="My first memory"):
            memory.create_memory("Test Memory")

        stored = memory.load_memory()
        self.assertIn("Test Memory", stored)
        self.assertEqual(stored["Test Memory"]["name"], "Test Memory")
        self.assertEqual(stored["Test Memory"]["details"], "My first memory")

        with patch("builtins.input", return_value="Test Memory"):
            memory.read_memory()

        memory.delete_memory("Test Memory")
        self.assertEqual(memory.load_memory(), {})


if __name__ == "__main__":
    unittest.main()
