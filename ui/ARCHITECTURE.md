# DANTE UI Architecture

Status: **decided** (2026-07-13). This document is load-bearing: the protocol
section is the contract between `ui/web`, `ui/desktop`, and `triforce/server`.
Downstream implementers must not change message shapes without bumping the
protocol version (see [Versioning](#versioning--reconnect-semantics)).

The UI talks to **the Executor only** (via `triforce/server`). Dreamer and
Judge are never exposed directly; their activity surfaces as server-pushed
state events.

---

## 1. Transport validation: WebSocket vs SSE(+POST) vs polling

Requirements to satisfy:

| # | Requirement |
|---|-------------|
| R1 | Bidirectional chat (user sends text, assistant replies) |
| R2 | Token-streaming assistant replies (many small server→client frames) |
| R3 | Server-pushed avatar/agent state events: `idle/listening/thinking/speaking`, mode changes `Awake/Sleep/Reflective`, future dream notifications |
| R4 | Single local user, localhost only (no proxies, no CDNs, no load balancers) |
| R5 | Electron + browser targets |
| R6 | Python FastAPI backend |
| R7 | Future: Temporal workflows emit events at arbitrary times (dream reports, reflection summaries) — the server must push with no pending client request |

### Candidates

**Polling (short/long)**
- R2 fails in spirit: token streaming over polling means either high-latency batching or aggressive poll intervals (wasteful, jittery).
- R3/R7 degrade to "eventually noticed" — a dream notification should animate the brain the moment it happens, not up to `poll_interval` later.
- Only advantage is maximal proxy compatibility, which R4 makes irrelevant.
- **Rejected.**

**SSE + POST**
- SSE handles R2/R3 well (unidirectional server→client stream, auto-reconnect built into `EventSource`).
- But R1 requires a *second* channel: every user input is a separate `POST /chat`, so the "connection" is actually two half-channels that must be correlated by message id, with two failure modes to handle (stream drop vs POST failure) and two places to enforce ordering.
- `EventSource` cannot set headers and is text-only; fine today, a constraint later (binary audio frames for voice).
- FastAPI supports SSE fine, but there is no simplification payoff: we still write the POST endpoint, the id-correlation logic, and reconnect handling for the POST side.
- **Rejected as primary; retained as documented fallback** (see below).

**WebSocket**
- One connection satisfies R1+R2+R3+R7 natively: full-duplex, ordered, low per-message overhead (2–6 byte frame header vs HTTP headers per POST).
- R7 is the decisive strength: Temporal-driven events (a dream completing at 3am while the desktop app idles) are pushed on the already-open socket with zero extra machinery. Any request/response transport would need a standing subscription channel anyway — at which point you have reinvented half a WebSocket.
- R4 removes WS's classic weaknesses: no corporate proxy stripping `Upgrade`, no LB affinity problems, no scale-out fan-out concerns on `ws://127.0.0.1`.
- R5: `WebSocket` is native in every browser and in Electron's Chromium renderer — identical client code for both targets.
- R6: FastAPI/Starlette WebSocket support is first-class (`@app.websocket`), and `uvicorn[standard]` ships the `websockets` implementation.
- Cost: we own reconnect logic ourselves (unlike `EventSource`). That is ~30 lines of backoff code, specified below so every client implements it identically.

### Decision

**WebSocket, single connection, JSON text frames.** SSE would still need a
POST channel for input, doubling the surface for no benefit at localhost;
polling fails streaming and push outright. WebSocket's push model is also the
right substrate for future Temporal-driven events.

**Fallback pattern (documented, not implemented):** if a restrictive
proxy/environment ever breaks WS (e.g. remote access through a corporate
tunnel), the same envelope messages map 1:1 onto SSE + POST: server→client
messages become SSE `data:` events on `GET /events`, client→server messages
become `POST /msg` with the identical JSON body. Because both directions
already use a self-describing `type` field, no message redesign is needed —
only a transport adapter behind the client's `send()`/`onMessage()` interface.
Keep that interface transport-agnostic in `ui/web` so the swap stays cheap.

---

## 2. Protocol spec (v1)

### Endpoint

| Thing | Value |
|---|---|
| WebSocket URL | `ws://127.0.0.1:8420/ws` |
| Server bind | `127.0.0.1:8420` (loopback only — never `0.0.0.0`) |
| Frame format | UTF-8 JSON text frames, one message per frame |
| Health check | `GET http://127.0.0.1:8420/healthz` → `200 {"ok": true}` |

### Envelope

Every message in either direction is a JSON object with at minimum:

```json
{ "v": 1, "type": "<namespace.verb>", ... }
```

- `v` (number, required): protocol version. Currently `1`. Receivers MUST
  ignore messages with an unknown `v` greater than theirs after logging, and
  MUST ignore unknown fields within a known type (forward compatibility).
- `type` (string, required): message discriminator, `namespace.verb` style.
- Unknown `type` values MUST be ignored (log + drop), never treated as fatal.
- `id` correlates a chat exchange: the client mints it (UUID v4 string) on
  `chat.send`; the server echoes it on every related `chat.*` reply.

### Client → Server

| type | Fields | Meaning |
|---|---|---|
| `client.hello` | `v`, `type`, `client: 'web' \| 'desktop'` | First message after connect. Announces client kind and protocol version. |
| `chat.send` | `v`, `type`, `id: string`, `text: string` | User sends a chat message. `id` is a client-minted UUID v4. |
| `chat.cancel` | `v`, `type`, `id: string` | Ask the server to stop generating the reply for `id`. Server responds with `chat.complete` for that `id` (possibly after a final partial delta). |
| `ping` | `v`, `type` | Liveness probe. Server answers `pong`. Client sends every 20 s of socket idle. |

### Server → Client

| type | Fields | Meaning |
|---|---|---|
| `server.hello` | `v`, `type`, `protocol: number`, `simulated: boolean` | First message after connect. `simulated: true` means the real Executor (google-adk/LLM) is unavailable and replies come from the simulated Executor — the UI should show a subtle "demo mode" indicator. |
| `chat.delta` | `v`, `type`, `id: string`, `text: string` | One streamed token/chunk of the assistant reply for exchange `id`. Client appends in arrival order. |
| `chat.complete` | `v`, `type`, `id: string` | Reply for `id` is finished (normally or via cancel). No further `chat.delta` for this `id` will follow. |
| `agent.state` | `v`, `type`, `state: 'idle' \| 'listening' \| 'thinking' \| 'speaking'` | Avatar/brain animation state. Server pushes on every change, and pushes the current value right after `server.hello`. |
| `system.mode` | `v`, `type`, `mode: 'awake' \| 'sleep' \| 'reflective'` | DANTE system mode. Pushed on change and right after `server.hello`. |
| `dream.notify` | `v`, `type`, `title: string`, `body: string` | Future: Temporal-driven dream/reflection notification. Clients MAY ignore in v1; defined now so the envelope is stable. |
| `error` | `v`, `type`, `code: string`, `message: string`, `id?: string` | Recoverable error. `id` present when tied to a chat exchange (that exchange is then terminated — treat as `chat.complete`). Codes: `bad_message`, `executor_unavailable`, `internal`. |
| `pong` | `v`, `type` | Reply to `ping`. |

### Connection lifecycle

```
client                                  server
  |------------- WS connect ------------->|
  |-- client.hello ---------------------->|
  |<------------------------ server.hello-|
  |<------------------------- agent.state-|   (current state snapshot)
  |<------------------------- system.mode-|   (current mode snapshot)
  |-- chat.send {id:A} ------------------>|
  |<--------------------- agent.state:thinking
  |<---------------- chat.delta {id:A} x N|
  |<--------------------- agent.state:speaking (server's choice of timing)
  |<---------------------chat.complete{id:A}
  |<--------------------- agent.state:idle|
```

### Versioning & reconnect semantics

- **Versioning:** `v` is per-message. Additive changes (new optional fields,
  new `type` values) do NOT bump `v` — receivers ignore what they don't know.
  Breaking changes (renamed/removed fields, changed semantics) bump `v` and
  must be called out in this document.
- **Server is stateless per connection.** No session resume, no replay buffer.
  Chat history lives in the client (and in DANTE's own memory, which is not
  this protocol's concern). On a new connection the server only sends
  `server.hello` + current `agent.state` + current `system.mode`.
- **Client auto-reconnect:** on close/error, reconnect with exponential
  backoff: 500 ms, 1 s, 2 s, 4 s, 8 s, then every 8 s (±20% jitter), forever.
  Reset backoff after a connection survives 10 s. Any chat exchange that had
  no `chat.complete` when the socket dropped is marked *interrupted* in the
  UI (its `id` is dead — deltas are never replayed).
- **Demo mode (graceful degradation):** while disconnected, the web UI stays
  fully interactive — the brain renders, chat input works, and a local canned
  responder answers with a "server offline" persona. On reconnect the client
  switches back to live transport transparently. Demo mode is a client-side
  concern; `simulated: true` from the server is the *server-side* degradation
  (server up, LLM down) and is a distinct, milder indicator.

---

## 3. Stack decision

| Layer | Choice | Notes |
|---|---|---|
| `ui/web` | **Vite + TypeScript + Three.js** | 3D procedural brain — generated geometry only, **no external 3D model assets**. Vanilla TS (no React): one screen, one canvas, one chat pane; a framework earns nothing here. |
| `ui/desktop` | **Electron** | `contextIsolation: true`, `nodeIntegration: false`, preload script only if/when native features are needed. Loads the Vite dev server URL (`http://127.0.0.1:5173`) in dev and `../web/dist/index.html` in prod — the desktop app is a shell around the *same* web app, zero UI code duplication. |
| Server | **FastAPI + uvicorn** in `triforce/server` | Deps installed manually (`pip install fastapi "uvicorn[standard]" websockets` — see `triforce/server/README.md`), NOT added to `pyproject.toml`. Must import without fastapi installed (guarded imports) and serve a simulated Executor when google-adk/LLM is unavailable. |

**Why Three.js:** the centerpiece is a real 3D object — a procedural brain
with depth, orbiting camera, and lighting-driven state changes — and Three.js
is the most mature 3D scene graph on the web (perspective cameras, lights,
materials, custom shaders, particles), with a decade of examples and docs for
exactly this kind of shader-driven artistic scene.

### Directory layout

```
ui/
  ARCHITECTURE.md      ← this file
  README.md            ← quickstart
  web/                 ← Vite + TS + Three.js app (browser + Electron renderer)
    src/
      main.ts          ← entry point (placeholder for now)
      protocol.ts      ← TS types mirroring §2 EXACTLY — single source of truth for clients
  desktop/             ← Electron main process (implementation later)
triforce/server/       ← FastAPI WS server (implementation later)
```

### Ports & URLs (canonical)

| What | Value |
|---|---|
| WS endpoint | `ws://127.0.0.1:8420/ws` |
| Server HTTP (health) | `http://127.0.0.1:8420/healthz` |
| Vite dev server | `http://127.0.0.1:5173` |
| Vite preview | `http://127.0.0.1:4173` (vite default) |
| Electron dev target | `http://127.0.0.1:5173` |
| Electron prod target | `file://…/ui/web/dist/index.html` |
