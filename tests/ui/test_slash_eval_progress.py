from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from flex_agent.ui.helpers import handle_slash_command
from flex_agent.workspace import Workspace


class SlashEvalProgressTests(unittest.TestCase):
    def test_eval_open_forwards_on_progress(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws = Workspace(Path(tmp))
            ws.ensure_layout()
            messages: list[str] = []

            def fake_evaluate(_workspace, *, mode, on_progress=None):
                if on_progress is not None:
                    on_progress("[eval] test progress")
                return "eval report"

            with patch("flex_agent.ui.helpers.evaluate_workspace", side_effect=fake_evaluate):
                handled, output = handle_slash_command(
                    ws,
                    "/eval:open",
                    on_progress=messages.append,
                )

            self.assertTrue(handled)
            self.assertEqual(output, "eval report")
            self.assertEqual(messages, ["[eval] test progress"])

    def test_eval_axial_forwards_on_progress(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws = Workspace(Path(tmp))
            ws.ensure_layout()
            messages: list[str] = []

            def fake_evaluate(_workspace, *, mode, align=False, on_progress=None):
                if on_progress is not None:
                    on_progress("[eval:axial] test progress")
                return "axial report"

            with patch("flex_agent.ui.helpers.evaluate_axial_workspace", side_effect=fake_evaluate):
                handled, output = handle_slash_command(
                    ws,
                    "/eval:axial",
                    on_progress=messages.append,
                )

            self.assertTrue(handled)
            self.assertEqual(output, "axial report")
            self.assertEqual(messages, ["[eval:axial] test progress"])


if __name__ == "__main__":
    unittest.main()
