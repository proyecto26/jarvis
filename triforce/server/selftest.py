"""Smoke selftest for the DANTE UI bridge.

Run:  python -m triforce.server.selftest

Uses fastapi's TestClient when available; exits 0 with a skip message
otherwise. Lives here (not in tests/) because tests/ is owned by another
workflow. Forces the simulated Executor — the demo path is the acceptance
path — and shrinks demo delays so the whole suite runs in seconds.
"""

from __future__ import annotations

import os
import subprocess
import sys
import uuid
from pathlib import Path

# Must be set BEFORE the app/executor modules are imported anywhere below.
os.environ["DANTE_FORCE_SIMULATED"] = "1"
os.environ["DANTE_DEMO_TIME_SCALE"] = "0.02"

REPO_ROOT = Path(__file__).resolve().parents[2]

_failures: list[str] = []


def check(condition: bool, label: str) -> None:
    status = "PASS" if condition else "FAIL"
    print(f"  [{status}] {label}")
    if not condition:
        _failures.append(label)


def recv_until(ws, mtype: str, limit: int = 400) -> tuple[list[dict], dict]:
    """Receive frames until one of type ``mtype``; return (before, match)."""
    seen: list[dict] = []
    for _ in range(limit):
        msg = ws.receive_json()
        if msg.get("type") == mtype:
            return seen, msg
        seen.append(msg)
    raise AssertionError(f"never received {mtype!r}; got {len(seen)} other frames")


def expect_handshake(ws, simulated: bool = True) -> None:
    hello = ws.receive_json()
    check(hello.get("type") == "server.hello", "first frame is server.hello")
    check(hello.get("v") == 1 and hello.get("protocol") == 1, "server.hello v/protocol == 1")
    check(hello.get("simulated") is simulated, f"server.hello simulated is {simulated}")
    state = ws.receive_json()
    check(
        state.get("type") == "agent.state" and state.get("state") == "idle",
        "agent.state snapshot (idle) follows server.hello",
    )
    mode = ws.receive_json()
    check(
        mode.get("type") == "system.mode" and mode.get("mode") == "awake",
        "system.mode snapshot (awake) follows agent.state",
    )


def test_import_without_fastapi() -> None:
    print("import guard: module imports with fastapi blocked")
    code = (
        "import sys\n"
        "from importlib.abc import MetaPathFinder\n"
        "class Blocker(MetaPathFinder):\n"
        "    def find_spec(self, fullname, path=None, target=None):\n"
        "        if fullname == 'fastapi' or fullname.startswith('fastapi.'):\n"
        "            raise ImportError('fastapi blocked for selftest')\n"
        "sys.meta_path.insert(0, Blocker())\n"
        "import triforce.server.app as m\n"
        "assert m.FASTAPI_AVAILABLE is False, 'guard flag should be False'\n"
        "assert callable(m.app), 'stub ASGI app should be callable'\n"
        "assert 'pip install fastapi' in m.INSTALL_HINT\n"
        "print('guarded-import OK')\n"
    )
    proc = subprocess.run(
        [sys.executable, "-c", code], cwd=str(REPO_ROOT), capture_output=True, text=True
    )
    check(
        proc.returncode == 0 and "guarded-import OK" in proc.stdout,
        "triforce.server.app imports cleanly without fastapi (subprocess)",
    )
    if proc.returncode != 0:
        print(proc.stdout)
        print(proc.stderr)


def test_health(client) -> None:
    print("health endpoints")
    for path in ("/healthz", "/health"):
        resp = client.get(path)
        check(
            resp.status_code == 200 and resp.json() == {"ok": True},
            f"GET {path} -> 200 {{'ok': true}}",
        )


def test_handshake_and_ping(client) -> None:
    print("handshake, client.hello, ping/pong")
    with client.websocket_connect("/ws") as ws:
        expect_handshake(ws)
        ws.send_json({"v": 1, "type": "client.hello", "client": "web"})
        ws.send_json({"v": 1, "type": "ping"})
        msg = ws.receive_json()
        check(msg.get("type") == "pong" and msg.get("v") == 1, "ping answered with pong")


def test_chat_roundtrip(client) -> None:
    print("chat.send -> states + deltas + chat.complete -> idle")
    with client.websocket_connect("/ws") as ws:
        expect_handshake(ws)
        cid = str(uuid.uuid4())
        ws.send_json({"v": 1, "type": "chat.send", "id": cid, "text": "Hello DANTE, are you there?"})
        before, complete = recv_until(ws, "chat.complete")

        states = [m["state"] for m in before if m.get("type") == "agent.state"]
        deltas = [m for m in before if m.get("type") == "chat.delta"]
        others = [m for m in before if m.get("type") not in ("agent.state", "chat.delta")]

        check(states == ["listening", "thinking", "speaking"],
              f"agent.state order listening->thinking->speaking (got {states})")
        check(len(deltas) >= 5, f"streamed multiple deltas ({len(deltas)})")
        check(all(m.get("id") == cid for m in deltas), "every delta carries the exchange id")
        check(all(isinstance(m.get("text"), str) and m["text"] for m in deltas),
              "every delta has non-empty text")
        check(not others, f"no unexpected frame types during stream ({others})")
        check(complete.get("id") == cid, "chat.complete echoes the exchange id")

        idle = ws.receive_json()
        check(idle.get("type") == "agent.state" and idle.get("state") == "idle",
              "agent.state idle after chat.complete")

        reply = "".join(m["text"] for m in deltas)
        check(len(reply) > 40, f"assembled reply is substantial ({len(reply)} chars)")


def test_chat_cancel(client) -> None:
    print("chat.cancel mid-stream")
    with client.websocket_connect("/ws") as ws:
        expect_handshake(ws)
        cid = str(uuid.uuid4())
        ws.send_json({"v": 1, "type": "chat.send", "id": cid, "text": "Tell me a very long story"})
        # Wait for the first delta so we cancel mid-stream.
        _, first_delta = recv_until(ws, "chat.delta")
        check(first_delta.get("id") == cid, "streaming started before cancel")
        ws.send_json({"v": 1, "type": "chat.cancel", "id": cid})
        before, complete = recv_until(ws, "chat.complete")
        check(complete.get("id") == cid, "chat.complete arrives after cancel")
        stray = [m for m in before if m.get("type") not in ("chat.delta", "agent.state")]
        check(not stray, "only deltas/states between cancel and complete")
        idle = ws.receive_json()
        check(idle.get("type") == "agent.state" and idle.get("state") == "idle",
              "agent.state idle after cancelled exchange")
        # Cancel for a finished/unknown id is silently dropped.
        ws.send_json({"v": 1, "type": "chat.cancel", "id": cid})
        ws.send_json({"v": 1, "type": "ping"})
        msg = ws.receive_json()
        check(msg.get("type") == "pong", "cancel of finished id is dropped (pong next)")


def test_bad_and_unknown_messages(client) -> None:
    print("malformed / unknown / future-version frames")
    with client.websocket_connect("/ws") as ws:
        expect_handshake(ws)

        ws.send_text("this is not json {")
        msg = ws.receive_json()
        check(msg.get("type") == "error" and msg.get("code") == "bad_message",
              "invalid JSON -> error bad_message")

        ws.send_json({"v": 1, "type": "chat.send", "text": "missing id"})
        msg = ws.receive_json()
        check(msg.get("type") == "error" and msg.get("code") == "bad_message",
              "chat.send without id -> error bad_message")

        ws.send_json({"v": 1, "type": "totally.unknown", "x": 1})
        ws.send_json({"v": 99, "type": "ping"})
        ws.send_json({"v": 1, "type": "ping"})
        msg = ws.receive_json()
        check(msg.get("type") == "pong",
              "unknown type and v=99 frames dropped silently (pong next)")


def test_disconnect_mid_stream_and_sequential_connections(client) -> None:
    print("disconnect mid-stream, then fresh connections keep working")
    with client.websocket_connect("/ws") as ws:
        expect_handshake(ws)
        cid = str(uuid.uuid4())
        ws.send_json({"v": 1, "type": "chat.send", "id": cid, "text": "stream then vanish"})
        recv_until(ws, "chat.delta")  # mid-stream...
        # ...and drop the connection without waiting for chat.complete.
    check(True, "client disconnected mid-stream without server error")

    for i in (1, 2):
        with client.websocket_connect("/ws") as ws:
            expect_handshake(ws)
            ws.send_json({"v": 1, "type": "ping"})
            msg = ws.receive_json()
            check(msg.get("type") == "pong", f"sequential connection #{i} serves pong")


def main() -> int:
    print("DANTE UI bridge selftest (simulated Executor, scaled delays)")

    test_import_without_fastapi()

    try:
        from fastapi.testclient import TestClient
    except ImportError:
        print(
            "SKIP: fastapi (or its TestClient dependency httpx) is not installed.\n"
            '      pip install fastapi "uvicorn[standard]" websockets httpx\n'
            "Import-guard check ran above; exiting 0."
        )
        return 1 if _failures else 0

    from triforce.server.app import app

    with TestClient(app) as client:
        test_health(client)
        test_handshake_and_ping(client)
        test_chat_roundtrip(client)
        test_chat_cancel(client)
        test_bad_and_unknown_messages(client)
        test_disconnect_mid_stream_and_sequential_connections(client)

    if _failures:
        print(f"\nFAILED: {len(_failures)} assertion(s):")
        for f in _failures:
            print(f"  - {f}")
        return 1
    print("\nAll selftest assertions passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
