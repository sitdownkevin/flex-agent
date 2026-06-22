# CODE: COnstruct Development Engine

CODE is a Deep Agents based construct-development harness. The implementation uses
OpenCoding, Inducing, and AxialCoding roles over a persistent workspace while keeping
the historical `flex-agent` command as the local entrypoint.

## Quick start

```bash
cd flex-agent
uv sync
cp env.example .env
uv run flex-agent
```

Switch language, prompt set, or workspace category:

```bash
uv run flex-agent --language en
uv run flex-agent --prompts-dir baseline
uv run flex-agent --workspace exp-v2
uv run flex-agent --prompts-dir exp-v2 --workspace exp-v2
uv run flex-agent --debug
```
