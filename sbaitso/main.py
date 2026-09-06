"""Web backend: FastAPI serving the xterm.js frontend + a websocket.

Each websocket connection is a fresh session (zero persistence, naturally).
"""

from __future__ import annotations

import asyncio
import json
from contextlib import suppress
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .engine import Engine, EngineArgs, Inputs
from .events import Quit

WEB_DIR = Path(__file__).resolve().parent.parent / "web"

app = FastAPI(title="DR. SBAITSO/2", docs_url=None, redoc_url=None)
app.state.engine_args = EngineArgs(brain="auto")


def configure(engine_args: EngineArgs) -> None:
    """Set process-wide defaults for new web sessions before uvicorn starts."""
    app.state.engine_args = engine_args

app.mount("/assets", StaticFiles(directory=WEB_DIR), name="assets")


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(WEB_DIR / "index.html")


@app.get("/healthz")
async def healthz() -> dict:
    return {"status": "OK", "memory": "640K", "storage": "NONE (AS PROMISED)"}


@app.websocket("/ws")
async def ws(websocket: WebSocket) -> None:
    await websocket.accept()
    inputs = Inputs()
    engine = Engine.from_args(websocket.app.state.engine_args)

    async def sender() -> None:
        try:
            async for ev in engine.run(inputs):
                await websocket.send_text(json.dumps(ev.to_dict()))
                if isinstance(ev, Quit):
                    break
        except Exception:
            pass  # client vanished mid-prescription; nothing to save anyway
        with suppress(Exception):
            await websocket.close()

    send_task = asyncio.create_task(sender())
    try:
        while True:
            if send_task.done():
                break
            msg = await websocket.receive_text()
            data = json.loads(msg)
            if data.get("type") == "input":
                inputs.push(data.get("text", ""))
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        inputs.close()
        with suppress(Exception):
            await send_task
