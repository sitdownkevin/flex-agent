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

## Web TUI (browser)

Run the same TUI experience in a browser. No registration required; each session maps to a workspace under `workspaces/<session_id>/`.

### Install web dependencies

```bash
uv sync --extra web
cd web/frontend && npm install && npm run build
```

### Start server

```bash
uv run agent-web
# or
uv run uvicorn web.backend.server:app --host 0.0.0.0 --port 8000
```

Open `http://localhost:8000`. The entry screen lets you:

- **Open** an existing workspace by `session_id`
- **Create** a new workspace with:
  - **env** mode: use the server `.env` (`OPENAI_API_KEY`, `OPENAI_BASE_URL`, `OPENAI_MODEL`, `OPENAI_MODEL_PRO`)
  - **BYOK** mode: supply your own API credentials (stored per workspace in `workspaces/<session_id>/meta/env.json`)
  - **Prompt set**: `baseline`, `baseline_en`, `baseline_oneshot`, or `baseline_fewshot` (copied into `workspaces/<session_id>/prompts/`)

Inside a workspace you can edit `task_background.md` from the terminal toolbar. Each workspace keeps its own prompt copy and env settings; the CLI (`uv run agent`) is unaffected.

Download `corpus.jsonl` and `corpus_with_labels.jsonl` templates from the sidebar, replace with your data, and upload before running open coding tasks.

### Development

```bash
# terminal 1: backend
uv run uvicorn web.backend.server:app --host 127.0.0.1 --port 8000 --reload

# terminal 2: frontend dev server (proxies /api to backend)
cd web/frontend && npm run dev
```

### Deployment notes

- Reuse the same `.env` as the CLI (`OPENAI_API_KEY`, `OPENAI_BASE_URL`, `OPENAI_MODEL`, etc.).
- Put nginx (or similar) in front for HTTPS; optional basic auth for production.
- **Concurrency:** agent turns and slash commands are serialized globally (one at a time across all sessions) because the existing CLI uses module-level language/workspace globals. File upload, download, and session listing are not serialized.
- **Memory:** workspace files persist across server restarts; in-process LangGraph conversation memory does not. After restart, the agent can continue from saved coding/codebook state via tools like `workspace_status`.

## Docker Compose deployment

A single-container deployment is provided. The image builds the frontend and serves both the static assets and the FastAPI/WebSocket backend on port 8000.

### Quick start

```bash
cp env.example .env
# edit .env: set OPENAI_API_KEY, OPENAI_BASE_URL, OPENAI_MODEL, OPENAI_MODEL_PRO

docker compose up -d --build
curl http://localhost:9876/api/health
```

Open `http://localhost:9876`.

- Workspace data (including `.checkpoints.sqlite` conversation history) is persisted in the `flex-agent-workspaces` volume.
- `.env` is injected via `env_file`; BYOK sessions store their own overrides under `workspaces/<id>/meta/env.json`.
- Change the host port via `FLEX_AGENT_PORT` (defaults to 9876):
  ```bash
  FLEX_AGENT_PORT=8080 docker compose up -d
  ```

### Update to a new version

```bash
git pull
docker compose up -d --build
```

Existing workspace data in the volume is preserved.

### Bind-mount workspaces to the host

To inspect or back up workspace files directly on the host, replace the named volume with a bind mount in `docker-compose.yml`:

```yaml
volumes:
  - ./workspaces:/app/workspaces
```

The CLI (`uv run agent`) is unaffected by Docker deployment and remains available on the host.