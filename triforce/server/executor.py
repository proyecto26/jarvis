"""Executor wiring for the UI bridge — real ADK Executor with demo fallback.

``build_responder()`` returns a per-connection responder object exposing:

    simulated: bool
    async def stream(text: str, cancel: asyncio.Event) -> AsyncIterator[str]

The real path drives ``triforce.agents.executor.agent.executor_agent`` through
an ADK ``InMemoryRunner``. If google-adk is not importable, no Gemini
credentials are configured, or ``DANTE_FORCE_SIMULATED`` is truthy, the
``DemoResponder`` takes over. The two paths are protocol-indistinguishable:
both stream text chunks and let the connection layer emit ``agent.state``
transitions and ``chat.delta``/``chat.complete`` frames.

Only stdlib is imported at module level — google-adk imports are deferred so
``triforce.server`` imports on machines without it.
"""

from __future__ import annotations

import asyncio
import logging
import os
import random
import re
import uuid
from typing import AsyncIterator, Optional, Tuple

logger = logging.getLogger(__name__)

_TRUTHY = ("1", "true", "yes", "on")


def _time_scale() -> float:
    """Multiplier for all demo delays. Selftest shrinks this to run fast."""
    try:
        return max(0.0, float(os.getenv("DANTE_DEMO_TIME_SCALE", "1.0")))
    except ValueError:
        return 1.0


def _force_simulated() -> bool:
    return os.getenv("DANTE_FORCE_SIMULATED", "").strip().lower() in _TRUTHY


def _have_gemini_credentials() -> bool:
    if os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY"):
        return True
    if os.getenv("GOOGLE_GENAI_USE_VERTEXAI", "").strip().lower() in _TRUTHY:
        return True
    return False


def executor_available() -> bool:
    """True when the real Executor path can plausibly serve replies."""
    if _force_simulated():
        return False
    try:
        import google.adk  # noqa: F401  — presence check only
    except Exception:  # noqa: BLE001 — any import failure means unavailable
        return False
    return _have_gemini_credentials()


# ---------------------------------------------------------------------------
# Demo responder — THE acceptance path
# ---------------------------------------------------------------------------

_GREETING_RE = re.compile(
    r"^\s*(hi|hey|hello|hola|yo|good\s+(morning|afternoon|evening))\b", re.IGNORECASE
)

_OPENERS = [
    "Right —",
    "Understood.",
    "Okay,",
    "Got it.",
    "Alright,",
    "Noted.",
]

_GREETINGS = [
    "Hello! I'm DANTE's Executor — the one agent here that's allowed to talk to you.",
    "Hey there. DANTE Executor online and listening.",
    "Hi! You've reached the Executor, the outward-facing third of the trinity.",
]

_QUESTION_BODIES = [
    "that's a good question. Normally I'd route it through the Judge before answering, "
    "but my language model is offline right now, so this is the simulated Executor speaking.",
    "I'd love to give you a real answer — at the moment the LLM backend isn't connected, "
    "so I'm streaming a stand-in reply through the exact same pipeline the real one uses.",
    "the honest answer is that my reasoning engine is unplugged on this machine. "
    "Everything else — streaming, state transitions, the protocol — is fully live though.",
]

_STATEMENT_BODIES = [
    "I've taken that in. The Dreamer and the Judge would usually weigh in next; "
    "for now I'm running in simulated mode, so consider this a faithful dress rehearsal.",
    "message received loud and clear. My LLM backend is unavailable at the moment, "
    "so I'm answering from the simulated Executor — same wire protocol, canned brain.",
    "I've logged that. When google-adk and a Gemini key are configured, this exact "
    "conversation flows through the real Executor agent instead of me.",
]

_CLOSERS = [
    "Ask me anything else — I'll keep the stream warm.",
    "The full trinity will be with you once the model comes online.",
    "Everything you see here maps one-to-one onto the real path.",
    "Try the cancel button mid-reply; I honor that too.",
]


def _compose_demo_reply(user_text: str, rng: random.Random) -> str:
    snippet = user_text.strip().replace("\n", " ")
    if len(snippet) > 60:
        snippet = snippet[:57] + "..."

    if _GREETING_RE.match(user_text):
        parts = [rng.choice(_GREETINGS), rng.choice(_CLOSERS)]
    elif user_text.rstrip().endswith("?"):
        parts = [
            rng.choice(_OPENERS),
            f'you asked "{snippet}" —',
            rng.choice(_QUESTION_BODIES),
            rng.choice(_CLOSERS),
        ]
    else:
        parts = [
            rng.choice(_OPENERS),
            rng.choice(_STATEMENT_BODIES),
            rng.choice(_CLOSERS),
        ]
    return " ".join(parts)


class DemoResponder:
    """Streams a canned-but-varied reply token by token with realistic delays.

    Protocol-wise indistinguishable from the real Executor: an initial
    "thinking" pause (1–2 s), then word-sized chunks every 20–80 ms.
    All delays scale with ``DANTE_DEMO_TIME_SCALE``.
    """

    simulated = True

    def __init__(self) -> None:
        self._rng = random.Random()

    async def stream(self, text: str, cancel: asyncio.Event) -> AsyncIterator[str]:
        scale = _time_scale()
        # Thinking pause before the first token (1–2 s at scale 1.0).
        await asyncio.sleep(self._rng.uniform(1.0, 2.0) * scale)
        if cancel.is_set():
            return

        reply = _compose_demo_reply(text, self._rng)
        # Whitespace-preserving word chunks, e.g. "Hello! " "I'm " ...
        for chunk in re.findall(r"\S+\s*", reply):
            if cancel.is_set():
                return
            yield chunk
            await asyncio.sleep(self._rng.uniform(0.02, 0.08) * scale)


# ---------------------------------------------------------------------------
# Real Executor responder (google-adk)
# ---------------------------------------------------------------------------


class RealExecutorResponder:
    """Drives the real Executor agent through an ADK InMemoryRunner.

    One instance per WebSocket connection: the ADK session (conversation
    context) lives exactly as long as the connection, matching the
    stateless-per-connection reconnect semantics.
    """

    simulated = False

    _USER_ID = "dante-ui"
    _APP_NAME = "dante-ui"

    def __init__(self) -> None:
        # Deferred imports: raise here (caught by build_responder) rather
        # than at module import time.
        from google.adk.runners import InMemoryRunner

        from triforce.agents.executor.agent import executor_agent

        self._runner = InMemoryRunner(agent=executor_agent, app_name=self._APP_NAME)
        self._session_id: Optional[str] = None
        # ADK sessions are strictly sequential conversations: overlapping
        # run_async calls on one session interleave history appends in
        # InMemorySessionService (no lock there) and corrupt the context the
        # next turn is built from. Serialize every invocation on this
        # connection's session — the connection layer also serializes
        # exchanges, but the invariant belongs to the session owner.
        self._invocation_lock = asyncio.Lock()

    async def _ensure_session(self) -> str:
        if self._session_id is None:
            session = await self._runner.session_service.create_session(
                app_name=self._APP_NAME,
                user_id=self._USER_ID,
                session_id=str(uuid.uuid4()),
            )
            self._session_id = session.id
        return self._session_id

    def _run_config(self):
        """Prefer SSE token streaming when this ADK version supports it."""
        try:
            from google.adk.agents.run_config import RunConfig, StreamingMode

            return RunConfig(streaming_mode=StreamingMode.SSE)
        except Exception:  # noqa: BLE001 — non-streaming still works
            return None

    async def stream(self, text: str, cancel: asyncio.Event) -> AsyncIterator[str]:
        from google.genai import types

        # The lock spans the whole invocation, including yields. The
        # connection layer guarantees the generator is always finalized
        # (aclose) so the lock is released even on cancel/abandonment.
        async with self._invocation_lock:
            session_id = await self._ensure_session()
            content = types.Content(role="user", parts=[types.Part(text=text)])

            kwargs = {}
            run_config = self._run_config()
            if run_config is not None:
                kwargs["run_config"] = run_config

            streamed_partial = False
            async for event in self._runner.run_async(
                user_id=self._USER_ID,
                session_id=session_id,
                new_message=content,
                **kwargs,
            ):
                if cancel.is_set():
                    return
                event_text = self._event_text(event)
                if not event_text:
                    continue
                if getattr(event, "partial", False):
                    streamed_partial = True
                    yield event_text
                elif not streamed_partial:
                    # Non-streaming fallback: whole reply in the final event.
                    yield event_text

    @staticmethod
    def _event_text(event) -> str:
        content = getattr(event, "content", None)
        parts = getattr(content, "parts", None) or []
        return "".join(p.text for p in parts if getattr(p, "text", None))


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def build_responder() -> Tuple[object, bool]:
    """Return ``(responder, simulated)`` for one connection.

    Tries the real Executor first (when available); ANY failure falls back
    to the DemoResponder — the server must always be able to answer.
    """
    if executor_available():
        try:
            responder = RealExecutorResponder()
            logger.info("UI bridge: real Executor path active")
            return responder, False
        except Exception as exc:  # noqa: BLE001 — degrade, never crash
            logger.warning("Real Executor unavailable (%s); using DemoResponder", exc)
    else:
        logger.info("UI bridge: simulated Executor (demo) path active")
    return DemoResponder(), True
