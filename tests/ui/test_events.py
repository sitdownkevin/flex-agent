from __future__ import annotations

import unittest

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from flex_agent.ui.events import StepRecord, StepStatus, StreamEventParser
from flex_agent.ui.labels import summarize_tool_args, tool_label
from flex_agent.i18n import set_language


class StreamEventParserTests(unittest.TestCase):
    def test_tool_call_and_result_create_running_then_done_steps(self) -> None:
        parser = StreamEventParser()
        ai = AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "batch_bob_code",
                    "args": {"text_ids": [1, 2, 3]},
                    "id": "call-1",
                }
            ],
        )
        tool = ToolMessage(content="Bob coded 3/3 texts.", tool_call_id="call-1")

        first = parser.consume({"messages": [ai]})
        self.assertEqual(len(first.timeline), 1)
        self.assertIn("Bob 批量编码", first.timeline[0].text)
        self.assertEqual(parser.steps["call-1"].status, StepStatus.RUNNING)

        second = parser.consume({"messages": [ai, tool]})
        self.assertEqual(parser.steps["call-1"].status, StepStatus.DONE)
        self.assertTrue(any("Bob coded" in entry.text for entry in second.timeline))
        self.assertTrue(second.refresh_workspace)

    def test_todos_are_parsed_from_state(self) -> None:
        parser = StreamEventParser()
        update = parser.consume(
            {
                "messages": [],
                "todos": [
                    {"content": "init corpus", "status": "completed"},
                    {"content": "batch bob", "status": "in_progress"},
                ],
            }
        )
        self.assertEqual(len(update.todos), 2)
        self.assertEqual(update.todos[0].status, "completed")
        self.assertEqual(update.todos[1].content, "batch bob")

    def test_human_and_assistant_messages(self) -> None:
        parser = StreamEventParser()
        update = parser.consume(
            {
                "messages": [
                    HumanMessage(content="hello"),
                    AIMessage(content="world"),
                ]
            }
        )
        self.assertEqual([entry.kind for entry in update.timeline], ["user"])
        self.assertEqual(update.streaming_assistant, "world")
        flushed = parser.flush_assistant_text()
        self.assertEqual([entry.kind for entry in flushed.timeline], ["assistant"])

    def test_note_user_message_deduplicates_stream_human(self) -> None:
        parser = StreamEventParser()
        noted = parser.note_user_message("once")
        streamed = parser.consume({"messages": [HumanMessage(content="once")]})
        self.assertEqual(len(noted.timeline), 1)
        self.assertEqual(len(streamed.timeline), 0)

    def test_note_user_message_emit_false_tracks_without_timeline(self) -> None:
        parser = StreamEventParser()
        noted = parser.note_user_message("once", emit=False)
        streamed = parser.consume({"messages": [HumanMessage(content="once")]})
        self.assertEqual(len(noted.timeline), 0)
        self.assertEqual(len(streamed.timeline), 0)

    def test_mark_interrupted_clears_pending_and_running_steps(self) -> None:
        parser = StreamEventParser()
        parser.pending_assistant_text = "partial"
        parser.steps["call-1"] = StepRecord(
            step_id="call-1",
            tool_name="task",
            label="子任务",
            summary="",
            status=StepStatus.RUNNING,
        )
        update = parser.mark_interrupted()
        self.assertEqual(parser.pending_assistant_text, "")
        self.assertEqual(update.steps["call-1"].status, StepStatus.ERROR)
        self.assertEqual(update.steps["call-1"].result_preview, "interrupted")
        self.assertEqual(update.activity_mode, "idle")

    def test_duplicate_messages_are_not_re_emitted(self) -> None:
        parser = StreamEventParser()
        message = HumanMessage(content="once")
        chunk = {"messages": [message]}
        first = parser.consume(chunk)
        second = parser.consume(chunk)
        self.assertEqual(len(first.timeline), 1)
        self.assertEqual(len(second.timeline), 0)

    def test_assistant_streaming_updates_text(self) -> None:
        parser = StreamEventParser()
        ai = AIMessage(content="hel")
        first = parser.consume({"messages": [ai]})
        second = parser.consume({"messages": [AIMessage(content="hello world")]})
        self.assertEqual(first.streaming_assistant, "hel")
        self.assertEqual(second.streaming_assistant, "hello world")
        self.assertEqual(len(second.timeline), 0)


class ToolLabelTests(unittest.TestCase):
    def test_tool_label_mapping(self) -> None:
        set_language("zh")
        self.assertEqual(tool_label("init_open_coding_run"), "初始化语料")
        self.assertEqual(tool_label("unknown_tool"), "unknown_tool")

    def test_tool_label_mapping_english(self) -> None:
        try:
            set_language("en")
            self.assertEqual(tool_label("init_open_coding_run"), "Initialize corpus")
            self.assertEqual(
                summarize_tool_args("batch_bob_code", {"text_ids": [1, 2]}),
                "2 texts",
            )
        finally:
            set_language("zh")

    def test_task_summary(self) -> None:
        summary = summarize_tool_args(
            "task",
            {"subagent_type": "alice-codebook", "description": "review codebook"},
        )
        self.assertIn("alice-codebook", summary)


if __name__ == "__main__":
    unittest.main()
