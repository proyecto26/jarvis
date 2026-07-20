"""FastAPI bridge between the DANTE UI and the Executor.

Endpoints (canonical, see ui/ARCHITECTURE.md):
  - ``GET /healthz`` (and ``GET /health`` alias) -> ``200 {"ok": true}``
  - ``WS  /ws``  -> protocol v1 (ui/web/src/protocol.ts is the client mirror)

Run:
  uvicorn triforce.server.app:app --host 127.0.0.1 --port 8420
  # or: python -m triforce.server

INVARIANT: this module imports cleanly without fastapi installed. The import
is guarded; a helpful error surfaces only when the ASGI app is actually
served. When google-adk / an LLM backend is unavailable, chats are answered
by the simulated Executor (see triforce.server.executor) and ``server.hello``
carries ``simulated: true``.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import AsyncIterator, Dict, Optional, Tuple

from triforce.server import protocol
from triforce.server.executor import build_responder

logger = logging.getLogger(__name__)


class _OtelDetachNoiseFilter(logging.Filter):
    """Drop OpenTelemetry's benign 'Failed to detach context' errors.

    ADK traces LLM calls with contextvars-based OTel spans. We finalize the
    stream generator from a different asyncio task (cancel/watchdog/aclose),
    so OTel cannot reset its context token and logs a ValueError — harmless,
    widely reported, and pure console noise for this server.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        return "Failed to detach context" not in record.getMessage()


logging.getLogger("opentelemetry.context").addFilter(_OtelDetachNoiseFilter())

INSTALL_HINT = (
    "triforce.server requires FastAPI and uvicorn. Install them with:\n\n"
    '    uv sync --extra server   # or: pip install fastapi "uvicorn[standard]" websockets\n\n'
    "then run: uvicorn triforce.server.app:app --host 127.0.0.1 --port 8420"
)

try:
    from fastapi import FastAPI, WebSocket, WebSocketDisconnect

    FASTAPI_AVAILABLE = True
except ImportError as _exc:  # pragma: no cover — exercised by selftest subprocess
    FastAPI = None  # type: ignore[assignment]
    WebSocket = None  # type: ignore[assignment]
    WebSocketDisconnect = None  # type: ignore[assignment]
    FASTAPI_AVAILABLE = False
    _FASTAPI_IMPORT_ERROR = _exc


# How long the avatar shows "listening" before flipping to "thinking".
LISTENING_BEAT_S = 0.15


def _stall_timeout_s() -> float:
    """Watchdog: max seconds to wait for the responder's first/next chunk.

    A black-holed LLM call yields nothing forever; without this bound the
    exchange could never be cancelled or errored (the cancel event is only
    observed around chunks). Generous by default — real LLM calls are slow.
    """
    try:
        return max(1.0, float(os.getenv("DANTE_STREAM_STALL_TIMEOUT_S", "120")))
    except ValueError:
        return 120.0


class Connection:
    """One WebSocket connection: hello handshake, snapshots, chat exchanges.

    Stateless across connections (no resume/replay). Concurrency model:
    the receive loop and per-exchange tasks share the socket through a
    single send lock; ``agent.state`` is pushed only on change.
    """

    def __init__(self, ws: "WebSocket") -> None:
        self._ws = ws
        self._send_lock = asyncio.Lock()
        self._closed = False
        self._agent_state = "idle"
        self._system_mode = "awake"
        # exchange id -> (task, cancel_event)
        self._exchanges: Dict[str, Tuple[asyncio.Task, asyncio.Event]] = {}
        # Exchanges run strictly one at a time per connection: agent.state is
        # a single shared stream (concurrent writers would contradict each
        # other) and the real Executor's ADK session must never see
        # overlapping invocations. Later chat.sends queue behind this lock.
        self._exchange_lock = asyncio.Lock()
        self._responder, self._simulated = build_responder()

    # -- socket plumbing ---------------------------------------------------

    async def _send(self, message: dict) -> None:
        """Send one frame; swallow failures caused by a racing disconnect."""
        if self._closed:
            return
        async with self._send_lock:
            if self._closed:
                return
            try:
                await self._ws.send_text(json.dumps(message))
            except Exception:  # noqa: BLE001 — client went away mid-send
                self._closed = True

    async def _set_agent_state(self, state: str) -> None:
        if state != self._agent_state:
            self._agent_state = state
            await self._send(protocol.agent_state(state))

    # -- lifecycle -----------------------------------------------------------

    async def run(self) -> None:
        await self._ws.accept()
        await self._send(protocol.server_hello(self._simulated))
        # Snapshots right after server.hello (spec: push current values).
        await self._send(protocol.agent_state(self._agent_state))
        await self._send(protocol.system_mode(self._system_mode))
        try:
            while True:
                raw = await self._ws.receive_text()
                try:
                    await self._dispatch(raw)
                except Exception:  # noqa: BLE001 — dispatch bugs must be loud
                    # A failure handling one frame is a server bug, never
                    # connection teardown: log it visibly (with traceback)
                    # and keep the connection alive instead of silently
                    # dying and dropping the client into demo mode.
                    logger.exception("frame dispatch failed for frame %.200r", raw)
                    await self._send(
                        protocol.error("internal", "internal error while handling a frame")
                    )
        except WebSocketDisconnect:
            logger.debug("client disconnected")
        except Exception as exc:  # noqa: BLE001 — receive-side teardown only
            # Only receive_text failures land here (e.g. receive-after-close
            # RuntimeError during shutdown) — genuine teardown, so stay quiet.
            logger.debug("connection ended: %s", exc)
        finally:
            self._closed = True
            for task, cancel in list(self._exchanges.values()):
                cancel.set()
                task.cancel()
            self._exchanges.clear()

    # -- inbound dispatch ----------------------------------------------------

    async def _dispatch(self, raw: str) -> None:
        result = protocol.parse_client_frame(raw)
        if result.drop_reason:
            logger.info("dropping frame: %s", result.drop_reason)
            return
        if result.reply_error is not None:
            await self._send(result.reply_error)
            return

        msg = result.message
        mtype = msg["type"]
        if mtype == "client.hello":
            logger.info("client.hello from %r", msg.get("client"))
        elif mtype == "ping":
            await self._send(protocol.pong())
        elif mtype == "chat.send":
            await self._start_exchange(msg["id"], msg["text"])
        elif mtype == "chat.cancel":
            self._cancel_exchange(msg["id"])

    # -- chat exchanges --------------------------------------------------------

    async def _start_exchange(self, exchange_id: str, text: str) -> None:
        if exchange_id in self._exchanges:
            await self._send(
                protocol.error(
                    "bad_message",
                    "duplicate chat.send id for an in-flight exchange",
                    exchange_id,
                )
            )
            return
        cancel = asyncio.Event()
        task = asyncio.create_task(self._run_exchange(exchange_id, text, cancel))
        self._exchanges[exchange_id] = (task, cancel)

    def _cancel_exchange(self, exchange_id: str) -> None:
        entry = self._exchanges.get(exchange_id)
        if entry is None:
            logger.info("chat.cancel for unknown/finished id %s — dropped", exchange_id)
            return
        entry[1].set()

    async def _run_exchange(
        self, exchange_id: str, text: str, cancel: asyncio.Event
    ) -> None:
        try:
            async with self._exchange_lock:  # exchanges are serial (see __init__)
                if not cancel.is_set():
                    await self._set_agent_state("listening")
                    await asyncio.sleep(LISTENING_BEAT_S)
                if not cancel.is_set():
                    await self._set_agent_state("thinking")
                    if not await self._stream_reply(exchange_id, text, cancel):
                        return  # error frame already terminated the exchange
                await self._send(protocol.chat_complete(exchange_id))
        except asyncio.CancelledError:
            pass  # connection torn down mid-stream — nothing left to send
        finally:
            self._exchanges.pop(exchange_id, None)
            # Queued exchanges are already in _exchanges, so idle is pushed
            # only when nothing is running OR waiting.
            if not self._exchanges and not self._closed:
                await self._set_agent_state("idle")

    async def _stream_reply(
        self, exchange_id: str, text: str, cancel: asyncio.Event
    ) -> bool:
        """Pump responder chunks into ``chat.delta`` frames.

        Cancel-responsive even while the responder is silent (chat.cancel
        wakes the wait immediately instead of waiting for the next chunk)
        and watchdog-bounded so a hung LLM call errors out rather than
        leaving the exchange pending forever. Returns False when the
        exchange was terminated by an error frame.
        """
        stream = self._responder.stream(text, cancel)
        cancel_waiter: asyncio.Future = asyncio.ensure_future(cancel.wait())
        try:
            first = True
            while not cancel.is_set():
                chunk = await self._next_chunk(stream, cancel_waiter)
                if chunk is None:
                    break
                if first:
                    await self._set_agent_state("speaking")
                    first = False
                await self._send(protocol.chat_delta(exchange_id, chunk))
            return True
        except Exception as exc:  # noqa: BLE001 — degrade to protocol error
            logger.warning("executor stream failed for %s: %s", exchange_id, exc)
            code = "internal" if self._simulated else "executor_unavailable"
            # Per spec, an error carrying `id` terminates the exchange
            # (client treats it as chat.complete).
            await self._send(
                protocol.error(code, f"reply generation failed: {exc}", exchange_id)
            )
            return False
        finally:
            cancel_waiter.cancel()
            # Always finalize the generator: abandoning it suspended would
            # leave the real Executor's ADK invocation dangling un-closed.
            try:
                await stream.aclose()
            except Exception:  # noqa: BLE001 — already broken/cancelled
                pass

    @staticmethod
    async def _next_chunk(
        stream: AsyncIterator[str], cancel_waiter: "asyncio.Future"
    ) -> Optional[str]:
        """Next chunk from ``stream``, racing the cancel event and a watchdog.

        Returns ``None`` when the stream ends or cancel fires; raises
        ``TimeoutError`` when the responder stays silent past the watchdog.
        """
        timeout = _stall_timeout_s()
        step: asyncio.Future = asyncio.ensure_future(stream.__anext__())
        try:
            done, _ = await asyncio.wait(
                {step, cancel_waiter},
                timeout=timeout,
                return_when=asyncio.FIRST_COMPLETED,
            )
        except asyncio.CancelledError:
            step.cancel()
            raise
        if step in done:
            try:
                return step.result()
            except StopAsyncIteration:
                return None
        # Cancelled by the user, or the responder stalled: retire the
        # in-flight __anext__. This CancelledError is what actually wakes a
        # generator parked inside a hung LLM await.
        step.cancel()
        await asyncio.wait({step})
        if not step.cancelled():
            step.exception()  # retrieve, so asyncio never logs it as unretrieved
        if cancel_waiter.done():
            return None
        raise TimeoutError(f"the Executor produced no output for {timeout:.0f}s")


def create_app() -> "FastAPI":
    """Build the FastAPI application (raises with install hint if missing)."""
    if not FASTAPI_AVAILABLE:
        raise RuntimeError(INSTALL_HINT)

    fastapi_app = FastAPI(title="DANTE UI bridge", docs_url=None, redoc_url=None)

    @fastapi_app.get("/healthz")
    async def healthz() -> dict:
        return {"ok": True}

    @fastapi_app.get("/health")
    async def health() -> dict:  # alias — some tooling probes /health
        return {"ok": True}

    @fastapi_app.websocket("/ws")
    async def ws_endpoint(ws: WebSocket) -> None:
        await Connection(ws).run()

    return fastapi_app


if FASTAPI_AVAILABLE:
    app = create_app()
else:
    async def app(scope, receive, send):  # type: ignore[misc]  # minimal ASGI stub
        """Placeholder ASGI callable so `uvicorn triforce.server.app:app`
        fails with an actionable message instead of an import error."""
        raise RuntimeError(INSTALL_HINT)
