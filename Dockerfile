# syntax=docker/dockerfile:1

# ---- Frontend build ----
FROM node:22-alpine AS frontend
WORKDIR /app/web/frontend
COPY web/frontend/package.json web/frontend/package-lock.json ./
RUN npm ci
COPY web/frontend/ ./
RUN npm run build

# ---- Runtime ----
FROM python:3.13-slim AS runtime
WORKDIR /app

# uv binary for reproducible python deps
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Install project deps (frozen lockfile, web extras, no dev)
COPY pyproject.toml uv.lock README.md ./
COPY src/ ./src/
COPY web/ ./web/
COPY prompts/ ./prompts/
COPY data/ ./data/
RUN uv sync --frozen --extra web --no-dev

# Built frontend served by FastAPI StaticFiles
COPY --from=frontend /app/web/frontend/dist ./web/frontend/dist

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    HOST=0.0.0.0 \
    PORT=8000

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health').read()"

CMD ["uvicorn", "web.backend.server:app", "--host", "0.0.0.0", "--port", "8000"]
