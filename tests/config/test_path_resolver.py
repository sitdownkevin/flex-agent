from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from flex_agent.config import (
    DEFAULT_PROMPTS_DIR,
    DEFAULT_WORKSPACE,
    PROJECT_ROOT,
    REQUIRED_PROMPT_FILES,
    get_prompts_dir,
    path_label,
    resolve_prompts_dir,
    resolve_workspace_dir,
    set_prompts_dir,
)


class PathResolverTests(unittest.TestCase):
    def test_resolve_prompts_dir_shorthand(self) -> None:
        resolved = resolve_prompts_dir("baseline")
        self.assertEqual(resolved, DEFAULT_PROMPTS_DIR.resolve())
        for name in REQUIRED_PROMPT_FILES:
            self.assertTrue((resolved / name).is_file())

    def test_resolve_prompts_dir_relative(self) -> None:
        resolved = resolve_prompts_dir("prompts/baseline")
        self.assertEqual(resolved, DEFAULT_PROMPTS_DIR.resolve())

    def test_resolve_workspace_dir_shorthand(self) -> None:
        resolved = resolve_workspace_dir("baseline")
        self.assertEqual(resolved, DEFAULT_WORKSPACE.resolve())

    def test_resolve_workspace_dir_relative(self) -> None:
        resolved = resolve_workspace_dir("workspaces/baseline")
        self.assertEqual(resolved, DEFAULT_WORKSPACE.resolve())

    def test_resolve_workspace_dir_absolute(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            resolved = resolve_workspace_dir(tmp)
            self.assertEqual(resolved, Path(tmp).resolve())

    def test_path_label_relative(self) -> None:
        label = path_label(DEFAULT_PROMPTS_DIR)
        self.assertEqual(label, "prompts/baseline")

    def test_resolve_prompts_dir_missing_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            empty = Path(tmp) / "empty"
            empty.mkdir()
            with self.assertRaises(FileNotFoundError):
                resolve_prompts_dir(empty)

    def test_set_prompts_dir_updates_session(self) -> None:
        set_prompts_dir("baseline")
        self.assertEqual(get_prompts_dir(), DEFAULT_PROMPTS_DIR.resolve())


if __name__ == "__main__":
    unittest.main()
