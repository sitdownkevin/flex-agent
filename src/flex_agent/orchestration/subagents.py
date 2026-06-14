from __future__ import annotations

from flex_agent.coding.agents import PromptContext


def build_subagents(prompt_ctx: PromptContext | None = None) -> list[dict]:
    ctx = prompt_ctx or PromptContext.load()
    return [
        {
            "name": "bob-coder",
            "description": (
                "对单条中文评论做开放式编码，提取体验维度并写入 coding/{id}.json。"
                "适合检查单条编码质量或补编码。"
            ),
            "system_prompt": (
                ctx.bob_template
                + "\n\n你是子 Agent。读取 corpus/raw.jsonl 与 coding/ 文件，"
                "必要时用 write_file 写入 coding/{id}.json。只返回简洁结论。"
            ),
        },
        {
            "name": "alice-codebook",
            "description": (
                "基于 codebook 样本的 Bob 结果归纳初始 dimensions，写入 codebook/dimensions.json。"
            ),
            "system_prompt": (
                ctx.alice_template
                + "\n\n你是子 Agent。从 coding/ 中读取 partition.codebook_text_ids 对应文件，"
                "归纳后写入 codebook/dimensions.json。"
            ),
        },
        {
            "name": "kevin-updater",
            "description": (
                "在现有 codebook/dimensions.json 基础上做保守增量更新，并写 batch 快照。"
            ),
            "system_prompt": (
                ctx.kevin_template
                + "\n\n你是子 Agent。读取 codebook/dimensions.json 与 Kevin 批次对应 coding 文件，"
                "输出完整更新版 dimensions。"
            ),
        },
    ]
