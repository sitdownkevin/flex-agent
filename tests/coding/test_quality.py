from __future__ import annotations

import unittest

from flex_agent.coding.quality import (
    clean_content_markup,
    extract_item_details,
    extract_item_pool,
    item_dimension,
    merge_new_items_into_dimensions,
    normalize_finished_text,
    parse_labels,
    review_dimensions,
)
from flex_agent.models import DimensionDetail, FinishedItemDetail, FinishedTextItem


class OpenCodingQualityTests(unittest.TestCase):
    def test_parse_labels_normalizes_and_drops_invalid_labels(self) -> None:
        labels = "staff_patience:+1; neutral; playfulness:+1; bad_label; 服务态度:+1"
        warnings = None

        parsed = parse_labels(labels, warnings)

        self.assertEqual(parsed, ["专业度:+1", "趣味性:+1", "态度:+1"])

    def test_clean_content_markup_rewrites_non_p_tags(self) -> None:
        cleaned, warnings = clean_content_markup(
            '这个游戏<e>很有意思</e>，<span title="趣味性:+1">下次还来</span>'
        )

        self.assertEqual(cleaned, "这个游戏<p>很有意思</p>，<p>下次还来</p>")
        self.assertGreaterEqual(warnings.invalid_markup, 2)

    def test_normalize_finished_text_normalizes_dimensions(self) -> None:
        finished = FinishedTextItem(
            id=1,
            content="员工讲解耐心，游戏好玩",
            content_with_labels="<e>员工讲解耐心</e>，<p>游戏好玩</p>",
            items=[
                FinishedItemDetail(
                    name="员工讲解耐心",
                    normalized_label="员工指导",
                    evidence="员工讲解耐心",
                ),
                FinishedItemDetail(
                    name="游戏好玩",
                    normalized_label="playfulness",
                    evidence="游戏好玩",
                ),
            ],
        )

        normalized, warnings = normalize_finished_text(finished)

        self.assertEqual(normalized.content_with_labels, "<p>员工讲解耐心</p>，<p>游戏好玩</p>")
        self.assertEqual(
            [item.normalized_label for item in normalized.items],
            ["专业度", "趣味性"],
        )
        self.assertEqual(extract_item_pool([normalized]), ["专业度", "趣味性"])
        self.assertGreaterEqual(warnings.normalized_labels, 1)

    def test_normalize_finished_text_supports_legacy_labels(self) -> None:
        finished = FinishedTextItem(
            id=1,
            content="员工讲解耐心，游戏好玩",
            content_with_labels="<p>员工讲解耐心</p>，<p>游戏好玩</p>",
            items=[
                FinishedItemDetail(
                    name="员工讲解耐心",
                    labels="staff_guidance:+1;neutral;趣味性:+1",
                    evidence="员工讲解耐心",
                )
            ],
        )

        normalized, warnings = normalize_finished_text(finished)

        self.assertEqual([item.normalized_label for item in normalized.items], ["专业度", "趣味性"])
        self.assertGreaterEqual(warnings.neutral_labels, 1)

    def test_normalize_finished_text_wraps_missing_evidence(self) -> None:
        finished = FinishedTextItem(
            id=2,
            content="老板人很好，游戏种类多",
            content_with_labels="老板人很好，游戏种类多",
            items=[
                FinishedItemDetail(
                    name="老板态度好",
                    normalized_label="态度",
                    evidence="老板人很好",
                ),
                FinishedItemDetail(
                    name="游戏种类多",
                    normalized_label="丰富度",
                    evidence="游戏种类多",
                ),
            ],
        )

        normalized, warnings = normalize_finished_text(finished)

        self.assertEqual(normalized.content_with_labels, "<p>老板人很好</p>，<p>游戏种类多</p>")
        self.assertEqual(warnings.invalid_markup, 2)

    def test_merge_new_items_does_not_append_unassigned_items_to_existing_dimensions(self) -> None:
        dimensions = [
            DimensionDetail(name="服务互动", items=["态度", "专业度"]),
            DimensionDetail(name="游玩体验", items=["趣味性"]),
        ]

        merged, warnings = merge_new_items_into_dimensions(dimensions, ["服务态度", "创新性"])

        self.assertEqual(merged[0].items, ["态度", "专业度"])
        self.assertEqual(merged[1].items, ["趣味性"])
        self.assertTrue(any("unassigned items skipped" in note for note in warnings.notes))
        self.assertTrue(any("创新性" in note for note in warnings.notes))

    def test_merge_new_items_supports_new_dimensions_without_unassigned_fallback(self) -> None:
        dimensions = [
            DimensionDetail(name="服务互动", items=["态度"]),
            DimensionDetail(name="游玩体验", items=["趣味性"]),
        ]
        new_dimensions = [
            DimensionDetail(
                name="情绪疗愈价值",
                items=["解压感", "陪伴感"],
                definition="体验带来的情绪释放与心理修复价值。",
            )
        ]

        merged, warnings = merge_new_items_into_dimensions(
            dimensions,
            ["解压感", "新鲜感"],
            new_dimensions=new_dimensions,
        )

        self.assertEqual(merged[2].name, "情绪疗愈价值")
        self.assertEqual(merged[2].definition, "体验带来的情绪释放与心理修复价值。")
        self.assertEqual(merged[2].items, ["解压感", "陪伴感"])
        self.assertTrue(any("unassigned items skipped" in note for note in warnings.notes))
        self.assertTrue(any("创新性" in note for note in warnings.notes))

    def test_merge_new_items_limits_new_dimension_proposals(self) -> None:
        dimensions = [
            DimensionDetail(name="服务互动", items=["态度"]),
            DimensionDetail(name="游玩体验", items=["趣味性"]),
        ]
        new_dimensions = [
            DimensionDetail(
                name="情绪疗愈价值",
                items=["解压感", "陪伴感"],
                definition="体验带来的情绪支持与释放价值。",
            ),
            DimensionDetail(
                name="环境适配价值",
                items=["空间感", "私密性"],
                definition="场地与空间配置带来的适配性价值。",
            ),
            DimensionDetail(
                name="稀疏维度",
                items=["单一条目"],
                definition="只有一个条目的稀疏维度。",
            ),
        ]

        merged, warnings = merge_new_items_into_dimensions(
            dimensions,
            [],
            new_dimensions=new_dimensions,
        )

        self.assertEqual([dimension.name for dimension in merged], ["服务互动", "游玩体验", "情绪疗愈价值"])
        self.assertEqual(merged[2].items, ["解压感", "陪伴感"])
        self.assertNotIn("空间感", merged[-1].items)
        self.assertNotIn("私密性", merged[-1].items)
        self.assertNotIn("单一条目", merged[-1].items)
        self.assertTrue(any("max_new_dimensions_per_merge" in note for note in warnings.notes))
        self.assertTrue(any("fewer than 2 unique items" in note for note in warnings.notes))
        self.assertTrue(any("unassigned items skipped" in note for note in warnings.notes))

    def test_merge_new_items_with_empty_dimensions_does_not_create_fallback(self) -> None:
        merged, warnings = merge_new_items_into_dimensions([], ["态度", "趣味性"])

        self.assertEqual(merged, [])
        self.assertTrue(any("no existing dimensions" in note for note in warnings.notes))
        self.assertTrue(any("unassigned items skipped" in note for note in warnings.notes))

    def test_review_dimensions_deduplicates_items(self) -> None:
        dimensions = [
            DimensionDetail(name="服务互动", items=["态度", "服务态度"]),
            DimensionDetail(name="设施体验", items=["物理舒适度", "身体舒适度"]),
        ]

        reviewed, warnings = review_dimensions(dimensions)

        self.assertEqual(reviewed[0].items, ["态度"])
        self.assertEqual(reviewed[1].items, ["物理舒适度"])
        self.assertGreaterEqual(warnings.duplicate_items, 2)

    def test_review_dimensions_preserves_dimension_count(self) -> None:
        dimensions = [
            DimensionDetail(name=f"维度{i}", items=[f"条目{i}"])
            for i in range(12)
        ]

        reviewed, _ = review_dimensions(dimensions)

        self.assertEqual(len(reviewed), 12)

    def test_review_dimensions_records_uncovered_items_without_fallback(self) -> None:
        dimensions = [
            DimensionDetail(name="服务互动", items=["态度"]),
        ]
        finished = [
            FinishedTextItem(
                id=1,
                content="员工很好，游戏好玩",
                content_with_labels="<p>员工很好</p>，<p>游戏好玩</p>",
                items=[
                    FinishedItemDetail(name="员工很好", normalized_label="态度"),
                    FinishedItemDetail(name="游戏好玩", normalized_label="趣味性"),
                ],
            )
        ]

        reviewed, warnings = review_dimensions(dimensions, finished)

        self.assertEqual(len(reviewed), 1)
        self.assertEqual(reviewed[0].name, "服务互动")
        self.assertEqual(reviewed[0].items, ["态度"])
        self.assertTrue(any("uncovered items" in note for note in warnings.notes))
        self.assertTrue(any("趣味性" in note for note in warnings.notes))

    def test_item_dimension_prefers_normalized_label(self) -> None:
        item = FinishedItemDetail(
            name="画面好",
            normalized_label="画面",
            labels="态度:+1",
        )
        self.assertEqual(item_dimension(item), "画面")

    def test_extract_item_pool_from_normalized_label_only(self) -> None:
        finished = FinishedTextItem(
            id=3,
            content="画面很好",
            content_with_labels="<p>画面很好</p>",
            items=[
                FinishedItemDetail(
                    name="画面好",
                    normalized_label="画面",
                    evidence="画面很好",
                )
            ],
        )
        self.assertEqual(extract_item_pool([finished]), ["画面"])

    def test_extract_item_details_returns_json_ready_records(self) -> None:
        finished = FinishedTextItem(
            id=4,
            content="服务很好，游戏好玩",
            content_with_labels="<p>服务很好</p>，<p>游戏好玩</p>",
            items=[
                FinishedItemDetail(
                    name="服务很好",
                    normalized_label="态度",
                    reason="工作人员态度友好。",
                ),
                FinishedItemDetail(
                    name="服务不错",
                    normalized_label="服务态度",
                    reason="工作人员态度友好。",
                ),
                FinishedItemDetail(
                    name="游戏好玩",
                    normalized_label="趣味性",
                    reason="玩法带来娱乐感。",
                ),
                FinishedItemDetail(
                    name="游戏有趣",
                    normalized_label="趣味性",
                    reason="互动过程有趣。",
                ),
            ],
        )

        details = extract_item_details([finished], max_examples=1)

        self.assertEqual(
            details,
            [
                {"label": "态度", "reasons": ["工作人员态度友好。"]},
                {"label": "趣味性", "reasons": ["玩法带来娱乐感。"]},
            ],
        )


if __name__ == "__main__":
    unittest.main()
