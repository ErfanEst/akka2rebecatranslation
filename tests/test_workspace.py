import tempfile
import unittest
from pathlib import Path

from src.artifacts.workspace import WorkspaceExistsError, WorkspaceManager


class WorkspaceTests(unittest.TestCase):
    def test_attempts_are_isolated_and_never_reopened(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            manager = WorkspaceManager(directory)
            candidate = manager.create_candidate("simple counter")
            first = candidate.attempt(1)
            second = candidate.attempt(2)
            self.assertNotEqual(first.root, second.root)
            self.assertEqual(first.root.name, "attempt_1")
            with self.assertRaises(FileExistsError):
                candidate.attempt(1)

    def test_existing_candidate_is_not_overwritten(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            manager = WorkspaceManager(Path(directory))
            manager.create_candidate("candidate")
            with self.assertRaises(WorkspaceExistsError):
                manager.create_candidate("candidate")


if __name__ == "__main__":
    unittest.main()
