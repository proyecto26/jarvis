/**
 * DANTE client transport — WebSocket primary with auto-reconnect and a
 * client-side DEMO MODE fallback (ARCHITECTURE.md §1/§2).
 *
 * The interface is deliberately transport-agnostic: the app consumes a single
 * stream of `ServerMessage`s and calls `sendChat()`/`cancelChat()`. Whether
 * frames come from the live WebSocket or the local DemoResponder is invisible
 * above this module — the documented SSE(+POST) fallback would slot in behind
 * the same surface.
 */
import {
  PROTOCOL_VERSION,
  WS_URL,
  RECONNECT_BASE_MS,
  RECONNECT_MAX_MS,
  RECONNECT_JITTER,
  RECONNECT_STABLE_MS,
  PING_IDLE_MS,
  PONG_TIMEOUT_MS,
} from './protocol';
import type { ClientMessage, ServerMessage } from './protocol';
import { DemoResponder } from './demo';

/**
 * connecting — first attempt in flight, no verdict yet.
 * connected  — live socket, `server.hello` received.
 * demo       — server unreachable; local responder active, reconnecting forever.
 */
export type ConnectionStatus = 'connecting' | 'connected' | 'demo';

/** Where a chat exchange is being answered from. */
export type ExchangeSource = 'live' | 'demo';

export interface DanteClientHandlers {
  /** Connection status changed. `simulated` is meaningful only when connected. */
  onStatus: (status: ConnectionStatus, simulated: boolean) => void;
  /** A validated server (or demo-synthesized) message arrived. */
  onMessage: (msg: ServerMessage) => void;
  /** The live socket dropped — in-flight live exchanges are now interrupted. */
  onDisconnect: () => void;
}

const SERVER_TYPES: ReadonlySet<string> = new Set([
  'server.hello',
  'chat.delta',
  'chat.complete',
  'agent.state',
  'system.mode',
  'dream.notify',
  'error',
  'pong',
]);

/** Validate one inbound frame per the envelope rules; null → log + drop. */
function parseServerMessage(data: unknown): ServerMessage | null {
  if (typeof data !== 'string') return null;
  let raw: unknown;
  try {
    raw = JSON.parse(data);
  } catch {
    console.warn('[dante] dropping non-JSON frame');
    return null;
  }
  if (typeof raw !== 'object' || raw === null) return null;
  const msg = raw as { v?: unknown; type?: unknown };
  if (typeof msg.v !== 'number' || typeof msg.type !== 'string') {
    console.warn('[dante] dropping frame without v/type envelope');
    return null;
  }
  if (msg.v > PROTOCOL_VERSION) {
    console.warn(`[dante] dropping frame with future protocol v${msg.v}`);
    return null;
  }
  if (!SERVER_TYPES.has(msg.type)) {
    console.warn(`[dante] dropping unknown message type "${msg.type}"`);
    return null;
  }
  return raw as ServerMessage;
}

export class DanteClient {
  private readonly handlers: DanteClientHandlers;
  private readonly demo: DemoResponder;

  private ws: WebSocket | null = null;
  private status: ConnectionStatus = 'connecting';
  private live = false;
  private attempts = 0;
  private reconnectTimer = 0;
  private stableTimer = 0;
  private pingTimer = 0;
  /** Timestamp of the last INBOUND frame — outbound sends prove nothing. */
  private lastActivity = 0;
  /** Non-zero while a ping is outstanding; the value is when it was sent. */
  private awaitingPongSince = 0;
  private everFailed = false;

  constructor(handlers: DanteClientHandlers) {
    this.handlers = handlers;
    this.demo = new DemoResponder((msg) => this.handlers.onMessage(msg));
  }

  start(): void {
    this.setStatus('connecting');
    this.connect();
    // Idle ping keep-alive with a pong deadline: after 20 s of read idle we
    // send `ping`; if no inbound frame follows within PONG_TIMEOUT_MS the
    // socket is half-open (sleep/Wi-Fi drop without a FIN — send() never
    // errors on those), so force-close it instead of waiting minutes for
    // the OS TCP timeout. onConnectionLost then reconnects / goes demo.
    this.pingTimer = window.setInterval(() => {
      if (!this.live) return;
      const now = Date.now();
      if (this.awaitingPongSince > 0) {
        if (now - this.awaitingPongSince >= PONG_TIMEOUT_MS) {
          console.warn('[dante] no pong within deadline — socket is dead');
          this.failHalfOpenSocket();
        }
        return;
      }
      if (now - this.lastActivity >= PING_IDLE_MS) {
        this.awaitingPongSince = now;
        this.sendRaw({ v: PROTOCOL_VERSION, type: 'ping' });
      }
    }, 2_500);
  }

  /** Returns which backend answered, so the caller can track interruption. */
  sendChat(id: string, text: string): ExchangeSource {
    if (this.live) {
      this.sendRaw({ v: PROTOCOL_VERSION, type: 'chat.send', id, text });
      return 'live';
    }
    this.demo.respond(id, text);
    return 'demo';
  }

  cancelChat(id: string, source: ExchangeSource): void {
    if (source === 'live' && this.live) {
      this.sendRaw({ v: PROTOCOL_VERSION, type: 'chat.cancel', id });
    } else {
      this.demo.cancel(id);
    }
  }

  dispose(): void {
    window.clearTimeout(this.reconnectTimer);
    window.clearTimeout(this.stableTimer);
    window.clearInterval(this.pingTimer);
    this.demo.dispose();
    if (this.ws) {
      this.ws.onclose = null;
      this.ws.close();
      this.ws = null;
    }
  }

  private connect(): void {
    let ws: WebSocket;
    try {
      ws = new WebSocket(WS_URL);
    } catch {
      this.onConnectionLost();
      return;
    }
    this.ws = ws;

    ws.onopen = () => {
      this.lastActivity = Date.now();
      this.awaitingPongSince = 0;
      this.sendRaw({ v: PROTOCOL_VERSION, type: 'client.hello', client: 'web' });
      // Backoff resets only after the connection proves stable for 10 s.
      window.clearTimeout(this.stableTimer);
      this.stableTimer = window.setTimeout(() => {
        this.attempts = 0;
      }, RECONNECT_STABLE_MS);
    };

    ws.onmessage = (ev: MessageEvent) => {
      this.lastActivity = Date.now();
      this.awaitingPongSince = 0; // any inbound frame proves liveness
      const msg = parseServerMessage(ev.data);
      if (!msg) return;
      if (msg.type === 'server.hello') {
        this.live = true;
        this.attempts = Math.min(this.attempts, 4); // hello seen; near-reset
        // The real server owns the conversation again: settle any in-flight
        // demo exchanges (their bubbles complete) so canned demo frames
        // never interleave with live server state/deltas while 'connected'.
        this.demo.settleAll();
        this.setStatus('connected', msg.simulated);
        return; // consumed here; simulated flag travels via onStatus
      }
      if (msg.type === 'pong') return; // liveness only
      this.handlers.onMessage(msg);
    };

    ws.onclose = () => this.onConnectionLost();
    ws.onerror = () => {
      // onclose always follows onerror for WebSocket; just ensure teardown.
    };
  }

  /** A ping went unanswered: tear the half-open socket down ourselves. */
  private failHalfOpenSocket(): void {
    const ws = this.ws;
    this.onConnectionLost(); // detaches handlers; safe to close afterwards
    try {
      ws?.close();
    } catch {
      // socket already unusable — that is the point
    }
  }

  private onConnectionLost(): void {
    if (this.ws) {
      this.ws.onopen = null;
      this.ws.onmessage = null;
      this.ws.onclose = null;
      this.ws = null;
    }
    this.awaitingPongSince = 0;
    window.clearTimeout(this.stableTimer);

    const wasLive = this.live;
    this.live = false;
    if (wasLive) this.handlers.onDisconnect();

    if (this.status !== 'demo') {
      this.setStatus('demo');
      if (!this.everFailed || wasLive) {
        // Sync visuals to a sane local baseline, like a fresh server would.
        this.demo.announce();
      }
      this.everFailed = true;
    }

    // Exponential backoff: 500 ms → 8 s cap, ±20% jitter, forever.
    const base = Math.min(
      RECONNECT_BASE_MS * 2 ** this.attempts,
      RECONNECT_MAX_MS,
    );
    const jitter = 1 + RECONNECT_JITTER * (Math.random() * 2 - 1);
    const delay = Math.round(base * jitter);
    this.attempts += 1;
    window.clearTimeout(this.reconnectTimer);
    this.reconnectTimer = window.setTimeout(() => this.connect(), delay);
  }

  private sendRaw(msg: ClientMessage): void {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      // NOTE: no lastActivity bump here — sends into a dead socket succeed
      // silently, so only INBOUND frames may count as liveness evidence.
      this.ws.send(JSON.stringify(msg));
    }
  }

  private setStatus(status: ConnectionStatus, simulated = false): void {
    this.status = status;
    this.handlers.onStatus(status, simulated);
  }
}
