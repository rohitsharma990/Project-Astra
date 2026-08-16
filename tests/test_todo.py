import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import todo


class TodoTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.todo_file = Path(self.tmpdir.name) / "todos.json"
        todo.TODOS_FILE = self.todo_file

    def test_create_list_read_and_delete_todo(self):
        created = todo.create_todo("Learn Python")
        self.assertTrue(created)

        todos = todo.load_todos()
        self.assertIn("Learn Python", todos)
        self.assertFalse(todos["Learn Python"])

        self.assertTrue(todo.read_todo("Learn Python"))

        todo.delete_todo("Learn Python")
        self.assertEqual(todo.load_todos(), {})


if __name__ == "__main__":
    unittest.main()
