你是一个定性研究专家。请用 **ReAct 范式**将 agent 维度名称映射到 human 标准维度名称。

## 总原则（极宽口径）

**默认倾向 MATCH**。只要 agent 维度与某个 human 维度语义稍微接近、同领域、或存在包含/被包含关系，就映射到该 human 维度。仅当 agent 维度与所有 human 维度完全无关时才 null。

## ReAct 工作流

对**每一个 agent 维度**依次执行：

1. **Thought**：分析该 agent 维度与全部 human 维度的语义关系、包含/被包含关系、上下位关系
2. **Action**：`MATCH <human_dimension>` 或 `NO_MATCH`
3. **Observation**：一句话确认依据

全部 agent 维度处理完后，输出 JSON mapping。

## 映射规则

- 语义相同、近义、同体验范畴、上下位、部分重叠 → MATCH
- 名称包含或被包含且语义范畴一致 → MATCH
- **允许多对一**：多个 agent 维度可映射到同一 human 维度
- 必须为每个 agent 维度给出映射，不得遗漏
- 只输出 JSON，不要解释文字

## 人工标准维度列表

{human_list}

## Agent 生成的维度列表

{agent_list}

请输出 JSON 对象，key 是 agent 维度名称，value 是映射到的人工维度名称（或 null）:
