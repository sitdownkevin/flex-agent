from __future__ import annotations

import json
import unittest

from flex_agent.coding.agents import (
    AliceDimensionDetail,
    BobItemDetail,
    BobOutput,
    KevinDimensionDetail,
    get_agent_schema_models,
)


class AgentStructuredOutputSchemaTests(unittest.TestCase):
    def test_bob_schema_uses_baseline_fragment_terms(self) -> None:
        schema_text = json.dumps(
            {
                "bob_item": BobItemDetail.model_json_schema(),
                "bob_output": BobOutput.model_json_schema(),
            },
            ensure_ascii=False,
        )

        self.assertNotIn("ReAct", schema_text)
        self.assertNotIn("对提取短语", schema_text)
        self.assertIn("对提取片段", schema_text)
        self.assertIn("<p>...</p>", schema_text)
        self.assertIn("不改写原句", schema_text)

    def test_dimension_item_schema_matches_baseline_inputs(self) -> None:
        alice_items = AliceDimensionDetail.model_fields["items"].description or ""
        kevin_items = KevinDimensionDetail.model_fields["items"].description or ""

        self.assertIn("items_details.label", alice_items)
        self.assertIn("items_pool", alice_items)
        self.assertNotIn("必须来自 items_pool。", alice_items)

        self.assertIn("已有代码本条目", kevin_items)
        self.assertIn("当前批次输入", kevin_items)
        self.assertNotIn("传入的 items_pool 或已有维度", kevin_items)

    def test_english_runtime_schema_uses_english_descriptions(self) -> None:
        schemas = get_agent_schema_models("en")
        schema_text = json.dumps(
            {
                "bob_item": schemas.bob_item.model_json_schema(),
                "bob_output": schemas.bob_output.model_json_schema(),
                "alice_dimension": schemas.alice_dimension.model_json_schema(),
                "kevin_dimension": schemas.kevin_dimension.model_json_schema(),
            },
            ensure_ascii=False,
        )

        self.assertIn("concise English summary", schema_text)
        self.assertIn("English dimension", schema_text)
        self.assertIn("<p>...</p>", schema_text)
        self.assertNotIn("中文", schema_text)
        self.assertNotIn("维度名称", schema_text)


if __name__ == "__main__":
    unittest.main()
