# CODE: COnstruct Development Engine

CODE is a Agent with construct-development harness.

## Framework

![Framework](./docs/topo_framework.png)


## Quick start

Install `uv`

```bash
pip install uv
```

Set environment variables

```bash
cd flex-agent
uv sync
cp env.example .env
```

Run the agent

```bash
uv run agent
```

> Switch language, prompt set, or workspace category:
> 
> ```bash
> uv run agent --language en
> uv run agent --prompts-dir baseline
> uv run agent --workspace exp-v2
> uv run agent --prompts-dir exp-v2 --workspace exp-v2
> uv run agent --debug
> ```