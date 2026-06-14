from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from flex_agent.ui.events import StepRecord, StepStatus, TimelineEntry, TodoItem, UIUpdate
from flex_agent.ui.renderer import PlainCliRenderer, terminal_width


class PlainCliRendererTests(unittest.TestCase):
    def test_todos_only_render_when_changed(self) -> None:
        renderer = PlainCliRenderer()
        workspace = MagicMock()
        todos = [TodoItem(content="step one", status="pending")]
        update = UIUpdate(todos=todos)

        with patch.object(renderer, "_print_line") as print_line:
            renderer.render_update(update, parser=MagicMock(), workspace=workspace)
            first_calls = print_line.call_count
            renderer.render_update(update, parser=MagicMock(), workspace=workspace)
            second_calls = print_line.call_count

        self.assertGreater(first_calls, 0)
        self.assertEqual(first_calls, second_calls)

    def test_workspace_status_dedupes(self) -> None:
        renderer = PlainCliRenderer()
        workspace = MagicMock()
        workspace.status.return_value = {
            "texts_total": 1,
            "coded_count": 0,
            "queue_remaining": 1,
            "dimensions_count": 0,
            "run": None,
        }

        with patch.object(renderer, "_print_line") as print_line:
            renderer.render_workspace_status(workspace)
            renderer.render_workspace_status(workspace)

        self.assertEqual(print_line.call_count, 1)

    def test_step_update_replaces_running_line(self) -> None:
        renderer = PlainCliRenderer()
        running = StepRecord(
            step_id="call-1",
            tool_name="task",
            label="子任务",
            summary="demo",
            status=StepStatus.RUNNING,
        )
        done = StepRecord(
            step_id="call-1",
            tool_name="task",
            label="子任务",
            summary="demo",
            status=StepStatus.DONE,
            result_preview="ok",
        )
        update_running = UIUpdate(
            timeline=[TimelineEntry(kind="step", text="", step_id="call-1")],
            steps={"call-1": running},
        )
        update_done = UIUpdate(
            timeline=[TimelineEntry(kind="step", text="", step_id="call-1")],
            steps={"call-1": done},
        )

        with patch("sys.stdout") as stdout:
            stdout.write = MagicMock()
            stdout.flush = MagicMock()
            renderer.render_update(update_running, parser=MagicMock(), workspace=MagicMock())
            renderer.render_update(update_done, parser=MagicMock(), workspace=MagicMock())

        joined = "".join(call.args[0] for call in stdout.write.call_args_list)
        self.assertIn("\033[A", joined)

    def test_terminal_width_has_sane_minimum(self) -> None:
        with patch("flex_agent.ui.renderer.shutil.get_terminal_size", side_effect=OSError):
            self.assertEqual(terminal_width(default=80), 80)


if __name__ == "__main__":
    unittest.main()
