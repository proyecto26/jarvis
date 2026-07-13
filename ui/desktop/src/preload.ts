/**
 * DANTE desktop preload — placeholder.
 *
 * Runs with contextIsolation on. Intentionally exposes NOTHING to the
 * renderer yet: the web app needs no Node/Electron APIs — its only
 * transport is a plain WebSocket to ws://127.0.0.1:8420/ws.
 *
 * Future IPC (e.g. native notifications for dream.notify) goes through
 * contextBridge.exposeInMainWorld here — never by enabling nodeIntegration.
 */
export {};
