from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any, List, Type, TypeVar, cast

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from flex_agent.config import PROJECT_ROOT
from flex_agent.models import DimensionDetail, TextItem


PROMPTS_DIR = PROJECT_ROOT / "prompts"
ModelT = TypeVar("ModelT", bound=BaseModel)


def _read_prompt_file(filename: str) -> str:
    return (PROMPTS_DIR / filename).read_text(encoding="utf-8")


def _extract_json_object(raw_text: str) -> str:
    cleaned = raw_text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[a-zA-Z0-9_-]*\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
        cleaned = cleaned.strip()
    if cleaned.startswith("{") and cleaned.endswith("}"):
        return cleaned
    match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
    if match:
        return match.group(0)
    raise ValueError("Model response does not contain a JSON object.")


def _raw_result_to_content(result: Any) -> tuple[str, BaseMessage | None]:
    if isinstance(result, BaseMessage):
        content = result.content
        if isinstance(content, str):
            return content, result
        return json.dumps(content, ensure_ascii=False, default=str), result
    if isinstance(result, str):
        return result, None
    return str(result), None


async def ainvoke_structured(
    llm: BaseChatModel,
    prompt: ChatPromptTemplate,
    schema: Type[ModelT],
    payload: dict,
) -> ModelT:
    parser = PydanticOutputParser(pydantic_object=schema)
    invoke_payload = dict(payload)
    invoke_payload["format_instructions"] = parser.get_format_instructions()
    chain = prompt | llm
    result = await chain.ainvoke(invoke_payload)
    raw_content, _ = _raw_result_to_content(result)
    try:
        return cast(ModelT, parser.parse(raw_content))
    except Exception as exc:
        try:
            json_str = _extract_json_object(raw_content)
            return schema.model_validate(json.loads(json_str))
        except Exception as fallback_exc:
            raise RuntimeError(
                f"Structured output parsing failed for {schema.__name__}: {exc}; fallback: {fallback_exc}"
            ) from fallback_exc


class PromptContext(BaseModel):
    grounded_theory_background: str
    task_background: str
    bob_template: str
    alice_template: str
    kevin_template: str

    @classmethod
    def load(cls) -> "PromptContext":
        gt_background = _read_prompt_file("grounded_theory_background.md")
        task_background = _read_prompt_file("task_background.md")
        return cls(
            grounded_theory_background=gt_background,
            task_background=task_background,
            bob_template=_read_prompt_file("agent_bob.md").format(
                grounded_theory_background=gt_background,
                task_background=task_background,
            ),
            alice_template=_read_prompt_file("agent_alice.md").format(
                grounded_theory_background=gt_background,
                task_background=task_background,
            ),
            kevin_template=_read_prompt_file("agent_kevin.md").format(
                grounded_theory_background=gt_background,
                task_background=task_background,
            ),
        )


class BobItemDetail(BaseModel):
    name: str = Field(description="对提取短语的中文简短概括。")
    evidence: str | None = Field(default=None, description="原评论中的精确或近似原文证据。")
    normalized_label: str = Field(description="该条目的主中文维度。")
    reason: str | None = Field(default=None, description="一句简短中文说明，解释为何该证据支持该维度。")


class BobOutput(BaseModel):
    content_with_labels: str
    items: List[BobItemDetail] = Field(default_factory=list)


class AliceDimensionDetail(BaseModel):
    name: str = Field(description="维度名称。")
    items: List[str] = Field(description="属于该维度的规范化中文条目标签，必须来自 items_pool。")
    definition: str = Field(description="用一句简洁的中文定义该维度的边界。")


class AliceOutput(BaseModel):
    dimensions: List[AliceDimensionDetail] = Field(default_factory=list)


class KevinDimensionDetail(BaseModel):
    name: str = Field(description="维度名称。")
    items: List[str] = Field(
        description="属于该维度的规范化中文条目标签，必须来自传入的 items_pool 或已有维度。"
    )
    definition: str = Field(description="用一句简洁的中文定义该维度的边界。")


class KevinOutput(BaseModel):
    dimensions: List[KevinDimensionDetail] = Field(default_factory=list)


ItemDetailInput = list[dict[str, Any]]


def _json_prompt_value(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2)


def _format_dimensions_json(existing_dimensions: list[DimensionDetail]) -> str:
    return _json_prompt_value(
        [
            {
                "name": dimension.name,
                "items": list(dimension.items),
                "definition": dimension.definition,
            }
            for dimension in existing_dimensions
        ]
    )


async def arun_bob(
    llm: BaseChatModel,
    prompt_ctx: PromptContext,
    text: TextItem,
) -> BobOutput:
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", prompt_ctx.bob_template + "\n\n{format_instructions}"),
            ("human", "text_id: {text_id}\ncontent: {content}"),
        ]
    )
    return await ainvoke_structured(
        llm=llm,
        prompt=prompt,
        schema=BobOutput,
        payload={"text_id": text.id, "content": text.content},
    )


async def arun_alice(
    llm: BaseChatModel,
    prompt_ctx: PromptContext,
    items_pool: List[str],
    items_details: ItemDetailInput | None = None,
) -> AliceOutput:
    if items_details:
        human_content = "items_details JSON:\n{items_details}"
        payload = {"items_details": _json_prompt_value(items_details)}
    else:
        human_content = "items_pool JSON:\n{items_pool}"
        payload = {"items_pool": _json_prompt_value(list(items_pool))}

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", prompt_ctx.alice_template + "\n\n{format_instructions}"),
            ("human", human_content),
        ]
    )
    return await ainvoke_structured(llm=llm, prompt=prompt, schema=AliceOutput, payload=payload)


async def arun_kevin(
    llm: BaseChatModel,
    prompt_ctx: PromptContext,
    existing_dimensions: List[DimensionDetail],
    items_pool: List[str],
    items_details: ItemDetailInput | None = None,
) -> KevinOutput:
    if items_details:
        human_content = (
            "current_dimensions JSON:\n{current_dimensions}\n\n"
            "items_details JSON:\n{items_details}"
        )
        payload = {
            "current_dimensions": _format_dimensions_json(existing_dimensions),
            "items_details": _json_prompt_value(items_details),
        }
    else:
        human_content = (
            "current_dimensions JSON:\n{current_dimensions}\n\n"
            "items_pool JSON:\n{items_pool}"
        )
        payload = {
            "current_dimensions": _format_dimensions_json(existing_dimensions),
            "items_pool": _json_prompt_value(list(items_pool)),
        }

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", prompt_ctx.kevin_template + "\n\n{format_instructions}"),
            ("human", human_content),
        ]
    )
    return await ainvoke_structured(llm=llm, prompt=prompt, schema=KevinOutput, payload=payload)
