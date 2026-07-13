# @dante/desktop

Electron shell for the DANTE web UI (`ui/web`). It is a thin, secure wrapper:
`contextIsolation: true`, `nodeIntegration: false`, `sandbox: true`, and a
preload that exposes nothing yet (placeholder for future IPC such as native
`dream.notify` notifications).

## Prerequisites

The shell renders `ui/web` — it must be either **running** (dev) or **built**
(start) first:

```sh
# dev: Vite dev server on http://127.0.0.1:5173 (strictPort)
cd ui/web && npm install && npm run dev

# start: build once to ui/web/dist
cd ui/web && npm install && npm run build
```

## Run

```sh
cd ui/desktop
npm install

npm run dev    # loads http://127.0.0.1:5173 (Vite must be running)
npm run start  # loads ../web/dist/index.html (web must be built)
npm run smoke  # boots headless-ish, prints "ready", exits (CI check)
```

`npm run dev` passes `--dev`; setting `ELECTRON_DEV=1` works too.

## Networking

The renderer opens its WebSocket **directly** to the Executor server at
`ws://127.0.0.1:8420/ws` (see `ui/ARCHITECTURE.md`). No proxying, no IPC —
the desktop shell adds nothing to the transport path. If the server is down,
the web app's demo mode applies exactly as in the browser.
