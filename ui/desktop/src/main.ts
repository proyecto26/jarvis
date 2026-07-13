/**
 * DANTE desktop shell — Electron main process.
 *
 * Wraps the ui/web app. Security posture: contextIsolation ON,
 * nodeIntegration OFF, sandbox ON. The renderer talks WebSocket
 * directly to ws://127.0.0.1:8420/ws (see ui/ARCHITECTURE.md) —
 * no proxying or IPC is needed for the protocol.
 *
 * Modes:
 *   dev   — ELECTRON_DEV=1 or --dev flag: loads http://127.0.0.1:5173 (Vite dev server)
 *   prod  — default: loads ../web/dist/index.html (built web app)
 *   smoke — --smoke flag: boots, logs "ready", and quits (CI/verification)
 */
import { app, BrowserWindow } from 'electron';
import * as path from 'node:path';

const isDev = process.env.ELECTRON_DEV === '1' || process.argv.includes('--dev');
const isSmoke = process.argv.includes('--smoke');

const DEV_URL = 'http://127.0.0.1:5173';
const PROD_INDEX = path.join(__dirname, '..', '..', 'web', 'dist', 'index.html');

/**
 * Navigation hardening (Electron security checklist: "limit navigation",
 * "limit window creation"). The shell renders exactly one app — the DANTE
 * UI — so window.open is denied outright and renderer-initiated navigation
 * is confined to the app's own origin: the Vite dev server in dev, the
 * built file: bundle in prod. Registered via web-contents-created so every
 * WebContents this app ever creates is covered, not just the first window.
 */
function isAllowedNavigation(target: string): boolean {
  try {
    const url = new URL(target);
    return isDev ? url.origin === new URL(DEV_URL).origin : url.protocol === 'file:';
  } catch {
    return false; // unparseable URLs never navigate
  }
}

app.on('web-contents-created', (_event, contents) => {
  contents.setWindowOpenHandler(() => ({ action: 'deny' }));
  contents.on('will-navigate', (event, url) => {
    if (!isAllowedNavigation(url)) event.preventDefault();
  });
  contents.on('will-frame-navigate', (event) => {
    if (!isAllowedNavigation(event.url)) event.preventDefault();
  });
});

function createWindow(): BrowserWindow {
  const win = new BrowserWindow({
    width: 1280,
    height: 800,
    minWidth: 640,
    minHeight: 480,
    title: 'DANTE',
    backgroundColor: '#05060a', // matches ui/web dark background
    autoHideMenuBar: true,
    show: false, // avoid white flash; shown on ready-to-show
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
      preload: path.join(__dirname, 'preload.js'),
    },
  });

  win.once('ready-to-show', () => {
    if (!isSmoke) win.show();
  });

  // Keep the title fixed regardless of document.title changes.
  win.on('page-title-updated', (event) => {
    event.preventDefault();
    win.setTitle('DANTE');
  });

  if (isDev) {
    void win.loadURL(DEV_URL);
  } else {
    void win.loadFile(PROD_INDEX);
  }

  return win;
}

app.whenReady().then(() => {
  const win = createWindow();

  if (isSmoke) {
    // Smoke mode: confirm the window boots without exceptions, then exit.
    // did-fail-load is fine in smoke (dev server/dist may be absent) —
    // we only verify the Electron shell itself comes up cleanly.
    let done = false;
    const finish = (ok: boolean) => {
      if (done) return;
      done = true;
      console.log(ok ? 'ready' : 'smoke: window failed to initialize');
      // Give stdout a tick to flush on Windows before quitting.
      setTimeout(() => app.exit(ok ? 0 : 1), 50);
    };
    win.webContents.once('did-finish-load', () => finish(true));
    win.webContents.once('did-fail-load', () => finish(true));
    // Hard timeout so smoke can never hang.
    setTimeout(() => finish(false), 15000);
  }

  app.on('activate', () => {
    // macOS convention; harmless elsewhere.
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('window-all-closed', () => {
  // Single-window utility app: quit on all platforms, including macOS.
  app.quit();
});
