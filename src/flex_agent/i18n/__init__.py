from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal, Mapping

Language = Literal["zh", "en"]

VALID_LANGUAGES: tuple[Language, ...] = ("zh", "en")
DEFAULT_LANGUAGE: Language = "zh"
LANGUAGE_ENV_VAR = "FLEX_AGENT_LANGUAGE"

_active_language: Language = DEFAULT_LANGUAGE


@dataclass(frozen=True)
class LLMBundle:
    orchestrator_prompt: str
    private_access_note: str
    open_coding_workspace_schema_note: str
    codebook_workspace_schema_note: str
    subagent_descriptions: Mapping[str, str]
    subagent_addenda: Mapping[str, str]
    schema_descriptions: Mapping[str, str]
    tool_arg_descriptions: Mapping[str, str]
    tool_descriptions: Mapping[str, str]
    eval_semantic_warning: str
    eval_dimension_warning: str
    direct_dimension_alignment_prompt: str
    direct_category_alignment_prompt: str


@dataclass(frozen=True)
class CLIBundle:
    activity_labels: Mapping[str, str]
    tool_labels: Mapping[str, str]
    parser_description: str
    workspace_help: str
    prompts_dir_help: str
    language_help: str
    banner_hint: str
    help_text: str
    no_codebook_data: str
    todo_count: str
    text_count: str
    invalid_eval_mode: str
    eval_failed: str
    axial_eval_failed: str
    cleared_workspace: str
    interrupted: str
    bye: str
    status_unavailable: str
    workspace_prefix: str
    plan_title: str
    running: str


@dataclass(frozen=True)
class ReportBundle:
    open_title: str
    axial_title: str
    direct_open_title: str
    direct_axial_title: str
    metrics_line: str
    coded_and_benchmark: str
    direct_input_line: str
    open_keyword_section: str
    open_semantic_section: str
    axial_keyword_section: str
    axial_semantic_section: str
    no_results: str
    common_texts: str
    human_agent_only: str
    metric_header: str
    counts: str
    three_way: str
    axial_granularity: str
    axial_header_granularity: str
    direct_axial_granularity: str
    summary_saved: str
    report_saved: str
    per_text_aggregated: str
    per_text_written: str
    axial_global_result: str


@dataclass(frozen=True)
class ProgressBundle:
    open_coding_start: str
    open_coding_skip: str
    open_coding_done: str
    open_coding_summary: str
    initialized_run: str
    no_texts_to_code: str
    induction_empty_pool: str
    induction_written: str
    run_not_initialized: str
    no_axial_coding_batches: str
    invalid_batch_index: str
    axial_coding_summary: str
    export_missing_run: str
    export_result: str
    eval_no_results: str
    eval_benchmark_missing: str
    eval_no_coded_texts: str
    eval_start: str
    eval_load_benchmark: str
    eval_aligned_pairs: str
    eval_no_pairs: str
    eval_dimension_mapping: str
    eval_keyword_running: str
    eval_keyword_written: str
    eval_keyword_macro: str
    eval_semantic_macro: str
    eval_generating_report: str
    eval_saved: str
    eval_complete: str
    semantic_pending: str
    semantic_pending_skipped_suffix: str
    semantic_skip: str
    semantic_progress: str
    axial_no_results: str
    axial_no_dimensions: str
    axial_no_valid_dimensions: str
    axial_start: str
    axial_category_mapping: str
    axial_keyword_running: str
    axial_keyword_macro: str
    axial_semantic_skip_complete: str
    axial_semantic_running: str
    axial_semantic_macro: str
    axial_generating_report: str
    axial_saved: str
    axial_complete: str
    axial_aggregate_saved: str
    eval_aggregate_saved: str

    @property
    def bob_start(self) -> str:
        return self.open_coding_start

    @property
    def bob_skip(self) -> str:
        return self.open_coding_skip

    @property
    def bob_done(self) -> str:
        return self.open_coding_done

    @property
    def bob_summary(self) -> str:
        return self.open_coding_summary

    @property
    def alice_empty_pool(self) -> str:
        return self.induction_empty_pool

    @property
    def alice_written(self) -> str:
        return self.induction_written

    @property
    def no_kevin_batches(self) -> str:
        return self.no_axial_coding_batches

    @property
    def kevin_summary(self) -> str:
        return self.axial_coding_summary


@dataclass(frozen=True)
class DirectEvalBundle:
    parser_description: str
    input_help: str
    output_help: str
    batch_size_help: str
    mode_help: str
    limit_help: str
    model_help: str
    resume_help: str
    no_llm_semantic_help: str
    language_help: str
    predictions: str
    report: str


@dataclass(frozen=True)
class TextBundle:
    language: Language
    llm: LLMBundle
    cli: CLIBundle
    report: ReportBundle
    progress: ProgressBundle
    direct: DirectEvalBundle


ZH_ORCHESTRATOR_PROMPT = """你是 flex-agent 主编排器，负责自主完成 VR/元宇宙评论的开放式编码（Open Coding）任务。

## 工作方式

1. 收到用户目标后，先用 `write_todos` 制定计划。
2. 所有编码状态必须持久化到 workspace 文件，不要只在对话里保存结果。
3. 优先调用专用 Python 工具执行批量步骤；必要时再用 `task` 调度子 Agent 做语义判断。
4. 每完成一个阶段，用 `workspace_status` 或 `read_file` 核对文件状态。
5. 全部完成后调用 `export_result` 导出 code-agent 兼容 JSON。
6. 某步工具返回 failed/error 时，分析原因并自动重试或调整参数后继续，不要停下来等用户说 continue。
7. 禁止用 `write_file`/`edit_file` 修改 `corpus/partition.json`、`corpus/queue.json`、`corpus/raw.jsonl`；这些只能由 `init_open_coding_run` 写入。

## Workspace 布局

- `corpus/codebook_done.jsonl`：原始输入语料（初始化时作为 data_path，不含人工 GT 标签）
- `private/codebook_done_human.jsonl`：人工评测 benchmark（仅主编排器可访问；编码时禁止读取）
- `corpus/raw.jsonl`：`init_open_coding_run` 采样后的工作副本，不要把它当作初始化数据源
- `corpus/queue.json`：待编码 id
- `corpus/partition.json`：seed/update pool 划分
- `coding/{id}.json`：OpenCoding 单条编码结果
- `codebook/dimensions.json`：当前代码本
- `codebook/batches/{n}.json`：AxialCoding 批次快照
- `quality/warnings.json`：质量告警
- `exports/open_coding_result_*.json`：编码结果导出
- `eval/open/`：open coding 评测结果（`summary.json`、`report.txt`、`{id}.json`）
- `eval/axial/`：主轴编码评测结果（用户 TUI 触发 `/eval:axial`；编码时禁止读取）

编码过程中禁止读取 `private/`、`eval/` 或将其中内容传递给子 Agent。用户可在 TUI 使用 `/eval:open` 或 `/eval:axial` 离线评测，无需你调用评测工具。

## 标准 SOP

1. `init_open_coding_run`：从原始 jsonl（如 `/corpus/codebook_done.jsonl`）加载、采样、初始化 corpus 与 partition
2. `batch_open_coding`：并发编码全部文本，写入 `coding/`
3. `run_construct_induction`：基于 seed pool 生成初始 dimensions
4. `run_axial_coding`：按 update pool 批次更新代码本
5. `export_result`：导出评估兼容结果

若初始化失败或 corpus 状态不一致，重新调用 `init_open_coding_run` 并指定正确的原始 data_path；不要手动改 corpus 文件。

## 子 Agent

- `open-coding`：单条文本开放式编码专家
- `construct-induction`：初始代码本归纳专家
- `axial-coding`：保守增量更新代码本专家

当用户要求检查、解释或微调某个文件内容时，可结合 `read_file`/`grep` 与子 Agent 协作。
请用中文与用户沟通，保持简洁、可审计。
"""


EN_ORCHESTRATOR_PROMPT = """You are the flex-agent orchestrator. Your job is to complete open coding for VR/metaverse review data in a persistent workspace.

## Operating Model

1. When you receive a user goal, first call `write_todos` to make a plan.
2. All coding state must be persisted to workspace files; do not keep results only in the conversation.
3. Prefer the dedicated Python tools for batch steps; use `task` subagents only when semantic judgment or file review is needed.
4. After each phase, verify file state with `workspace_status` or `read_file`.
5. When the run is complete, call `export_result` to create the code-agent compatible JSON export.
6. If a step returns failed/error, analyze the cause, retry or adjust parameters, and continue without waiting for the user to say continue.
7. Do not use `write_file` or `edit_file` to modify `corpus/partition.json`, `corpus/queue.json`, or `corpus/raw.jsonl`; only `init_open_coding_run` may write those files.

## Workspace Layout

- `corpus/codebook_done.jsonl`: source input corpus, used as initialization `data_path`, without human GT labels
- `private/codebook_done_human.jsonl`: human evaluation benchmark, visible only to the orchestrator; do not read it during coding
- `corpus/raw.jsonl`: sampled working copy from `init_open_coding_run`; do not treat it as the original data source
- `corpus/queue.json`: text ids still waiting for coding
- `corpus/partition.json`: seed/update pool split
- `coding/{id}.json`: OpenCoding single-text coding result
- `codebook/dimensions.json`: current codebook
- `codebook/batches/{n}.json`: AxialCoding batch snapshot
- `quality/warnings.json`: quality warnings
- `exports/open_coding_result_*.json`: exported coding result
- `eval/open/`: open-coding evaluation results (`summary.json`, `report.txt`, `{id}.json`)
- `eval/axial/`: axial-coding evaluation results, triggered by the TUI `/eval:axial`; do not read during coding

During coding, do not read `private/` or `eval/`, and do not pass their content to subagents. The user can run `/eval:open` or `/eval:axial` in the TUI for offline evaluation; you do not need to call evaluation tools.

## Standard SOP

1. `init_open_coding_run`: load and sample from the original jsonl, such as `/corpus/codebook_done.jsonl`, and initialize corpus and partition files
2. `batch_open_coding`: code every queued text concurrently and write `coding/`
3. `run_construct_induction`: create initial dimensions from the seed pool
4. `run_axial_coding`: update the codebook from update-pool batches
5. `export_result`: export the evaluation-compatible result

If initialization fails or corpus state is inconsistent, call `init_open_coding_run` again with the correct original `data_path`; do not manually edit corpus files.

## Subagents

- `open-coding`: single-text open coding specialist
- `construct-induction`: initial codebook synthesis specialist
- `axial-coding`: conservative incremental codebook updater

When the user asks to inspect, explain, or lightly adjust file contents, combine `read_file`/`grep` with subagent collaboration.
Communicate with the user in English, and keep responses concise and auditable.
"""


ZH_BUNDLE = TextBundle(
    language="zh",
    llm=LLMBundle(
        orchestrator_prompt=ZH_ORCHESTRATOR_PROMPT,
        private_access_note=(
            "\n\n禁止访问 `private/` 与 `eval/` 目录及其内容；这些目录仅用于主编排器离线评测，"
            "不得读取、引用或向其他 Agent 传递其中数据。"
        ),
        open_coding_workspace_schema_note=(
            "\n\n聊天回复可以简洁；如需写入 `coding/{id}.json`，内容必须是单个 JSON 对象，字段为 "
            "`id`、`content`、`content_with_labels`、`items`，其中 `items` 的元素包含 "
            "`name`、`evidence`、`normalized_label`、`reason`。"
        ),
        codebook_workspace_schema_note=(
            "\n\n聊天回复可以简洁；如需写入 `codebook/dimensions.json` 或批次快照，文件内容必须是"
            "维度对象数组，每个对象包含 `name`、`items`、`definition`；不要写成带 `dimensions` 包装层的对象。"
        ),
        subagent_descriptions={
            "open-coding": "对单条中文评论做开放式编码，提取体验维度并写入 coding/{id}.json。适合检查单条编码质量或补编码。",
            "construct-induction": "基于 seed pool 的 OpenCoding 结果归纳初始 dimensions，写入 codebook/dimensions.json。",
            "axial-coding": "在现有 codebook/dimensions.json 基础上做保守增量更新，并写 batch 快照。",
        },
        subagent_addenda={
            "open-coding": "\n\n你是 OpenCoding 子代理。读取 corpus/raw.jsonl 与 coding/ 文件，必要时用 write_file 写入 coding/{id}.json。",
            "construct-induction": "\n\n你是 Inducing 子代理。从 coding/ 中读取 partition.codebook_text_ids 对应 seed pool 文件，归纳后写入 codebook/dimensions.json。",
            "axial-coding": "\n\n你是 AxialCoding 子代理。读取 codebook/dimensions.json 与 update-pool 批次对应 coding 文件，输出完整更新版 dimensions。",
        },
        schema_descriptions={
            "open_coding_item_name": "对提取片段的中文简短概括。",
            "open_coding_item_evidence": "原评论中的精确或近似原文证据。",
            "open_coding_item_normalized_label": "该条目的主中文维度。",
            "open_coding_item_reason": "一句简短中文说明，解释为何该证据支持该维度。",
            "open_coding_content_with_labels": "原始内容，只在被提取片段外包裹 <p>...</p> 标签，不改写原句或使用其他标签。",
            "induction_dimension_name": "维度名称。",
            "induction_dimension_items": "属于该维度的中文条目标签，必须来自 items_details.label 或 items_pool 中的原始标签。",
            "induction_dimension_definition": "用一句简洁的中文定义该维度的边界。",
            "axial_coding_dimension_name": "维度名称。",
            "axial_coding_dimension_items": "属于该维度的中文条目列表，必须是已有代码本条目或当前批次输入中的原始标签。",
            "axial_coding_dimension_definition": "用一句简洁的中文定义该维度的边界。",
            "semantic_match_thought": "可选的简短判断依据。",
            "semantic_match_action": "可选的简短匹配结果标记。",
            "semantic_text_reasoning_trace": "可选的整条文本简短判断摘要。",
            "axial_match_thought": "可选的简短判断依据。",
            "dimension_alignment_mapping": "从 agent 维度到 human 维度的映射；无匹配则为 null。",
        },
        tool_arg_descriptions={
            "data_path": "源 jsonl 路径，每行包含 comments/content 字段，例如 /corpus/codebook_done.jsonl。不要传 corpus/raw.jsonl。",
            "max_nums": "要处理的最大文本数。",
            "codebook_nums": "用于 Inducing 初始代码本 seed pool 的文本数。",
            "kevin_batch_size": "AxialCoding update-pool 批次大小。",
            "sample_mode": "采样方式：sequential 或 random。",
            "random_seed": "采样/划分随机种子。",
            "open_mode": "导出元数据中的 open coding 模式标签。",
            "text_ids": "可选的显式 text id 列表；默认使用 queue 中所有文本。",
            "concurrency_limit": "OpenCoding 并发调用上限。",
            "batch_index": "从 1 开始的 AxialCoding 批次序号；省略则顺序运行所有批次。",
        },
        tool_descriptions={
            "init_open_coding_run": "初始化 workspace 中的 corpus、partition、queue 和空代码本文件。",
            "batch_open_coding": "并发运行 OpenCoding 对 text id 编码，并写入 coding/{id}.json 文件。",
            "run_construct_induction": "基于 seed pool 构建初始 dimensions，并写入 codebook/dimensions.json。",
            "run_axial_coding": "从 update-pool 批次增量更新代码本，并写入批次快照。",
            "export_result": "将 workspace 文件聚合为 code-agent 兼容的 exports/open_coding_result_*.json。",
            "workspace_status": "以 JSON 返回当前 workspace 计数与运行元数据。",
        },
        eval_semantic_warning="  [warn] semantic evidence alignment LLM call failed: {error!r}",
        eval_dimension_warning="  [warn] semantic alignment LLM call failed: {error!r}, falling back to exact match",
        direct_dimension_alignment_prompt=(
            "请判断 direct inference 给出的体验维度是否与人工维度语义等价。\n"
            "只输出 JSON：{{\"mapping\":{{\"agent_dimension\":\"human_dimension or null\"}}}}。\n"
            "允许多个 agent_dimension 匹配同一个 human_dimension；不匹配则为 null。\n\n"
            "评论：{content}\n"
            "人工维度：{human_items}\n"
            "Agent 维度：{agent_items}"
        ),
        direct_category_alignment_prompt=(
            "请将 direct inference 的全局高阶 category 与人工 category taxonomy 做语义映射。\n"
            "要求严格一对一；无法匹配则为 null。\n"
            "只输出 JSON：{{\"mapping\":{{\"agent_category\":\"human_category or null\"}}}}。\n\n"
            "人工 category：{human_categories}\n"
            "Agent category：{agent_categories}"
        ),
    ),
    cli=CLIBundle(
        activity_labels={"thinking": "Agent 思考中", "tool": "执行工具", "streaming": "生成回复"},
        tool_labels={
            "write_todos": "更新计划",
            "init_open_coding_run": "初始化语料",
            "batch_open_coding": "OpenCoding 批量编码",
            "run_construct_induction": "Inducing 归纳代码本",
            "run_axial_coding": "AxialCoding 增量 refinement",
            "export_result": "导出结果",
            "workspace_status": "检查 workspace",
            "task": "子 Agent 任务",
            "read_file": "读取文件",
            "write_file": "写入文件",
            "edit_file": "编辑文件",
            "glob": "搜索文件",
            "grep": "搜索内容",
            "ls": "列出目录",
            "execute": "执行命令",
        },
        parser_description="flex-agent interactive open coding CLI",
        workspace_help="Workspace category or path (default: baseline -> workspaces/baseline).",
        prompts_dir_help="Prompt set name or path. Defaults to baseline for zh and baseline_en for en.",
        language_help="Language for prompts, reports, and code-side text (default: zh or FLEX_AGENT_LANGUAGE).",
        banner_hint="输入 open coding 任务，或 /status /tree /export /eval:open /clear /help · Esc 中断 · exit 退出",
        help_text="\n".join(
            [
                "Slash 命令:",
                "  /status      - 查看 workspace 计数",
                "  /tree        - 打印 codebook 树",
                "  /export      - 导出 open coding JSON",
                "  /eval:open   - 对比人工 benchmark 评测 open coding（默认 both）",
                "  /eval:open keyword|semantic|both|metrics",
                "               metrics = 从 eval/open/*.json 重新聚合 CPR（无 LLM）",
                "  /eval:axial  - 对比人工 category 评测 axial coding（默认 both）",
                "  /eval:axial keyword|semantic|both|metrics",
                "               metrics = 从 eval/axial/*.json 重新聚合 CPR（无 LLM）",
                "  /clear       - 清除 coding/codebook/meta/quality/exports（保留 corpus/ 与 private/）",
                "  /help        - 显示帮助",
                "  Esc      - 中断当前 agent 回合",
                "  exit     - 退出",
            ]
        ),
        no_codebook_data="暂无 codebook 数据",
        todo_count="{count} 项",
        text_count="{count} 条",
        invalid_eval_mode="未知评测模式: {mode}（可选 keyword / semantic / both / metrics）",
        eval_failed="评测失败: {error!r}",
        axial_eval_failed="主轴评测失败: {error!r}",
        cleared_workspace="Cleared workspace (corpus/ and private/ preserved).",
        interrupted="已中断，可继续输入新指令",
        bye="bye",
        status_unavailable="workspace · status unavailable: {error}",
        workspace_prefix="workspace",
        plan_title="Plan",
        running="运行中",
    ),
    report=ReportBundle(
        open_title="flex-agent Open Coding 质量评估",
        axial_title="flex-agent Axial Coding 质量评估",
        direct_open_title="Direct Inference Open Coding 质量评估",
        direct_axial_title="Direct Inference Axial Coding 质量评估",
        metrics_line="指标: JMIS Consistency / Precision / Recall",
        coded_and_benchmark="已编码文本: {coded_count}  人工 benchmark: {benchmark_path}",
        direct_input_line="输入: {input_path}  Direct 预测文本: {predicted_count}",
        open_keyword_section="一、条目层级 — 维度名匹配",
        open_semantic_section="二、条目层级 — 逐文本证据对齐 (LLM)",
        axial_keyword_section="一、维度层级 — category 名匹配",
        axial_semantic_section="二、维度层级 — LLM 语义对齐",
        no_results="未生成任何评测结果。",
        common_texts="共同评估文本数: {common_texts}",
        human_agent_only="仅人工: {human_only}  仅 Agent: {agent_only}",
        metric_header=f"{'指标':<14} {'Micro-Avg':>10}",
        counts="计数: Human={n_human} Agent={n_agent} ∩={n_intersection} ∪={n_union}",
        three_way="三分类: both={both} llm_only={llm_only} human_only={human_only}",
        axial_granularity="评测粒度: workspace（单次全局比较，严格一对一）",
        axial_header_granularity="评测粒度: workspace（codebook {codebook_dimensions_count} 维 vs {human_category_count} 类 category，严格一对一）",
        direct_axial_granularity="评测粒度: workspace (direct category {agent_category_count} 类 vs human {human_category_count} 类，严格一对一)",
        summary_saved="汇总已保存: {path}",
        report_saved="报告文本已保存: {path}",
        per_text_aggregated="已聚合 {count} 条 per-text 结果",
        per_text_written="已写入 {count} 条 per-text 结果",
        axial_global_result="全局结果: eval/axial/{name}",
    ),
    progress=ProgressBundle(
        open_coding_start="[OpenCoding] 开始编码 {total} 条 (concurrency={limit})",
        open_coding_skip="[OpenCoding] 跳过 text_id={text_id} ({done}/{total})",
        open_coding_done="[OpenCoding] 完成 text_id={text_id} ({done}/{total}) · items={items}",
        open_coding_summary="OpenCoding processed {coded}/{total} texts. Skipped={skipped}. Remaining queue={remaining}.",
        initialized_run="Initialized run with {max_nums} texts, seed={codebook}, update={update}.",
        no_texts_to_code="No texts to code.",
        induction_empty_pool="Inducing skipped: empty item pool.",
        induction_written="Inducing wrote {count} dimensions to codebook/dimensions.json.",
        run_not_initialized="Run not initialized.",
        no_axial_coding_batches="No AxialCoding batches to process.",
        invalid_batch_index="Invalid batch_index={batch_index}; valid range 1..{total}.",
        axial_coding_summary="AxialCoding processed {processed} batch(es); dimensions={dimensions}.",
        export_missing_run="Run not initialized; nothing to export.",
        export_result="Exported code-agent compatible result to {path}.",
        eval_no_results="尚无评测结果。请先运行 /eval:open。",
        eval_benchmark_missing="人工 benchmark 未就绪。请确认 flex-agent/data/ 下种子文件存在，并重新启动 CLI。",
        eval_no_coded_texts="尚无已编码文本。请先运行 OpenCoding 编码（batch_open_coding）后再评测。",
        eval_start="[eval] 开始评测 mode={mode}，已编码 {coded_count} 条文本",
        eval_load_benchmark="[eval] 加载人工 benchmark: {path}",
        eval_aligned_pairs="[eval] 对齐 {pairs} 对 (agent={coded_count}, human={human_count}, agent_only={agent_only})",
        eval_no_pairs="无可用对齐文本。请确认 coding/ 与 private/ benchmark 正文一致。",
        eval_dimension_mapping="[eval] LLM 维度名映射: {count} 个未匹配维度",
        eval_keyword_running="[eval] keyword 逐条评测...",
        eval_keyword_written="[eval] keyword 全量完成 → 写入 eval/open/*.json ({count} 条)",
        eval_keyword_macro="[eval] keyword 聚合: C={consistency:.1%} P={precision:.1%} R={recall:.1%}",
        eval_semantic_macro="[eval] semantic 聚合: C={consistency:.1%} P={precision:.1%} R={recall:.1%} (complete {complete}/{total})",
        eval_generating_report="[eval] 生成报告...",
        eval_saved="[eval] 保存结果: {path}",
        eval_complete="[eval] 评测完成",
        semantic_pending="[eval] semantic 待评测 {pending} 条",
        semantic_pending_skipped_suffix=" (已跳过 {skipped} 条 complete)",
        semantic_skip="[eval] semantic 跳过 text_id={text_id}: {error!r}",
        semantic_progress="[eval] semantic {done}/{pending} 完成 (累计 {complete}/{total}): C={consistency:.1%} P={precision:.1%} R={recall:.1%}",
        axial_no_results="尚无主轴评测结果。请先运行 /eval:axial。",
        axial_no_dimensions="尚无 codebook 维度。请先运行 Inducing/AxialCoding 生成 codebook/dimensions.json。",
        axial_no_valid_dimensions="codebook 无有效主轴维度名。",
        axial_start="[eval:axial] 开始 workspace 级评测 mode={mode}：codebook {agent_count} 维 vs {human_count} 类 category",
        axial_category_mapping="[eval:axial] LLM category 映射: {count} 个 agent 主轴维度",
        axial_keyword_running="[eval:axial] keyword 全局评测...",
        axial_keyword_macro="[eval:axial] keyword: C={consistency:.1%} P={precision:.1%} R={recall:.1%}",
        axial_semantic_skip_complete="[eval:axial] semantic 跳过（已有 complete 结果）",
        axial_semantic_running="[eval:axial] semantic 全局评测（1 次 LLM）...",
        axial_semantic_macro="[eval:axial] semantic: C={consistency:.1%} P={precision:.1%} R={recall:.1%}",
        axial_generating_report="[eval:axial] 生成报告...",
        axial_saved="[eval:axial] 保存结果: {path}",
        axial_complete="[eval:axial] 评测完成",
        axial_aggregate_saved="[eval:axial] 聚合完成: {path}",
        eval_aggregate_saved="[eval] 聚合完成: {path}",
    ),
    direct=DirectEvalBundle(
        parser_description="运行自包含 direct inference baseline 与 CPR 评测。",
        input_help="包含评论与人工 benchmark 标签的 JSONL 输入文件。",
        output_help="输出运行目录。",
        batch_size_help="每次 direct inference LLM 调用包含的评论数。",
        mode_help="要生成的评测报告类型。",
        limit_help="可选的最大输入记录数。",
        model_help="覆盖 direct inference 与 semantic eval 使用的 OPENAI_MODEL。",
        resume_help="复用已完成的 batch_*.json 预测文件。",
        no_llm_semantic_help="跳过报告中的可选 LLM 语义对齐部分。",
        language_help="提示词、报告和代码侧文案语言。",
        predictions="预测结果: {path}",
        report="报告: {path}",
    ),
)


EN_BUNDLE = TextBundle(
    language="en",
    llm=LLMBundle(
        orchestrator_prompt=EN_ORCHESTRATOR_PROMPT,
        private_access_note=(
            "\n\nDo not access the `private/` or `eval/` directories or their contents. "
            "They are reserved for offline evaluation by the orchestrator. Do not read, cite, "
            "or pass that data to other agents."
        ),
        open_coding_workspace_schema_note=(
            "\n\nChat replies may be brief. If you write `coding/{id}.json`, the file must be "
            "one JSON object with fields `id`, `content`, `content_with_labels`, and `items`; "
            "each `items` entry contains `name`, `evidence`, `normalized_label`, and `reason`."
        ),
        codebook_workspace_schema_note=(
            "\n\nChat replies may be brief. If you write `codebook/dimensions.json` or batch "
            "snapshots, the file content must be an array of dimension objects. Each object "
            "contains `name`, `items`, and `definition`; do not wrap it in a top-level "
            "`dimensions` object."
        ),
        subagent_descriptions={
            "open-coding": "Open-code one Chinese review, extract experience dimensions, and write coding/{id}.json. Useful for checking or filling one text.",
            "construct-induction": "Synthesize initial dimensions from OpenCoding results in the seed pool and write codebook/dimensions.json.",
            "axial-coding": "Conservatively update the existing codebook/dimensions.json from update-pool batches and write batch snapshots.",
        },
        subagent_addenda={
            "open-coding": "\n\nYou are the OpenCoding subagent. Read corpus/raw.jsonl and coding/ files, and use write_file to write coding/{id}.json when needed.",
            "construct-induction": "\n\nYou are the Inducing subagent. Read coding/ files for partition.codebook_text_ids in the seed pool, then write the synthesized codebook to codebook/dimensions.json.",
            "axial-coding": "\n\nYou are the AxialCoding subagent. Read codebook/dimensions.json and coding files for the update-pool batch, then output the full updated dimensions array.",
        },
        schema_descriptions={
            "open_coding_item_name": "A concise English summary of the extracted fragment.",
            "open_coding_item_evidence": "Exact or approximate source evidence from the original review.",
            "open_coding_item_normalized_label": "The primary English dimension for this item.",
            "open_coding_item_reason": "One brief English sentence explaining why the evidence supports the dimension.",
            "open_coding_content_with_labels": "The original content with only extracted fragments wrapped in <p>...</p>; do not rewrite the sentence or use other tags.",
            "induction_dimension_name": "Dimension name.",
            "induction_dimension_items": "English item labels in this dimension; each must come from items_details.label or the original items_pool labels.",
            "induction_dimension_definition": "One concise English sentence defining the boundary of this dimension.",
            "axial_coding_dimension_name": "Dimension name.",
            "axial_coding_dimension_items": "English item labels in this dimension; each must be an existing codebook item or an original label from the current batch input.",
            "axial_coding_dimension_definition": "One concise English sentence defining the boundary of this dimension.",
            "semantic_match_thought": "Optional brief rationale.",
            "semantic_match_action": "Optional brief match-action marker.",
            "semantic_text_reasoning_trace": "Optional brief summary of the whole-text judgment.",
            "axial_match_thought": "Optional brief rationale.",
            "dimension_alignment_mapping": "Mapping from agent dimension to human dimension, or null if there is no match.",
        },
        tool_arg_descriptions={
            "data_path": "Path to a source jsonl with a comments/content field per line, such as /corpus/codebook_done.jsonl. Do not pass corpus/raw.jsonl.",
            "max_nums": "Maximum number of texts to process.",
            "codebook_nums": "Number of texts for the Inducing seed pool.",
            "kevin_batch_size": "AxialCoding update-pool batch size.",
            "sample_mode": "Sampling mode: sequential or random.",
            "random_seed": "Random seed for sampling and partitioning.",
            "open_mode": "Open-coding mode label for export metadata.",
            "text_ids": "Optional explicit text ids. Defaults to all texts in the queue.",
            "concurrency_limit": "Maximum number of concurrent OpenCoding calls.",
            "batch_index": "1-based AxialCoding batch index. If omitted, runs all update-pool batches sequentially.",
        },
        tool_descriptions={
            "init_open_coding_run": "Initialize corpus, partition, queue, and an empty codebook in workspace files.",
            "batch_open_coding": "Concurrently run OpenCoding for text ids and write coding/{id}.json files.",
            "run_construct_induction": "Build initial dimensions from the seed pool and write codebook/dimensions.json.",
            "run_axial_coding": "Incrementally update the codebook from update-pool batches and write batch snapshots.",
            "export_result": "Aggregate workspace files into code-agent compatible exports/open_coding_result_*.json.",
            "workspace_status": "Return current workspace counters and run metadata as JSON.",
        },
        eval_semantic_warning="  [warn] semantic evidence alignment LLM call failed: {error!r}",
        eval_dimension_warning="  [warn] semantic alignment LLM call failed: {error!r}, falling back to exact match",
        direct_dimension_alignment_prompt=(
            "Judge whether the experience dimensions from direct inference are semantically equivalent to the human dimensions.\n"
            "Output JSON only: {{\"mapping\":{{\"agent_dimension\":\"human_dimension or null\"}}}}.\n"
            "Multiple agent_dimension values may map to the same human_dimension; use null when there is no match.\n\n"
            "Review: {content}\n"
            "Human dimensions: {human_items}\n"
            "Agent dimensions: {agent_items}"
        ),
        direct_category_alignment_prompt=(
            "Map the global high-level categories from direct inference to the human category taxonomy.\n"
            "Require strict one-to-one matching; use null when there is no match.\n"
            "Output JSON only: {{\"mapping\":{{\"agent_category\":\"human_category or null\"}}}}.\n\n"
            "Human categories: {human_categories}\n"
            "Agent categories: {agent_categories}"
        ),
    ),
    cli=CLIBundle(
        activity_labels={"thinking": "Agent thinking", "tool": "Running tool", "streaming": "Writing response"},
        tool_labels={
            "write_todos": "Update plan",
            "init_open_coding_run": "Initialize corpus",
            "batch_open_coding": "Batch OpenCoding",
            "run_construct_induction": "Inducing synthesis",
            "run_axial_coding": "AxialCoding refinement",
            "export_result": "Export result",
            "workspace_status": "Check workspace",
            "task": "Subagent task",
            "read_file": "Read file",
            "write_file": "Write file",
            "edit_file": "Edit file",
            "glob": "Search files",
            "grep": "Search text",
            "ls": "List directory",
            "execute": "Run command",
        },
        parser_description="flex-agent interactive open coding CLI",
        workspace_help="Workspace category or path (default: baseline -> workspaces/baseline).",
        prompts_dir_help="Prompt set name or path. Defaults to baseline for zh and baseline_en for en.",
        language_help="Language for prompts, reports, and code-side text (default: zh or FLEX_AGENT_LANGUAGE).",
        banner_hint="Enter an open coding task, or /status /tree /export /eval:open /clear /help · Esc interrupts · exit quits",
        help_text="\n".join(
            [
                "Slash commands:",
                "  /status      - show workspace counters",
                "  /tree        - print codebook tree",
                "  /export      - export open coding JSON",
                "  /eval:open   - evaluate open coding vs human benchmark (default: both)",
                "  /eval:open keyword|semantic|both|metrics",
                "               metrics = re-aggregate CPR from eval/open/*.json (no LLM)",
                "  /eval:axial  - evaluate axial coding vs human categories (default: both)",
                "  /eval:axial keyword|semantic|both|metrics",
                "               metrics = re-aggregate CPR from eval/axial/*.json (no LLM)",
                "  /clear       - remove coding/codebook/meta/quality/exports (keep corpus/ & private/)",
                "  /help        - show this help",
                "  Esc      - interrupt the current agent turn",
                "  exit     - quit",
            ]
        ),
        no_codebook_data="No codebook data yet",
        todo_count="{count} items",
        text_count="{count} texts",
        invalid_eval_mode="Unknown evaluation mode: {mode} (choose keyword / semantic / both / metrics)",
        eval_failed="Evaluation failed: {error!r}",
        axial_eval_failed="Axial evaluation failed: {error!r}",
        cleared_workspace="Cleared workspace (corpus/ and private/ preserved).",
        interrupted="Interrupted; you can enter a new instruction",
        bye="bye",
        status_unavailable="workspace · status unavailable: {error}",
        workspace_prefix="workspace",
        plan_title="Plan",
        running="running",
    ),
    report=ReportBundle(
        open_title="flex-agent Open Coding Quality Evaluation",
        axial_title="flex-agent Axial Coding Quality Evaluation",
        direct_open_title="Direct Inference Open Coding Quality Evaluation",
        direct_axial_title="Direct Inference Axial Coding Quality Evaluation",
        metrics_line="Metrics: JMIS Consistency / Precision / Recall",
        coded_and_benchmark="Coded texts: {coded_count}  Human benchmark: {benchmark_path}",
        direct_input_line="Input: {input_path}  Direct predicted texts: {predicted_count}",
        open_keyword_section="1. Item Level - Dimension Name Match",
        open_semantic_section="2. Item Level - Per-Text Evidence Alignment (LLM)",
        axial_keyword_section="1. Dimension Level - Category Name Match",
        axial_semantic_section="2. Dimension Level - LLM Semantic Alignment",
        no_results="No evaluation results were generated.",
        common_texts="Common evaluated texts: {common_texts}",
        human_agent_only="Human only: {human_only}  Agent only: {agent_only}",
        metric_header=f"{'Metric':<14} {'Micro-Avg':>10}",
        counts="Counts: Human={n_human} Agent={n_agent} intersection={n_intersection} union={n_union}",
        three_way="Three-way: both={both} llm_only={llm_only} human_only={human_only}",
        axial_granularity="Evaluation granularity: workspace (single global comparison, strict one-to-one)",
        axial_header_granularity="Evaluation granularity: workspace (codebook {codebook_dimensions_count} dimensions vs {human_category_count} human categories, strict one-to-one)",
        direct_axial_granularity="Evaluation granularity: workspace (direct category {agent_category_count} vs human category {human_category_count}, strict one-to-one)",
        summary_saved="Summary saved: {path}",
        report_saved="Report saved: {path}",
        per_text_aggregated="Aggregated {count} per-text results",
        per_text_written="Wrote {count} per-text results",
        axial_global_result="Global result: eval/axial/{name}",
    ),
    progress=ProgressBundle(
        open_coding_start="[OpenCoding] Starting {total} texts (concurrency={limit})",
        open_coding_skip="[OpenCoding] Skipped text_id={text_id} ({done}/{total})",
        open_coding_done="[OpenCoding] Completed text_id={text_id} ({done}/{total}) · items={items}",
        open_coding_summary="OpenCoding processed {coded}/{total} texts. Skipped={skipped}. Remaining queue={remaining}.",
        initialized_run="Initialized run with {max_nums} texts, seed={codebook}, update={update}.",
        no_texts_to_code="No texts to code.",
        induction_empty_pool="Inducing skipped: empty item pool.",
        induction_written="Inducing wrote {count} dimensions to codebook/dimensions.json.",
        run_not_initialized="Run not initialized.",
        no_axial_coding_batches="No AxialCoding batches to process.",
        invalid_batch_index="Invalid batch_index={batch_index}; valid range 1..{total}.",
        axial_coding_summary="AxialCoding processed {processed} batch(es); dimensions={dimensions}.",
        export_missing_run="Run not initialized; nothing to export.",
        export_result="Exported code-agent compatible result to {path}.",
        eval_no_results="No evaluation results yet. Run /eval:open first.",
        eval_benchmark_missing="Human benchmark is not ready. Confirm the seed files exist under flex-agent/data/ and restart the CLI.",
        eval_no_coded_texts="No coded texts yet. Run OpenCoding (batch_open_coding) before evaluation.",
        eval_start="[eval] Starting mode={mode}; coded texts={coded_count}",
        eval_load_benchmark="[eval] Loading human benchmark: {path}",
        eval_aligned_pairs="[eval] Aligned {pairs} pairs (agent={coded_count}, human={human_count}, agent_only={agent_only})",
        eval_no_pairs="No aligned texts are available. Confirm coding/ and the private benchmark have matching content.",
        eval_dimension_mapping="[eval] LLM dimension-name mapping: {count} unmatched dimensions",
        eval_keyword_running="[eval] Running keyword per-text evaluation...",
        eval_keyword_written="[eval] Keyword pass complete -> wrote eval/open/*.json ({count} texts)",
        eval_keyword_macro="[eval] keyword aggregate: C={consistency:.1%} P={precision:.1%} R={recall:.1%}",
        eval_semantic_macro="[eval] semantic aggregate: C={consistency:.1%} P={precision:.1%} R={recall:.1%} (complete {complete}/{total})",
        eval_generating_report="[eval] Generating report...",
        eval_saved="[eval] Saved result: {path}",
        eval_complete="[eval] Evaluation complete",
        semantic_pending="[eval] semantic pending {pending} texts",
        semantic_pending_skipped_suffix=" (skipped {skipped} complete)",
        semantic_skip="[eval] semantic skipped text_id={text_id}: {error!r}",
        semantic_progress="[eval] semantic {done}/{pending} complete (total {complete}/{total}): C={consistency:.1%} P={precision:.1%} R={recall:.1%}",
        axial_no_results="No axial evaluation results yet. Run /eval:axial first.",
        axial_no_dimensions="No codebook dimensions yet. Run Inducing/AxialCoding to generate codebook/dimensions.json first.",
        axial_no_valid_dimensions="The codebook has no valid axial dimension names.",
        axial_start="[eval:axial] Starting workspace evaluation mode={mode}: codebook {agent_count} dimensions vs {human_count} human categories",
        axial_category_mapping="[eval:axial] LLM category mapping: {count} agent axial dimensions",
        axial_keyword_running="[eval:axial] Running keyword global evaluation...",
        axial_keyword_macro="[eval:axial] keyword: C={consistency:.1%} P={precision:.1%} R={recall:.1%}",
        axial_semantic_skip_complete="[eval:axial] semantic skipped; complete result already exists",
        axial_semantic_running="[eval:axial] Running semantic global evaluation (1 LLM call)...",
        axial_semantic_macro="[eval:axial] semantic: C={consistency:.1%} P={precision:.1%} R={recall:.1%}",
        axial_generating_report="[eval:axial] Generating report...",
        axial_saved="[eval:axial] Saved result: {path}",
        axial_complete="[eval:axial] Evaluation complete",
        axial_aggregate_saved="[eval:axial] Aggregation complete: {path}",
        eval_aggregate_saved="[eval] Aggregation complete: {path}",
    ),
    direct=DirectEvalBundle(
        parser_description="Run self-contained direct inference baseline and CPR evaluation.",
        input_help="JSONL input with comments and human benchmark labels.",
        output_help="Output run directory.",
        batch_size_help="Number of comments per direct inference LLM call.",
        mode_help="Which evaluation report(s) to generate.",
        limit_help="Optional maximum number of input records to process.",
        model_help="Override OPENAI_MODEL for direct inference and semantic eval.",
        resume_help="Reuse complete batch_*.json prediction files.",
        no_llm_semantic_help="Skip optional LLM semantic alignment sections in reports.",
        language_help="Language for prompts, reports, and code-side text.",
        predictions="Predictions: {path}",
        report="Report: {path}",
    ),
)

BUNDLES: Mapping[Language, TextBundle] = {
    "zh": ZH_BUNDLE,
    "en": EN_BUNDLE,
}


def resolve_language(spec: str | None = None) -> Language:
    raw = spec if spec is not None else os.getenv(LANGUAGE_ENV_VAR, DEFAULT_LANGUAGE)
    value = str(raw or DEFAULT_LANGUAGE).strip().lower()
    if value not in VALID_LANGUAGES:
        allowed = ", ".join(VALID_LANGUAGES)
        raise ValueError(f"Unsupported language {raw!r}; expected one of: {allowed}")
    return value  # type: ignore[return-value]


def set_language(spec: str | None = None) -> Language:
    global _active_language
    _active_language = resolve_language(spec)
    return _active_language


def get_language() -> Language:
    return _active_language


def get_bundle(language: str | None = None) -> TextBundle:
    return BUNDLES[resolve_language(language) if language is not None else get_language()]


def default_prompts_name(language: str | None = None) -> str:
    return "baseline_en" if (resolve_language(language) if language is not None else get_language()) == "en" else "baseline"
