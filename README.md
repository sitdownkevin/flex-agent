# flex-agent

基于 [deepagents](https://github.com/langchain-ai/deepagents) 的扎根理论编码 Agent。编码结果持久化到本地 workspace 文件，不再使用 LangGraph State 存储编码内容。

## 特性

- **DeepAgent 主编排器**：`write_todos` 自主规划，`task` 调度 Bob / Alice / Kevin 子 Agent
- **文件即状态**：`coding/`、`codebook/`、`corpus/` 等目录是唯一持久化来源
- **交互式 CLI**：Plan / Step Timeline / Workspace 状态，Claude Code 风格步骤流
- **内置 Open Coding 评测**：TUI `/eval:open` 对比人工 benchmark（JMIS Consistency / Precision / Recall）
- **gt-agent 兼容导出**：`exports/open_coding_result_*.json` 可继续用于 legacy eval
- **可切换 Prompt / Workspace**：支持多套提示词与 workspace 分类，便于 A/B 评测

## 快速开始

```bash
cd flex-agent
uv sync
cp env.example .env   # 配置 OPENAI_API_KEY 等
uv run flex-agent
```

默认使用 `prompts/baseline` 提示词与 `workspaces/baseline` 数据目录。启动时会自动将 `data/codebook_done.jsonl` 与 `data/codebook_done_human.jsonl` 播种到 workspace。

切换 prompt 集或 workspace 分类：

```bash
uv run flex-agent --prompts-dir baseline
uv run flex-agent --workspace exp-v2
uv run flex-agent --prompts-dir exp-v2 --workspace exp-v2
```

参数支持简写名（如 `baseline` → `prompts/baseline` / `workspaces/baseline`）、相对路径或绝对路径。

示例指令：

```text
> 对 /corpus/codebook_done.jsonl 做 open coding，max_nums=30, codebook_nums=10, kevin_batch_size=5
```

Slash 命令：

- `/status` — 查看 workspace 计数（含 session / run 中的 prompt 与 workspace 分类）
- `/tree` — 打印 codebook 树
- `/export` — 导出 gt-agent 兼容 JSON
- `/eval:open` — 评测当前 open coding（默认 both：维度名匹配 + LLM 语义对齐）
- `/eval:open keyword` — 仅维度名匹配（无 LLM）
- `/eval:open both --align` — 额外启用维度名 LLM 映射
- `/clear` — 清除运行产物（保留 `corpus/` 与 `private/`，含 `eval/`）
- `/help` — 帮助

## 目录布局

```text
flex-agent/
├── prompts/
│   └── baseline/                   # 默认 prompt 集
│       ├── agent_*.md
│       ├── *_background.md
│       └── eval_*.md
└── workspaces/                     # 多个 workspace 分类（gitignore）
    └── baseline/
        ├── meta/
        │   ├── session.json        # CLI 会话：prompts_dir + workspace_dir
        │   └── run.json            # 运行元数据（含 prompts_dir / workspace_dir）
        ├── corpus/
        │   ├── codebook_done.jsonl # 输入语料（无 GT 标签）
        │   ├── raw.jsonl
        │   ├── queue.json
        │   └── partition.json
        ├── private/
        │   └── codebook_done_human.jsonl  # 人工 benchmark（子 Agent 不可访问）
        ├── coding/{id}.json
        ├── codebook/dimensions.json
        ├── codebook/batches/{n}.json
        ├── quality/warnings.json
        ├── eval/
        │   ├── open/               # open coding 评测
        │   └── axial/              # 主轴编码评测（预留）
        └── exports/
            └── open_coding_result_*.json
```

## 测试

```bash
uv run python -m unittest discover -s tests -v
```

测试目录与源码分包对应：`tests/test_path_resolver.py`、`tests/workspace/`、`tests/coding/`、`tests/evaluation/`、`tests/ui/`。

评测相关 prompt 位于 `prompts/baseline/eval_text_alignment.md` 与 `prompts/baseline/eval_dimension_name_alignment.md`。

## 源码结构

```text
src/flex_agent/
├── cli.py, config.py       # 入口与配置（含 prompts/workspace 路径解析）
├── prompts/                # 共享 prompt 加载
├── models/                 # 数据结构
├── workspace/              # 文件持久化（Python 模块）
├── coding/                 # LLM 编码、质量检查、导出
├── eval/                   # Open coding 评测（/eval:open）
├── orchestration/          # DeepAgent 编排与工具
└── ui/                     # 交互式 CLI
```

## 与 gt-agent 的关系

`gt-agent/` 保留为 legacy 参考实现。`flex-agent/` 是新的 DeepAgent + 文件持久化架构；open coding 评测已内置，无需再单独跑 `gt-agent/scripts/eval_open_coding.py`。
