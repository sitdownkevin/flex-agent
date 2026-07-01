from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, HTTPException, Request, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from flex_agent.config import PROJECT_ROOT, load_env_file, warn_langsmith_tracing

from web.backend.checkpointer import close_checkpointer, init_checkpointer
from web.backend.env_runtime import VALID_PROMPT_SETS
from web.backend.file_validation import validate_jsonl
from web.backend.presence import presence_manager
from web.backend.session_manager import session_manager
from web.backend.ws_handler import ws_message_loop

load_env_file(PROJECT_ROOT / ".env")
warn_langsmith_tracing()

FRONTEND_DIST = PROJECT_ROOT / "web" / "frontend" / "dist"


class EnvOverrides(BaseModel):
    OPENAI_API_KEY: str = ""
    OPENAI_BASE_URL: str = ""
    OPENAI_MODEL: str = ""
    OPENAI_MODEL_PRO: str = ""


class CreateSessionRequest(BaseModel):
    language: str = Field(default="zh", pattern="^(zh|en)$")
    prompt_set: str = Field(default="baseline")
    mode: str = Field(default="env", pattern="^(env|byok)$")
    overrides: EnvOverrides = Field(default_factory=EnvOverrides)

    def overrides_dict(self) -> dict[str, str]:
        raw = self.overrides.model_dump()
        return {k: v.strip() for k, v in raw.items() if v and str(v).strip()}


class UpdateEnvRequest(BaseModel):
    overrides: EnvOverrides = Field(default_factory=EnvOverrides)

    def overrides_dict(self) -> dict[str, str]:
        raw = self.overrides.model_dump()
        return {k: v.strip() for k, v in raw.items() if v and str(v).strip()}


def create_app() -> FastAPI:
    app = FastAPI(title="CODE: COnstructDevelopmentEngine Web TUI", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.on_event("startup")
    async def _startup_checkpointer() -> None:
        await init_checkpointer()

    @app.on_event("shutdown")
    async def _shutdown_checkpointer() -> None:
        await close_checkpointer()

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/presence")
    async def get_presence() -> dict[str, int]:
        return await presence_manager.stats()

    @app.websocket("/api/presence/stream")
    async def presence_stream(websocket: WebSocket) -> None:
        await websocket.accept()
        conn_id = await presence_manager.subscribe(websocket)
        try:
            # Keep the connection open; presence updates are pushed via broadcast.
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            pass
        finally:
            await presence_manager.unsubscribe(conn_id)

    @app.post("/api/sessions")
    def create_session(body: CreateSessionRequest) -> dict[str, Any]:
        if body.prompt_set not in VALID_PROMPT_SETS:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid prompt_set; expected one of: {', '.join(sorted(VALID_PROMPT_SETS))}",
            )
        try:
            return session_manager.create_session(
                language=body.language,
                prompt_set=body.prompt_set,
                mode=body.mode,
                overrides=body.overrides_dict(),
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/sessions/{session_id}")
    def get_session(session_id: str) -> dict[str, Any]:
        try:
            return session_manager.get_session_info(session_id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/sessions/{session_id}/workspace/overview")
    def get_workspace_overview(session_id: str) -> dict[str, Any]:
        try:
            return session_manager.get_workspace_overview(session_id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.delete("/api/sessions/{session_id}")
    def delete_session(session_id: str) -> dict[str, str]:
        try:
            session_manager.delete_session(session_id)
            return {"status": "deleted", "id": session_id}
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/sessions/{session_id}/files/corpus.jsonl")
    def download_corpus(session_id: str) -> FileResponse:
        workspace = _get_workspace_or_404(session_id)
        path = workspace.corpus_seed_path
        if not path.exists():
            raise HTTPException(status_code=404, detail="corpus.jsonl not found")
        return FileResponse(
            path,
            media_type="application/x-ndjson",
            filename="corpus.jsonl",
        )

    @app.get("/api/sessions/{session_id}/files/corpus_with_labels.jsonl")
    def download_corpus_with_labels(session_id: str) -> FileResponse:
        workspace = _get_workspace_or_404(session_id)
        path = workspace.human_benchmark_path
        if not path.exists():
            raise HTTPException(status_code=404, detail="corpus_with_labels.jsonl not found")
        return FileResponse(
            path,
            media_type="application/x-ndjson",
            filename="corpus_with_labels.jsonl",
        )

    @app.put("/api/sessions/{session_id}/files/corpus.jsonl")
    async def upload_corpus(
        session_id: str,
        file: UploadFile = File(...),
    ) -> dict[str, str]:
        workspace = _get_workspace_or_404(session_id)
        content = (await file.read()).decode("utf-8")
        try:
            validate_jsonl(content, "corpus")
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        workspace.ensure_layout()
        workspace.corpus_seed_path.write_text(content, encoding="utf-8")
        session_manager.reset_runtime(session_id)
        return {"status": "ok", "path": str(workspace.corpus_seed_path)}

    @app.put("/api/sessions/{session_id}/files/corpus_with_labels.jsonl")
    async def upload_corpus_with_labels(
        session_id: str,
        file: UploadFile = File(...),
    ) -> dict[str, str]:
        workspace = _get_workspace_or_404(session_id)
        content = (await file.read()).decode("utf-8")
        try:
            validate_jsonl(content, "corpus_with_labels")
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        workspace.ensure_layout()
        workspace.human_benchmark_path.write_text(content, encoding="utf-8")
        session_manager.reset_runtime(session_id)
        return {"status": "ok", "path": str(workspace.human_benchmark_path)}

    @app.get("/api/sessions/{session_id}/exports")
    def list_exports(session_id: str) -> list[str]:
        workspace = _get_workspace_or_404(session_id)
        if not workspace.exports_dir.exists():
            return []
        return sorted(path.name for path in workspace.exports_dir.glob("*.json"))

    @app.get("/api/sessions/{session_id}/exports/{filename}")
    def download_export(session_id: str, filename: str) -> FileResponse:
        if ".." in filename or "/" in filename or "\\" in filename:
            raise HTTPException(status_code=400, detail="Invalid filename")
        workspace = _get_workspace_or_404(session_id)
        path = workspace.exports_dir / filename
        if not path.exists() or not path.is_file():
            raise HTTPException(status_code=404, detail="Export file not found")
        return FileResponse(path, media_type="application/json", filename=filename)

    @app.get("/api/sessions/{session_id}/prompts/task_background.md")
    def get_task_background(session_id: str) -> PlainTextResponse:
        try:
            content = session_manager.get_task_background(session_id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return PlainTextResponse(content, media_type="text/plain; charset=utf-8")

    @app.put("/api/sessions/{session_id}/prompts/task_background.md")
    async def put_task_background(session_id: str, request: Request) -> dict[str, str]:
        body = (await request.body()).decode("utf-8")
        try:
            session_manager.save_task_background(session_id, body)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"status": "ok"}

    @app.get("/api/sessions/{session_id}/env")
    def get_session_env(session_id: str) -> dict[str, Any]:
        try:
            return session_manager.get_env(session_id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.put("/api/sessions/{session_id}/env")
    def update_session_env(session_id: str, body: UpdateEnvRequest) -> dict[str, Any]:
        try:
            return session_manager.save_env(session_id, body.overrides_dict())
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.websocket("/api/sessions/{session_id}/stream")
    async def session_stream(websocket: WebSocket, session_id: str) -> None:
        await websocket.accept()
        presence_conn_id = await presence_manager.register_session(session_id, websocket)
        try:
            runtime = session_manager.get_or_create_runtime(session_id)
        except FileNotFoundError as exc:
            await websocket.send_text(f'{{"type":"error","message":{repr(str(exc))}}}')
            await websocket.close(code=4404)
            await presence_manager.unregister_session(session_id, presence_conn_id)
            return
        except ValueError as exc:
            await websocket.send_text(f'{{"type":"error","message":{repr(str(exc))}}}')
            await websocket.close(code=4400)
            await presence_manager.unregister_session(session_id, presence_conn_id)
            return

        try:
            await ws_message_loop(runtime, websocket)
        except WebSocketDisconnect:
            pass
        finally:
            if runtime.interrupt_event:
                runtime.interrupt_event.set()
            if runtime.active_turn and not runtime.active_turn.done():
                runtime.active_turn.cancel()
            await presence_manager.unregister_session(session_id, presence_conn_id)

    if FRONTEND_DIST.exists():
        # SPA fallback for /share/* paths so the frontend router can handle them
        @app.get("/share/{full_path:path}")
        def spa_share(full_path: str) -> FileResponse:
            return FileResponse(str(FRONTEND_DIST / "index.html"))

        app.mount("/", StaticFiles(directory=str(FRONTEND_DIST), html=True), name="frontend")
    else:

        @app.get("/")
        def frontend_missing() -> PlainTextResponse:
            return PlainTextResponse(
                "Frontend not built. Run: cd web/frontend && npm install && npm run build",
                status_code=503,
            )

    return app


def _get_workspace_or_404(session_id: str):
    try:
        return session_manager.get_workspace(session_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


app = create_app()
