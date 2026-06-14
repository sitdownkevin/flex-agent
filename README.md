# flex-agent

基于 [deepagents](https://github.com/langchain-ai/deepagents) 的扎根理论编码 Agent。编码结果持久化到本地 workspace 文件，不再使用 LangGraph State 存储编码内容。

## 特性

- **DeepAgent 主编排器**：`write_todos` 自主规划，`task` 调度 Bob / Alice / Kevin 子 Agent
- **文件即状态**：`coding/`、`codebook/`、`corpus/` 等目录是唯一持久化来源
- **交互式 CLI**：Plan / Step Timeline / Workspace 状态，Claude Code 风格步骤流
- **gt-agent 兼容导出**：`exports/open_coding_result_*.json` 可直接用于 eval 脚本

## 快速开始

```bash
cd flex-agent
uv sync
cp env.example .env   # 配置 OPENAI_API_KEY 等
uv run flex-agent
```

示例指令：

```text
> 对 data/codebook_done.jsonl 做 open coding，max_nums=30, codebook_nums=10, kevin_batch_size=5
```

Slash 命令：

- `/status` — 查看 workspace 计数
- `/tree` — 打印 codebook 树
- `/export` — 导出 gt-agent 兼容 JSON
- `/help` — 帮助

## Workspace 布局

```text
workspace/
├── meta/run.json
├── corpus/raw.jsonl
├── corpus/queue.json
├── corpus/partition.json
├── coding/{id}.json
├── codebook/dimensions.json
├── codebook/batches/{n}.json
├── quality/warnings.json
└── exports/open_coding_result_*.json
```

## 测试

```bash
uv run python -m unittest discover -s tests -v
```

测试目录与源码分包对应：`tests/workspace/`、`tests/coding/`、`tests/ui/`。

## 源码结构

```text
src/flex_agent/
├── cli.py, config.py       # 入口与配置
├── models/                 # 数据结构
├── workspace/              # 文件持久化
├── coding/                 # LLM 编码、质量检查、导出
├── orchestration/          # DeepAgent 编排与工具
└── ui/                     # 交互式 CLI
```

## 与 gt-agent 的关系

`gt-agent/` 保留为 legacy 参考实现。`flex-agent/` 是新的 DeepAgent + 文件持久化架构。
