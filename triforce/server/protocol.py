"""DANTE UI wire protocol v1 — Python mirror of ui/web/src/protocol.ts.

Pure stdlib: no fastapi/adk imports here, so this module always imports.
The contract lives in ui/ARCHITECTURE.md §2; change that first.

Receiver rules (both directions):
  - Unknown ``type``            -> log + drop (no reply).
  - Unknown fields on known types -> ignored (forward compatibility).
  - ``v`` > PROTOCOL_VERSION     -> log + drop.
  - Malformed JSON / bad shape   -> ``error`` with code ``bad_message``.
"""

from __future__ import annotations

import json
from typing import Any, Optional

PROTOCOL_VERSION = 1

AGENT_STATES = ("idle", "listening", "thinking", "speaking")
SYSTEM_MODES = ("awake", "sleep", "reflective")
ERROR_CODES = ("bad_message", "executor_unavailable", "internal")

CLIENT_TYPES = ("client.hello", "chat.send", "chat.cancel", "ping")

# ---------------------------------------------------------------------------
# Server -> Client message builders
# ---------------------------------------------------------------------------


def server_hello(simulated: bool) -> dict:
    return {
        "v": PROTOCOL_VERSION,
        "type": "server.hello",
        "protocol": PROTOCOL_VERSION,
        "simulated": bool(simulated),
    }


def chat_delta(exchange_id: str, text: str) -> dict:
    return {"v": PROTOCOL_VERSION, "type": "chat.delta", "id": exchange_id, "text": text}


def chat_complete(exchange_id: str) -> dict:
    return {"v": PROTOCOL_VERSION, "type": "chat.complete", "id": exchange_id}


def agent_state(state: str) -> dict:
    assert state in AGENT_STATES, state
    return {"v": PROTOCOL_VERSION, "type": "agent.state", "state": state}


def system_mode(mode: str) -> dict:
    assert mode in SYSTEM_MODES, mode
    return {"v": PROTOCOL_VERSION, "type": "system.mode", "mode": mode}


def error(code: str, message: str, exchange_id: Optional[str] = None) -> dict:
    assert code in ERROR_CODES, code
    msg: dict[str, Any] = {
        "v": PROTOCOL_VERSION,
        "type": "error",
        "code": code,
        "message": message,
    }
    if exchange_id is not None:
        msg["id"] = exchange_id
    return msg


def pong() -> dict:
    return {"v": PROTOCOL_VERSION, "type": "pong"}


# ---------------------------------------------------------------------------
# Client -> Server parsing / validation
# ---------------------------------------------------------------------------


class ParseResult:
    """Outcome of parsing one inbound frame.

    Exactly one of the three shapes:
      - ``message`` set        -> valid, dispatch it.
      - ``reply_error`` set    -> send that ``error`` message back.
      - ``drop_reason`` set    -> log and silently drop (unknown type / higher v).
    """

    __slots__ = ("message", "reply_error", "drop_reason")

    def __init__(
        self,
        message: Optional[dict] = None,
        reply_error: Optional[dict] = None,
        drop_reason: Optional[str] = None,
    ):
        self.message = message
        self.reply_error = reply_error
        self.drop_reason = drop_reason


_REQUIRED_STR_FIELDS = {
    "client.hello": ("client",),
    "chat.send": ("id", "text"),
    "chat.cancel": ("id",),
    "ping": (),
}


def parse_client_frame(raw: str) -> ParseResult:
    """Validate one raw text frame against protocol v1."""
    try:
        msg = json.loads(raw)
    except (ValueError, TypeError):
        return ParseResult(reply_error=error("bad_message", "frame is not valid JSON"))

    if not isinstance(msg, dict):
        return ParseResult(reply_error=error("bad_message", "frame is not a JSON object"))

    v = msg.get("v")
    mtype = msg.get("type")

    if not isinstance(v, int) or not isinstance(mtype, str):
        return ParseResult(
            reply_error=error("bad_message", "missing or invalid envelope fields 'v'/'type'")
        )

    if v > PROTOCOL_VERSION:
        return ParseResult(drop_reason=f"message v={v} > supported {PROTOCOL_VERSION}")

    if mtype not in _REQUIRED_STR_FIELDS:
        return ParseResult(drop_reason=f"unknown message type {mtype!r}")

    for field in _REQUIRED_STR_FIELDS[mtype]:
        value = msg.get(field)
        if not isinstance(value, str) or not value:
            exchange_id = msg.get("id") if isinstance(msg.get("id"), str) else None
            return ParseResult(
                reply_error=error(
                    "bad_message",
                    f"{mtype} requires string field {field!r}",
                    exchange_id,
                )
            )

    return ParseResult(message=msg)
