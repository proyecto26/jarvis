# DANTE UI

Web + desktop UI for DANTE. The UI talks only to the Executor via the
WebSocket server in `triforce/server` (`ws://127.0.0.1:8420/ws`).

Read [`ARCHITECTURE.md`](./ARCHITECTURE.md) first — it defines the transport
decision, the wire protocol (mirrored in `web/src/protocol.ts`), and the
canonical ports.

## Quickstart

### Web (browser)

```sh
cd ui/web
npm install
npm run dev        # http://127.0.0.1:5173
```

Works without the server: the UI falls back to demo mode (local canned
responder) and auto-reconnects when the server appears.

Production build:

```sh
npm run build      # outputs ui/web/dist/
npm run preview    # serve the build at http://127.0.0.1:4173
```

### Desktop (Electron)

```sh
cd ui/desktop
npm install
npm run dev        # loads http://127.0.0.1:5173 — start the web dev server first
```

Prod packaging loads `../web/dist/index.html`; run the web build first.
(Electron implementation is scaffolded but not written yet.)

### Server

```sh
pip install fastapi "uvicorn[standard]" websockets   # NOT in pyproject.toml — see triforce/server/README.md
python -m triforce.server                            # binds 127.0.0.1:8420
```

If google-adk/LLM is unavailable the server still runs, answering via a
simulated Executor (`server.hello` carries `simulated: true`).
