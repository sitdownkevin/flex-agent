from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, List, Type, TypeVar, cast

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field, create_model

from flex_agent.i18n import Language, get_bundle, get_language, resolve_language
from flex_agent.models import DimensionDetail, TextItem
from flex_agent.prompts.loader import read_prompt_file

ModelT = TypeVar("ModelT", bound=BaseModel)


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
    language: Language = "zh"

    @classmethod
    def load(cls, prompts_dir: Path | None = None, *, language: str | None = None) -> "PromptContext":
        active_language = resolve_language(language) if language is not None else get_language()
        gt_background = read_prompt_file("grounded_theory_background.md", prompts_dir=prompts_dir)
        task_background = read_prompt_file("task_background.md", prompts_dir=prompts_dir)
        return cls(
            grounded_theory_background=gt_background,
            task_background=task_background,
            bob_template=read_prompt_file("agent_bob.md", prompts_dir=prompts_dir).format(
                grounded_theory_background=gt_background,
                task_background=task_background,
            ),
            alice_template=read_prompt_file("agent_alice.md", prompts_dir=prompts_dir).format(
                grounded_theory_background=gt_background,
                task_background=task_background,
            ),
            kevin_template=read_prompt_file("agent_kevin.md", prompts_dir=prompts_dir).format(
                grounded_theory_background=gt_background,
                task_background=task_background,
            ),
            language=active_language,
        )


_DEFAULT_SCHEMA_DESCRIPTIONS = get_bundle("zh").llm.schema_descriptions


class BobItemDetail(BaseModel):
    name: str = Field(description=_DEFAULT_SCHEMA_DESCRIPTIONS["bob_item_name"])
    evidence: str | None = Field(
        default=None,
        description=_DEFAULT_SCHEMA_DESCRIPTIONS["bob_item_evidence"],
    )
    normalized_label: str = Field(description=_DEFAULT_SCHEMA_DESCRIPTIONS["bob_item_normalized_label"])
    reason: str | None = Field(
        default=None,
        description=_DEFAULT_SCHEMA_DESCRIPTIONS["bob_item_reason"],
    )


class BobOutput(BaseModel):
    content_with_labels: str = Field(
        description=_DEFAULT_SCHEMA_DESCRIPTIONS["bob_content_with_labels"]
    )
    items: List[BobItemDetail] = Field(default_factory=list)


class AliceDimensionDetail(BaseModel):
    name: str = Field(description=_DEFAULT_SCHEMA_DESCRIPTIONS["alice_name"])
    items: List[str] = Field(
        description=_DEFAULT_SCHEMA_DESCRIPTIONS["alice_items"]
    )
    definition: str = Field(description=_DEFAULT_SCHEMA_DESCRIPTIONS["alice_definition"])


class AliceOutput(BaseModel):
    dimensions: List[AliceDimensionDetail] = Field(default_factory=list)


class KevinDimensionDetail(BaseModel):
    name: str = Field(description=_DEFAULT_SCHEMA_DESCRIPTIONS["kevin_name"])
    items: List[str] = Field(
        description=_DEFAULT_SCHEMA_DESCRIPTIONS["kevin_items"]
    )
    definition: str = Field(description=_DEFAULT_SCHEMA_DESCRIPTIONS["kevin_definition"])


class KevinOutput(BaseModel):
    dimensions: List[KevinDimensionDetail] = Field(default_factory=list)


@dataclass(frozen=True)
class AgentSchemaModels:
    bob_item: type[BaseModel]
    bob_output: type[BaseModel]
    alice_dimension: type[BaseModel]
    alice_output: type[BaseModel]
    kevin_dimension: type[BaseModel]
    kevin_output: type[BaseModel]


def get_agent_schema_models(language: str | None = None) -> AgentSchemaModels:
    active_language = resolve_language(language) if language is not None else get_language()
    return _get_agent_schema_models(active_language)


@lru_cache(maxsize=2)
def _get_agent_schema_models(active_language: Language) -> AgentSchemaModels:
    descriptions = get_bundle(active_language).llm.schema_descriptions
    suffix = "Zh" if active_language == "zh" else "En"

    bob_item = create_model(
        f"BobItemDetail{suffix}",
        name=(str, Field(description=descriptions["bob_item_name"])),
        evidence=(str | None, Field(default=None, description=descriptions["bob_item_evidence"])),
        normalized_label=(str, Field(description=descriptions["bob_item_normalized_label"])),
        reason=(str | None, Field(default=None, description=descriptions["bob_item_reason"])),
    )
    bob_output = create_model(
        f"BobOutput{suffix}",
        content_with_labels=(str, Field(description=descriptions["bob_content_with_labels"])),
        items=(list[bob_item], Field(default_factory=list)),  # type: ignore[valid-type]
    )

    alice_dimension = create_model(
        f"AliceDimensionDetail{suffix}",
        name=(str, Field(description=descriptions["alice_name"])),
        items=(list[str], Field(description=descriptions["alice_items"])),
        definition=(str, Field(description=descriptions["alice_definition"])),
    )
    alice_output = create_model(
        f"AliceOutput{suffix}",
        dimensions=(list[alice_dimension], Field(default_factory=list)),  # type: ignore[valid-type]
    )

    kevin_dimension = create_model(
        f"KevinDimensionDetail{suffix}",
        name=(str, Field(description=descriptions["kevin_name"])),
        items=(list[str], Field(description=descriptions["kevin_items"])),
        definition=(str, Field(description=descriptions["kevin_definition"])),
    )
    kevin_output = create_model(
        f"KevinOutput{suffix}",
        dimensions=(list[kevin_dimension], Field(default_factory=list)),  # type: ignore[valid-type]
    )
    return AgentSchemaModels(
        bob_item=bob_item,
        bob_output=bob_output,
        alice_dimension=alice_dimension,
        alice_output=alice_output,
        kevin_dimension=kevin_dimension,
        kevin_output=kevin_output,
    )


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
    schema = get_agent_schema_models(prompt_ctx.language).bob_output
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", prompt_ctx.bob_template + "\n\n{format_instructions}"),
            ("human", "text_id: {text_id}\ncontent: {content}"),
        ]
    )
    parsed = await ainvoke_structured(
        llm=llm,
        prompt=prompt,
        schema=schema,
        payload={"text_id": text.id, "content": text.content},
    )
    return BobOutput.model_validate(parsed.model_dump())


async def arun_alice(
    llm: BaseChatModel,
    prompt_ctx: PromptContext,
    items_pool: List[str],
    items_details: ItemDetailInput | None = None,
) -> AliceOutput:
    schema = get_agent_schema_models(prompt_ctx.language).alice_output
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
    parsed = await ainvoke_structured(llm=llm, prompt=prompt, schema=schema, payload=payload)
    return AliceOutput.model_validate(parsed.model_dump())


async def arun_kevin(
    llm: BaseChatModel,
    prompt_ctx: PromptContext,
    existing_dimensions: List[DimensionDetail],
    items_pool: List[str],
    items_details: ItemDetailInput | None = None,
) -> KevinOutput:
    schema = get_agent_schema_models(prompt_ctx.language).kevin_output
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
    parsed = await ainvoke_structured(llm=llm, prompt=prompt, schema=schema, payload=payload)
    return KevinOutput.model_validate(parsed.model_dump())
