/**
 * DEMO MODE responder — a local, canned Executor used while the DANTE server
 * (ws://127.0.0.1:8420) is unreachable. It emits the exact same
 * `ServerMessage` shapes the real server would, through a single callback,
 * so the rest of the app is transport-blind (see ARCHITECTURE.md §2,
 * "Demo mode (graceful degradation)").
 *
 * This is distinct from `simulated: true` in `server.hello` (server up,
 * LLM down) — demo mode means the server itself is down.
 */
import { PROTOCOL_VERSION } from './protocol';
import type { ServerMessage } from './protocol';

const REPLIES: readonly string[] = [
  "I'm answering locally — the DANTE server at ws://127.0.0.1:8420 isn't reachable, so this is a canned demo persona, not the Executor. Start the server (see triforce/server/README.md) and I'll reconnect automatically.",
  'Still offline from the trinity, I\'m afraid. The Dreamer dreams, the Judge deliberates, the Executor speaks — but right now you only have me, a small local echo living in your browser tab.',
  'Demo mode fact: everything you see — the brain, the synapse firing, this reply streaming word by word — runs with zero backend. The moment the server comes up, I hand the conversation over to the real Executor.',
  'I heard you, but I can\'t actually think — no LLM back here, just setTimeout and good intentions. The connection pill up top will flip to "connected" as soon as the DANTE server answers.',
  'While we wait for the real brain: try watching the particle cortex change state. Idle breathes, listening ripples, thinking fires synapses, speaking pulses with every word I stream at you.',
];

interface ActiveExchange {
  timers: number[];
  cancelled: boolean;
}

export class DemoResponder {
  private readonly emit: (msg: ServerMessage) => void;
  private readonly active = new Map<string, ActiveExchange>();
  private idleTimer = 0;
  private replyIndex = 0;

  constructor(emit: (msg: ServerMessage) => void) {
    this.emit = emit;
  }

  /** Push the state snapshots a real server would push after `server.hello`. */
  announce(): void {
    this.emit({ v: PROTOCOL_VERSION, type: 'agent.state', state: 'idle' });
    this.emit({ v: PROTOCOL_VERSION, type: 'system.mode', mode: 'awake' });
  }

  /** Simulate the Executor answering `chat.send` for exchange `id`. */
  respond(id: string, userText: string): void {
    const ex: ActiveExchange = { timers: [], cancelled: false };
    this.active.set(id, ex);

    const reply = this.composeReply(userText);
    // Tokenize keeping trailing spaces so deltas concatenate exactly.
    const tokens = reply.match(/\S+\s*/g) ?? [reply];

    const schedule = (delay: number, fn: () => void): void => {
      const t = window.setTimeout(() => {
        if (!ex.cancelled) fn();
      }, delay);
      ex.timers.push(t);
    };

    let at = 150;
    schedule(at, () =>
      this.emit({ v: PROTOCOL_VERSION, type: 'agent.state', state: 'listening' }),
    );
    at += 450;
    schedule(at, () =>
      this.emit({ v: PROTOCOL_VERSION, type: 'agent.state', state: 'thinking' }),
    );
    at += 700 + Math.min(userText.length * 8, 1200);
    schedule(at, () =>
      this.emit({ v: PROTOCOL_VERSION, type: 'agent.state', state: 'speaking' }),
    );
    for (const token of tokens) {
      at += 28 + Math.random() * 45;
      schedule(at, () =>
        this.emit({ v: PROTOCOL_VERSION, type: 'chat.delta', id, text: token }),
      );
    }
    at += 120;
    schedule(at, () => this.finish(id));
  }

  /** Honor `chat.cancel`: stop deltas, still emit `chat.complete`. */
  cancel(id: string): void {
    const ex = this.active.get(id);
    if (!ex) return;
    ex.cancelled = true;
    for (const t of ex.timers) window.clearTimeout(t);
    this.finish(id);
  }

  /**
   * The live server took over (reconnect succeeded): stop every in-flight
   * demo exchange immediately, emitting `chat.complete` for each so the UI
   * closes its pending bubbles. Deliberately no trailing `agent.state` —
   * the reconnected server's snapshots own the state stream now.
   */
  settleAll(): void {
    window.clearTimeout(this.idleTimer);
    for (const [id, ex] of this.active) {
      ex.cancelled = true;
      for (const t of ex.timers) window.clearTimeout(t);
      this.emit({ v: PROTOCOL_VERSION, type: 'chat.complete', id });
    }
    this.active.clear();
  }

  dispose(): void {
    window.clearTimeout(this.idleTimer);
    for (const ex of this.active.values()) {
      ex.cancelled = true;
      for (const t of ex.timers) window.clearTimeout(t);
    }
    this.active.clear();
  }

  private finish(id: string): void {
    this.active.delete(id);
    this.emit({ v: PROTOCOL_VERSION, type: 'chat.complete', id });
    if (this.active.size === 0) {
      this.idleTimer = window.setTimeout(() => {
        if (this.active.size === 0) {
          this.emit({ v: PROTOCOL_VERSION, type: 'agent.state', state: 'idle' });
        }
      }, 400);
    }
  }

  private composeReply(userText: string): string {
    const body = REPLIES[this.replyIndex % REPLIES.length] ?? REPLIES[0]!;
    this.replyIndex += 1;
    const trimmed = userText.trim();
    const quoted =
      trimmed.length > 0 && trimmed.length <= 80 && this.replyIndex === 1
        ? `You said "${trimmed}" — noted for the real Executor. `
        : '';
    return `${quoted}${body}`;
  }
}
