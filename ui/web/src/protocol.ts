/**
 * DANTE UI wire protocol, v1.
 *
 * EXACT mirror of ui/ARCHITECTURE.md §2 "Protocol spec (v1)" — that document
 * is the contract; change it first, then this file, in the same commit.
 *
 * Transport: single WebSocket, UTF-8 JSON text frames, one message per frame.
 * Endpoint:  ws://127.0.0.1:8420/ws
 *
 * Rules for receivers (both directions):
 *  - Ignore (log + drop) messages with unknown `type`.
 *  - Ignore unknown fields on known types (forward compatibility).
 *  - Ignore messages whose `v` is greater than PROTOCOL_VERSION (log + drop).
 */

export const PROTOCOL_VERSION = 1 as const;

export const WS_URL = 'ws://127.0.0.1:8420/ws' as const;
export const HEALTH_URL = 'http://127.0.0.1:8420/healthz' as const;

/** Avatar/brain animation state, pushed by the server on every change. */
export type AgentState = 'idle' | 'listening' | 'thinking' | 'speaking';

/** DANTE system mode, pushed by the server on every change. */
export type SystemMode = 'awake' | 'sleep' | 'reflective';

/** Kind of client connecting, announced in `client.hello`. */
export type ClientKind = 'web' | 'desktop';

/** Recoverable error codes carried by `error` messages. */
export type ErrorCode = 'bad_message' | 'executor_unavailable' | 'internal';

/** Common envelope: every message has `v` and a `type` discriminator. */
export interface Envelope {
  v: typeof PROTOCOL_VERSION;
  type: string;
}

/* ------------------------------------------------------------------ */
/* Client → Server                                                     */
/* ------------------------------------------------------------------ */

/** First message after connect. Announces client kind and protocol version. */
export interface ClientHello extends Envelope {
  type: 'client.hello';
  client: ClientKind;
}

/** User sends a chat message. `id` is a client-minted UUID v4. */
export interface ChatSend extends Envelope {
  type: 'chat.send';
  id: string;
  text: string;
}

/**
 * Ask the server to stop generating the reply for `id`. Server responds with
 * `chat.complete` for that `id` (possibly after a final partial delta).
 */
export interface ChatCancel extends Envelope {
  type: 'chat.cancel';
  id: string;
}

/** Liveness probe; server answers `pong`. Sent every 20 s of socket idle. */
export interface Ping extends Envelope {
  type: 'ping';
}

export type ClientMessage = ClientHello | ChatSend | ChatCancel | Ping;

/* ------------------------------------------------------------------ */
/* Server → Client                                                     */
/* ------------------------------------------------------------------ */

/**
 * First message after connect. `simulated: true` means the real Executor
 * (google-adk/LLM) is unavailable and replies come from the simulated
 * Executor — the UI should show a subtle "demo mode" indicator.
 */
export interface ServerHello extends Envelope {
  type: 'server.hello';
  protocol: number;
  simulated: boolean;
}

/** One streamed token/chunk of the assistant reply for exchange `id`. */
export interface ChatDelta extends Envelope {
  type: 'chat.delta';
  id: string;
  text: string;
}

/**
 * Reply for `id` is finished (normally or via cancel). No further
 * `chat.delta` for this `id` will follow.
 */
export interface ChatComplete extends Envelope {
  type: 'chat.complete';
  id: string;
}

/**
 * Avatar/brain animation state. Pushed on every change, and pushed once
 * (current value) right after `server.hello`.
 */
export interface AgentStateMsg extends Envelope {
  type: 'agent.state';
  state: AgentState;
}

/** DANTE system mode. Pushed on change and right after `server.hello`. */
export interface SystemModeMsg extends Envelope {
  type: 'system.mode';
  mode: SystemMode;
}

/**
 * Future: Temporal-driven dream/reflection notification. Clients MAY ignore
 * in v1; defined now so the envelope is stable.
 */
export interface DreamNotify extends Envelope {
  type: 'dream.notify';
  title: string;
  body: string;
}

/**
 * Recoverable error. `id` present when tied to a chat exchange (that
 * exchange is then terminated — treat as `chat.complete`).
 */
export interface ErrorMsg extends Envelope {
  type: 'error';
  code: ErrorCode;
  message: string;
  id?: string;
}

/** Reply to `ping`. */
export interface Pong extends Envelope {
  type: 'pong';
}

export type ServerMessage =
  | ServerHello
  | ChatDelta
  | ChatComplete
  | AgentStateMsg
  | SystemModeMsg
  | DreamNotify
  | ErrorMsg
  | Pong;

/* ------------------------------------------------------------------ */
/* Reconnect policy (client-side, see ARCHITECTURE.md)                 */
/* ------------------------------------------------------------------ */

/** Exponential backoff schedule: 500 ms doubling to an 8 s cap, ±20% jitter. */
export const RECONNECT_BASE_MS = 500;
export const RECONNECT_MAX_MS = 8_000;
export const RECONNECT_JITTER = 0.2;
/** A connection surviving this long resets the backoff to base. */
export const RECONNECT_STABLE_MS = 10_000;
/** Client sends `ping` after this much socket idle. */
export const PING_IDLE_MS = 20_000;
/**
 * After sending `ping`, some inbound frame (normally `pong`) must arrive
 * within this window or the socket is treated as half-open/dead and is
 * force-closed so the normal reconnect + demo-mode fallback take over.
 */
export const PONG_TIMEOUT_MS = 10_000;
