# triforce/server — DANTE UI WebSocket server

FastAPI server exposing the Executor to the UI over a single WebSocket at
`ws://127.0.0.1:8420/ws` (health: `GET http://127.0.0.1:8420/healthz`,
alias `/health`). The wire protocol is defined in
[`ui/ARCHITECTURE.md`](../../ui/ARCHITECTURE.md) §2 and mirrored in
`ui/web/src/protocol.ts` (client) and `triforce/server/protocol.py` (server).

## Install (deliberately NOT in pyproject.toml)

Server dependencies are installed manually so the core `triforce` package
stays dependency-light:

```sh
pip install fastapi "uvicorn[standard]" websockets
# optional, for the selftest's WebSocket TestClient:
pip install httpx
```

## Run

```sh
uvicorn triforce.server.app:app --host 127.0.0.1 --port 8420
# or equivalently:
python -m triforce.server   # binds 127.0.0.1:8420 (loopback only)
```

## Selftest

```sh
python -m triforce.server.selftest
```

Runs protocol smoke assertions (handshake, chat streaming, cancel, malformed
frames, disconnect mid-stream, sequential connections) against the simulated
Executor via fastapi's TestClient; exits 0 with a skip message if fastapi or
httpx is missing. The import-guard check (module imports without fastapi)
always runs.

## Protocol summary (v1)

Every JSON frame carries `v: 1` and `type`. Unknown types, unknown fields,
and frames with `v` above 1 are logged and dropped; malformed frames get an
`error` with code `bad_message`.

Client → server: `client.hello {client}`, `chat.send {id, text}`,
`chat.cancel {id}`, `ping`.

Server → client, per connection:

1. `server.hello {protocol: 1, simulated}` — `simulated: true` means the
   demo responder is answering (see below).
2. `agent.state {state}` and `system.mode {mode}` snapshots, then again on
   every change.
3. Per `chat.send`: `agent.state` walks `listening → thinking → speaking`,
   `chat.delta {id, text}` streams the reply, `chat.complete {id}` ends it
   (also after `chat.cancel`, possibly after a final partial delta), then
   `agent.state: idle` when no exchange is in flight.
4. `error {code, message, id?}` — `bad_message`, `executor_unavailable`,
   `internal`; when `id` is present that exchange is over (treat as
   `chat.complete`).
5. `pong` answers `ping`.

Connections are stateless: no resume or replay after reconnect.

## Real Executor vs simulated

At connection time the server picks a responder (`triforce/server/executor.py`):

- **Real path** — activates when `google-adk` is importable AND Gemini
  credentials are configured (`GOOGLE_API_KEY` or `GEMINI_API_KEY` env/.env,
  or `GOOGLE_GENAI_USE_VERTEXAI=true`). The connection gets its own ADK
  `InMemoryRunner` session driving `triforce.agents.executor.agent
  .executor_agent`, with SSE token streaming when the ADK version supports it.
  `server.hello` carries `simulated: false`.
- **Simulated path** — anything else (or `DANTE_FORCE_SIMULATED=1`): the
  `DemoResponder` streams a canned-but-varied reply token by token with
  realistic delays and identical protocol behavior. `server.hello` carries
  `simulated: true`. `DANTE_DEMO_TIME_SCALE` (float, default `1.0`) scales
  the demo delays — the selftest sets `0.02`.

If a real-path reply fails mid-exchange, the client receives
`error {code: "executor_unavailable", id}` for that exchange; the server
keeps serving.

## Invariants

- **Guarded imports:** `triforce.server` imports cleanly without fastapi
  installed; `uvicorn triforce.server.app:app` then fails with an actionable
  install hint instead of an ImportError.
- **Simulated Executor:** the protocol is always served, LLM or not.
- **Stateless per connection:** no session resume or replay. After
  `server.hello`, push current `agent.state` and `system.mode` snapshots.
- Bind `127.0.0.1` only — never `0.0.0.0`.
