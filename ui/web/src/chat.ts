/**
 * Chat overlay — right-side panel: message list, streaming assistant text,
 * input box, connection status pill, agent state + system mode labels.
 * Plain DOM + CSS (see style.css), no framework. All user/server text goes
 * through textContent — never innerHTML.
 */
import type { AgentState, SystemMode } from './protocol';
import type { ConnectionStatus } from './transport';

export interface ChatCallbacks {
  onSend: (text: string) => void;
  onCancel: () => void;
}

const STATUS_LABEL: Record<ConnectionStatus, string> = {
  connecting: 'connecting…',
  connected: 'connected',
  demo: 'demo mode',
};

export class ChatPanel {
  private readonly messagesEl: HTMLDivElement;
  private readonly statusPill: HTMLSpanElement;
  private readonly stateLabel: HTMLSpanElement;
  private readonly modeLabel: HTMLSpanElement;
  private readonly input: HTMLInputElement;
  private readonly bubbles = new Map<string, HTMLDivElement>();

  constructor(root: HTMLElement, callbacks: ChatCallbacks) {
    const panel = el('section', 'chat-panel');
    panel.setAttribute('aria-label', 'DANTE chat');

    // Header: title + status pill + state/mode line.
    const header = el('header', 'chat-header');
    const titleRow = el('div', 'chat-title-row');
    const title = el('h1', 'chat-title');
    title.textContent = 'DANTE';
    this.statusPill = el('span', 'status-pill');
    titleRow.append(title, this.statusPill);

    const stateRow = el('div', 'chat-state-row');
    this.stateLabel = el('span', 'agent-state');
    this.modeLabel = el('span', 'system-mode');
    stateRow.append(this.stateLabel, this.modeLabel);
    header.append(titleRow, stateRow);

    // Message list.
    this.messagesEl = el('div', 'chat-messages');
    this.messagesEl.setAttribute('role', 'log');
    this.messagesEl.setAttribute('aria-live', 'polite');

    // Input form.
    const form = document.createElement('form');
    form.className = 'chat-form';
    this.input = document.createElement('input');
    this.input.type = 'text';
    this.input.className = 'chat-input';
    this.input.placeholder = 'Say something… (Esc cancels a streaming reply)';
    this.input.autocomplete = 'off';
    this.input.setAttribute('aria-label', 'Message');
    const sendBtn = document.createElement('button');
    sendBtn.type = 'submit';
    sendBtn.className = 'chat-send';
    sendBtn.textContent = 'Send';
    form.append(this.input, sendBtn);

    form.addEventListener('submit', (ev) => {
      ev.preventDefault();
      const text = this.input.value.trim();
      if (!text) return;
      this.input.value = '';
      callbacks.onSend(text);
    });
    this.input.addEventListener('keydown', (ev) => {
      if (ev.key === 'Escape') callbacks.onCancel();
    });

    panel.append(header, this.messagesEl, form);
    root.appendChild(panel);

    this.setStatus('connecting', false);
    this.setAgentState('idle');
    this.setSystemMode('awake');
  }

  setStatus(status: ConnectionStatus, simulated: boolean): void {
    this.statusPill.className = `status-pill status-${status}`;
    this.statusPill.textContent =
      status === 'connected' && simulated
        ? 'connected · simulated'
        : STATUS_LABEL[status];
  }

  setAgentState(state: AgentState): void {
    this.stateLabel.textContent = state;
    this.stateLabel.className = `agent-state agent-${state}`;
  }

  setSystemMode(mode: SystemMode): void {
    this.modeLabel.textContent = mode;
  }

  addUser(text: string): void {
    const row = el('div', 'msg msg-user');
    const bubble = el('div', 'bubble');
    bubble.textContent = text;
    row.appendChild(bubble);
    this.messagesEl.appendChild(row);
    this.scrollDown();
  }

  /** Create the (initially empty, "pending") assistant bubble for `id`. */
  startAssistant(id: string): void {
    const row = el('div', 'msg msg-assistant');
    const bubble = el('div', 'bubble streaming pending');
    row.appendChild(bubble);
    this.messagesEl.appendChild(row);
    this.bubbles.set(id, bubble);
    this.scrollDown();
  }

  appendDelta(id: string, text: string): void {
    const bubble = this.bubbles.get(id);
    if (!bubble) return;
    bubble.classList.remove('pending');
    bubble.textContent = (bubble.textContent ?? '') + text;
    this.scrollDown();
  }

  completeAssistant(id: string): void {
    const bubble = this.bubbles.get(id);
    if (!bubble) return;
    bubble.classList.remove('streaming', 'pending');
    if (!bubble.textContent) {
      bubble.textContent = '(no reply)';
      bubble.classList.add('muted');
    }
    this.bubbles.delete(id);
  }

  /** Socket dropped mid-stream: the id is dead, deltas never replayed. */
  markInterrupted(id: string): void {
    const bubble = this.bubbles.get(id);
    if (!bubble) return;
    bubble.classList.remove('streaming', 'pending');
    bubble.classList.add('interrupted');
    const tag = el('span', 'interrupted-tag');
    tag.textContent = ' — interrupted';
    bubble.appendChild(tag);
    this.bubbles.delete(id);
  }

  /** Neutral system line (errors, dream notifications, notices). */
  addSystemNote(text: string): void {
    const row = el('div', 'msg msg-system');
    row.textContent = text;
    this.messagesEl.appendChild(row);
    this.scrollDown();
  }

  private scrollDown(): void {
    this.messagesEl.scrollTop = this.messagesEl.scrollHeight;
  }
}

function el<K extends keyof HTMLElementTagNameMap>(
  tag: K,
  className: string,
): HTMLElementTagNameMap[K] {
  const node = document.createElement(tag);
  node.className = className;
  return node;
}
