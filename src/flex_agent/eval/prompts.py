from __future__ import annotations

from flex_agent.prompts.loader import read_prompt_file


def text_alignment_prompt() -> str:
    return read_prompt_file("eval_text_alignment.md")


def dimension_name_alignment_prompt(*, human_list: str, agent_list: str) -> str:
    return read_prompt_file("eval_dimension_name_alignment.md").format(
        human_list=human_list,
        agent_list=agent_list,
    )
