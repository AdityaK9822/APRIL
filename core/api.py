"""
APRIL Backend API

Thin FastAPI adapter over the existing AgentRuntime and EventBus. This is the
HTTP/SSE surface that web/desktop frontends (and other systems) can use.

It is intentionally a shim: it does not re-implement agent logic, session state,
or event semantics. All of those continue to live in core.agent and core.events.
"""

from __future__ import annotations

import asyncio
import dataclasses
import json
import logging
import os
from contextlib import suppress
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from .events import get_event_bus, Event
from .browser_service import BrowserService

KNOWN_EVENT_TYPES = [
    "message.delta",
    "message.start",
    "message.done",
    "tool_call.start",
    "tool_call.output",
    "tool_call.done",
    "log",
    "error",
    "status",
    "session",
]


def event_to_dict(event: Event[Any]) -> dict:
    payload = event.payload
    if dataclasses.is_dataclass(payload):
        payload = dataclasses.asdict(payload)
    timestamp = getattr(event, "timestamp", None)
    if isinstance(timestamp, datetime):
        timestamp = timestamp.isoformat()
    return {
        "type": event.event_type,
        "payload": payload,
        "timestamp": timestamp,
        "id": event.id,
    }


class EventBroadcaster:
    """Fan-out bridge from the in-process EventBus to per-connection SSE queues."""

    def __init__(self) -> None:
        self._queues: List[asyncio.Queue] = []
        self._lock = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._subscriptions: List[str] = []

    def start(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop
        bus = get_event_bus()
        for event_type in KNOWN_EVENT_TYPES:
            sub_id = bus.subscribe(event_type, self._forward)
            self._subscriptions.append(sub_id)

    def stop(self) -> None:
        bus = get_event_bus()
        for sub_id in self._subscriptions:
            with suppress(Exception):
                bus.unsubscribe(sub_id)
        self._subscriptions.clear()

    def _forward(self, event: Event[Any]) -> None:
        if self._loop is None:
            return
        data = event_to_dict(event)
        for queue in list(self._queues):
            with suppress(Exception):
                self._loop.call_soon_threadsafe(queue.put_nowait, data)

    async def register(self, queue: asyncio.Queue) -> None:
        self._queues.append(queue)

    async def unregister(self, queue: asyncio.Queue) -> None:
        with suppress(ValueError):
            self._queues.remove(queue)


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None


class ClearRequest(BaseModel):
    session_id: Optional[str] = None


class BrowserOpenRequest(BaseModel):
    session_id: Optional[str] = None
    viewport_width: int = 1280
    viewport_height: int = 800


class BrowserNavigateRequest(BaseModel):
    session_id: str
    url: str
    wait_until: str = "domcontentloaded"
    timeout_ms: int = 30_000


class BrowserActionRequest(BaseModel):
    session_id: str
    action_type: str
    selector: Optional[str] = None
    text: Optional[str] = None
    key: Optional[str] = None
    timeout_ms: int = 30_000


class BrowserCloseRequest(BaseModel):
    session_id: str


def create_default_agent():
    """Build an AgentRuntime from environment/config. May return None on failure."""
    try:
        from .config import AgentConfig
        from .agent import AgentRuntime

        config = AgentConfig.from_env()
        return AgentRuntime(config)
    except Exception as exc:  # pragma: no cover - depends on local env
        logging.getLogger("april.api").error("Failed to create default agent: %s", exc)
        return None


def create_app(agent=None):
    app = FastAPI(title="APRIL Agent API", version="0.1.0")

    app.state.agent = agent
    app.state.broadcaster = None
    app.state.browser_service = None

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:4173",
            "http://127.0.0.1:4173",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.on_event("startup")
    async def _startup() -> None:
        loop = asyncio.get_event_loop()
        if app.state.agent is None:
            app.state.agent = create_default_agent()
        if app.state.browser_service is None:
            app.state.browser_service = BrowserService()
            await app.state.browser_service.start()
        if app.state.broadcaster is None:
            broadcaster = EventBroadcaster()
            broadcaster.start(loop)
            app.state.broadcaster = broadcaster

    @app.on_event("shutdown")
    async def _shutdown() -> None:
        broadcaster = app.state.broadcaster
        if broadcaster is not None:
            broadcaster.stop()
        browser_service = app.state.browser_service
        if browser_service is not None:
            await browser_service.stop()

    @app.get("/healthz")
    async def healthz() -> dict:
        agent = app.state.agent
        return {
            "status": "ok",
            "agent": agent is not None,
            "session_id": getattr(getattr(agent, "session", None), "id", None),
        }

    @app.get("/api/events")
    async def events(request: Request) -> StreamingResponse:
        broadcaster = request.app.state.broadcaster
        queue: asyncio.Queue = asyncio.Queue()

        async def stream():
            await broadcaster.register(queue)
            try:
                yield "event: connected\ndata: {\"status\": \"connected\"}\n\n"
                while True:
                    if await request.is_disconnected():
                        break
                    try:
                        item = await asyncio.wait_for(queue.get(), timeout=15.0)
                    except asyncio.TimeoutError:
                        yield ": keepalive\n\n"
                        continue
                    yield f"event: {item['type']}\ndata: {json.dumps(item)}\n\n"
            finally:
                await broadcaster.unregister(queue)

        return StreamingResponse(stream(), media_type="text/event-stream")

    @app.post("/api/chat")
    async def chat(request: Request, body: ChatRequest) -> StreamingResponse:
        agent = request.app.state.agent
        if agent is None:
            raise RuntimeError("Agent is not available")

        async def stream():
            yield "event: chat.started\ndata: {\"status\": \"started\"}\n\n"
            try:
                async for token in agent.run_streaming(body.message):
                    yield "event: message.delta\n" + f"data: {json.dumps({'content': token})}\n\n"
                yield "event: chat.done\ndata: {\"status\": \"done\"}\n\n"
            except Exception as exc:  # pragma: no cover
                yield "event: error\ndata: " + json.dumps({"message": str(exc)}) + "\n\n"

        return StreamingResponse(stream(), media_type="text/event-stream")

    @app.post("/api/sessions/clear")
    async def clear(body: ClearRequest = ClearRequest()) -> dict:
        agent = app.state.agent
        if agent is not None:
            agent.clear_context()
        return {"status": "cleared"}

    @app.get("/api/context")
    async def context() -> dict:
        agent = app.state.agent
        if agent is None:
            return {"available": False}
        return {"available": True, **agent.get_context_summary()}

    def _browser_service() -> BrowserService:
        service = app.state.browser_service
        if service is None:
            raise RuntimeError("Browser service is not available")
        return service

    @app.post("/api/browser/open")
    async def browser_open(body: BrowserOpenRequest = BrowserOpenRequest()) -> dict:
        service = _browser_service()
        session = await service.open_session(
            session_id=body.session_id,
            viewport_width=body.viewport_width,
            viewport_height=body.viewport_height,
        )
        await service.navigate(session.id, "about:blank")
        return await service.get_state(session.id, include_screenshot=True)

    @app.post("/api/browser/navigate")
    async def browser_navigate(body: BrowserNavigateRequest) -> dict:
        service = _browser_service()
        state = await service.navigate(
            session_id=body.session_id,
            url=body.url,
            wait_until=body.wait_until,
            timeout_ms=body.timeout_ms,
        )
        return state

    @app.post("/api/browser/action")
    async def browser_action(body: BrowserActionRequest) -> dict:
        service = _browser_service()
        state = await service.action(
            session_id=body.session_id,
            action_type=body.action_type,
            selector=body.selector,
            text=body.text,
            key=body.key,
            timeout_ms=body.timeout_ms,
        )
        return state

    @app.get("/api/browser/screenshot/{session_id}")
    async def browser_screenshot(session_id: str) -> dict:
        service = _browser_service()
        return await service.get_state(session_id, include_screenshot=True)

    @app.get("/api/browser/content/{session_id}")
    async def browser_content(session_id: str) -> dict:
        service = _browser_service()
        return await service.get_state(session_id, include_screenshot=False)

    @app.post("/api/browser/close")
    async def browser_close(body: BrowserCloseRequest) -> dict:
        service = _browser_service()
        await service.close_session(body.session_id)
        return {"status": "closed", "session_id": body.session_id}

    @app.get("/api/browser/sessions")
    async def browser_sessions() -> dict:
        service = _browser_service()
        return {"sessions": await service.list_sessions()}

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "core.api:app",
        host=os.getenv("APRIL_API_HOST", "127.0.0.1"),
        port=int(os.getenv("APRIL_API_PORT", "8000")),
        reload=False,
    )