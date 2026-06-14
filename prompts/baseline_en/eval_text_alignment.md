你是一个定性研究评估专家。请用 **ReAct 范式**判断每条文本中 LLM 编码维度是否与人工编码维度语义重合。

## 总原则

**默认判为匹配（both）**。只要 agent 维度与某个 human 维度语义稍微接近、属于同一体验范畴、或存在包含/被包含关系，就输出该 human dimension。**只有** agent 维度与全部 human 维度在语义上完全风马牛不相及时，才输出 null。

## ReAct 工作流

对**每一条文本**中的**每一个 agent 维度**，依次执行：

1. **Thought**：结合 `content`、该 agent 维度的 `evidences`/`reasons`，以及全部 human 维度，分析：
   - 语义是否相同、近义、上下位、部分重叠
   - 名称是否存在包含或被包含
   - 证据是否指向同一体验侧面
   - 是否属于同一感官/服务/价格/舒适度/趣味性/环境等大类
2. **Action**：`MATCH <human_dimension>` 或 `NO_MATCH`
3. **Observation**：一句话确认 Action 的依据

全部 agent 维度处理完后，汇总为 JSON。

## 输出要求

- **允许多对一**：多个 agent 维度可以匹配同一个 human dimension；每个 agent 维度独立判断，不必做全局唯一分配
- 每个 agent 维度必须有一条 match 记录，含 `thought`、`action`、`matched_human_dimension`
- `matched_human_dimension` 只能使用输入中已有的 human 维度名称
- 不得在未逐项 ReAct 推理后将所有 agent 维度一律标为 null
- 只输出 JSON

## 输入数据

{texts_json}
