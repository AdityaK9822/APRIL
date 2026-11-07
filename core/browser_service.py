"""Browser service for APRIL ADE browser backed by Playwright + Chromium."""

from __future__ import annotations

import asyncio
import base64
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from contextlib import suppress as _context_suppress
from typing import Any, Dict, List, Optional

try:
    from playwright.async_api import async_playwright
except Exception:  # pragma: no cover - imported lazily in code paths
    async_playwright = None  # type: ignore[assignment]


@dataclass
class BrowserSession:
    id: str
    context: Any
    page: Any
    console_logs: List[Dict[str, Any]] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    current_url: str = ""


class BrowserService:
    def __init__(self) -> None:
        self._playwright = None
        self._browser = None
        self._sessions: Dict[str, BrowserSession] = {}
        self._lock = asyncio.Lock()

    def _executable_path(self) -> Optional[str]:
        explicit = os.getenv("APRIL_BROWSER_EXECUTABLE_PATH", "").strip()
        return explicit or None

    def _preferred_channel(self) -> Optional[str]:
        configured = os.getenv("APRIL_BROWSER_CHANNEL", "").strip()
        if configured:
            return configured
        return None

    async def start(self) -> None:
        if async_playwright is None:
            raise RuntimeError("Playwright is not installed")
        if self._browser is not None:
            return
        self._playwright = await async_playwright().start()
        channels_to_try = []
        configured = self._preferred_channel()
        if configured:
            channels_to_try.append(configured)
        else:
            channels_to_try.append("chromium")
            channels_to_try.append("chrome")

        last_error: Optional[Exception] = None
        for channel in channels_to_try:
            try:
                if channel == "chromium":
                    kwargs = {}
                    executable_path = self._executable_path()
                    if executable_path:
                        kwargs["executable_path"] = executable_path
                    self._browser = await self._playwright.chromium.launch(
                        headless=True,
                        **kwargs,
                    )
                else:
                    self._browser = await self._playwright.chromium.launch(
                        channel=channel,
                        headless=True,
                    )
                return
            except Exception as exc:  # pragma: no cover - fallback for local environment
                last_error = exc
                self._browser = None

        if last_error is not None:
            raise last_error

    async def stop(self) -> None:
        async with self._lock:
            for session_id in list(self._sessions):
                try:
                    session = self._sessions.pop(session_id)
                    await session.page.close()
                    await session.context.close()
                except Exception:
                    pass
        if self._browser is not None:
            with _context_suppress(Exception):
                await self._browser.close()
        self._browser = None
        if self._playwright is not None:
            with _context_suppress(Exception):
                await self._playwright.stop()
        self._playwright = None

    async def _ensure_browser(self) -> None:
        if self._browser is None:
            await self.start()

    async def open_session(
        self,
        session_id: Optional[str] = None,
        viewport_width: int = 1280,
        viewport_height: int = 800,
    ) -> BrowserSession:
        await self._ensure_browser()
        async with self._lock:
            if session_id and session_id in self._sessions:
                return self._sessions[session_id]
            sid = session_id or str(uuid.uuid4())
            context = await self._browser.new_context(
                viewport={"width": viewport_width, "height": viewport_height},
                accept_downloads=False,
            )
            page = await context.new_page()
            page.on(
                "console",
                lambda msg: self._sessions[sid].console_logs.append(
                    {"type": msg.type, "text": msg.text}
                ),
            )
            page.on(
                "pageerror",
                lambda err: self._sessions[sid].console_logs.append(
                    {"type": "pageerror", "text": str(err)}
                ),
            )
            session = BrowserSession(id=sid, context=context, page=page)
            self._sessions[sid] = session
            return session

    def get_session(self, session_id: str) -> BrowserSession:
        session = self._sessions.get(session_id)
        if session is None:
            raise KeyError(f"Unknown browser session: {session_id}")
        return session

    async def navigate(
        self,
        session_id: str,
        url: str,
        wait_until: str = "domcontentloaded",
        timeout_ms: int = 30_000,
    ) -> Dict[str, Any]:
        session = self.get_session(session_id)
        await session.page.goto(url, wait_until=wait_until, timeout=timeout_ms)
        session.current_url = session.page.url
        return await self.get_state(session_id, include_screenshot=False)

    async def get_state(
        self, session_id: str, include_screenshot: bool = True, screenshot_limit: int = 2_000_000
    ) -> Dict[str, Any]:
        session = self._sessions[session_id]
        text = ""
        try:
            text = await session.page.inner_text("body")
        except Exception:
            text = ""
        title = ""
        try:
            title = await session.page.title()
        except Exception:
            title = ""

        result: Dict[str, Any] = {
            "session_id": session_id,
            "url": session.page.url,
            "title": title,
            "text_preview": text[:8000],
            "console": {
                "count": len(session.console_logs),
                "errors": [log for log in session.console_logs if log.get("type") in ("error", "pageerror")][:30],
            },
            "created_at": session.created_at.isoformat(),
        }
        if include_screenshot:
            raw = await session.page.screenshot(type="png", full_page=False)
            result["screenshot"] = {
                "format": "png",
                "base64": base64.b64encode(raw).decode("ascii"),
            }
        return result

    async def action(
        self,
        session_id: str,
        action_type: str,
        selector: Optional[str] = None,
        text: Optional[str] = None,
        key: Optional[str] = None,
        timeout_ms: int = 30_000,
    ) -> Dict[str, Any]:
        session = self.get_session(session_id)
        page = session.page

        if action_type == "click":
            if not selector:
                raise ValueError("selector is required for click")
            await page.click(selector, timeout=timeout_ms)
        elif action_type == "type":
            if not selector:
                raise ValueError("selector is required for type")
            if text is None:
                raise ValueError("text is required for type")
            await page.fill(selector, text, timeout=timeout_ms)
        elif action_type == "press":
            if not selector:
                raise ValueError("selector is required for press")
            if not key:
                raise ValueError("key is required for press")
            await page.press(selector, key, timeout=timeout_ms)
        elif action_type == "wait":
            await page.wait_for_timeout(timeout_ms)
        else:
            raise ValueError(f"Unsupported action: {action_type}")

        session.current_url = page.url
        return await self.get_state(session_id, include_screenshot=True)

    async def close_session(self, session_id: str) -> None:
        async with self._lock:
            session = self._sessions.pop(session_id, None)
            if session is None:
                return
        with _context_suppress(Exception):
            await session.page.close()
        with _context_suppress(Exception):
            await session.context.close()

    async def list_sessions(self) -> List[str]:
        return sorted(self._sessions.keys())


class _Suppress:
    def __enter__(self) -> None:
        pass

    def __exit__(self, *args: Any) -> None:
        pass
