/**
 * DANTE web UI entry point — wires the three pieces together:
 *  - Brain: full-screen Three.js procedural brain (brain.ts)
 *  - ChatPanel: right-side chat overlay (chat.ts)
 *  - DanteClient: WebSocket transport with auto-reconnect + demo mode
 *    fallback (transport.ts / demo.ts), per ui/ARCHITECTURE.md §2.
 */
import './style.css';
import { createBrain } from './brain';
import { ChatPanel } from './chat';
import { DanteClient } from './transport';
import type { ExchangeSource } from './transport';
import type { ServerMessage } from './protocol';

const app = document.querySelector<HTMLDivElement>('#app');
if (!app) throw new Error('missing #app mount point');

// --- Brain (graceful fallback when WebGL is unavailable) -----------------
const canvas = document.createElement('canvas');
canvas.className = 'brain-canvas';
app.appendChild(canvas);
const brain = createBrain(canvas);
if (!brain) {
  canvas.remove();
  const fallback = document.createElement('div');
  fallback.className = 'brain-fallback';
  fallback.textContent = 'WebGL unavailable — chat still works.';
  app.appendChild(fallback);
}

// --- Chat exchanges -------------------------------------------------------
// Exchange ids in flight (no chat.complete yet) and which backend owns them.
const pending = new Map<string, ExchangeSource>();

const chat = new ChatPanel(app, {
  onSend(text) {
    const id = crypto.randomUUID();
    chat.addUser(text);
    chat.startAssistant(id);
    const source = client.sendChat(id, text);
    pending.set(id, source);
  },
  onCancel() {
    // Cancel the most recent in-flight exchange, if any.
    const last = [...pending.keys()].pop();
    if (!last) return;
    const source = pending.get(last);
    if (source) client.cancelChat(last, source);
  },
});

function handleMessage(msg: ServerMessage): void {
  switch (msg.type) {
    case 'chat.delta':
      chat.appendDelta(msg.id, msg.text);
      brain?.beat();
      break;
    case 'chat.complete':
      pending.delete(msg.id);
      chat.completeAssistant(msg.id);
      break;
    case 'agent.state':
      brain?.setAgentState(msg.state);
      chat.setAgentState(msg.state);
      break;
    case 'system.mode':
      brain?.setSystemMode(msg.mode);
      chat.setSystemMode(msg.mode);
      break;
    case 'dream.notify':
      // v1 clients MAY ignore; we surface it as a system note.
      chat.addSystemNote(`dream — ${msg.title}: ${msg.body}`);
      break;
    case 'error':
      if (msg.id) {
        // Exchange-scoped error terminates that exchange (as chat.complete).
        pending.delete(msg.id);
        chat.completeAssistant(msg.id);
      }
      chat.addSystemNote(`error (${msg.code}): ${msg.message}`);
      break;
    case 'server.hello':
    case 'pong':
      break; // consumed inside the transport
  }
}

// --- Transport ------------------------------------------------------------
const client = new DanteClient({
  onStatus(status, simulated) {
    chat.setStatus(status, simulated);
  },
  onMessage: handleMessage,
  onDisconnect() {
    // Live socket dropped: live exchanges without chat.complete are dead —
    // their ids will never receive deltas again (no replay on reconnect).
    for (const [id, source] of pending) {
      if (source === 'live') {
        chat.markInterrupted(id);
        pending.delete(id);
      }
    }
  },
});

client.start();
