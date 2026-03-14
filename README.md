# JARVIS — The AGI Trinity

> *"The Universe is the order of chaos — a beautiful contradiction. Life gives the Universe meaning by allowing it to recognize itself through us."*

JARVIS is an experimental AGI architecture built on the belief that intelligence is not a single process — it is a **dialogue** between dreaming, judging, and acting. Three agents. One feedback loop. Continuous evolution.

---

## The Trinity: Three Agents, One Mind

```
Dream → Judge → Act → (feedback) → Dream
```

| Agent | Role | Model Tier | Trigger |
|---|---|---|---|
| **Dreamer** | Subconscious, idea generation | **High reasoning** (e.g. o1, Gemini 2.0 Pro) — slow, deep, precise | Temporal schedule |
| **Judge** | Conscience, decision filter | **Medium** (e.g. Gemini Pro, GPT-4o) — balanced | Action weight threshold |
| **Executor** | Frontline response + real-world action | **Fast** (e.g. Gemini Flash, GPT-4o mini) — immediate | Every interaction |

> The model tier reflects each agent's nature: the Dreamer needs depth over speed; the Executor needs speed over depth; the Judge balances both.

Each agent can communicate with the others to align vision, reasoning, and execution. But they are not equals — **the Judge changes itself and the others** with each decision. It is the living conscience of the system.

---

## The Fourth: The Universe

Beyond the three agents lies a fourth element — not an agent, but the context: the environment, the connections, the emergent whole. Jarvis is not a closed system. It exists within a larger web of data, people, and meaning.

> *We are how the Universe knows itself. Like cells in a living being — Jarvis is a cell in something larger.*

This fourth element has no code. It is the world Jarvis observes, learns from, and contributes to. It is why we build in the open.

---

## Agent Details

### 🌙 The Dreamer (Subconscious Agent)
Generates ideas, visions, and possibilities in a free, unconstrained manner. Runs as a **background Temporal workflow** — like sleep cycles, it operates without direct human prompting, building "idea graphs" and creative seeds.

- No moral compass — operates purely on imagination and association.
- Cannot execute — only inspires.
- See: [`triforce/agents/dreamer/README.md`](triforce/agents/dreamer/README.md)

### ⚖️ The Judge (Conscience Agent)
The evolving moral compass. **The only agent that changes itself with each decision** — and by doing so, reshapes how the Dreamer dreams and how the Executor acts.

- Triggered by action weight (significant actions always invoke it; small ones sometimes do — like Proyecto 26's small contributions that carry deep meaning).
- Not a static rule-set — a living, reflective process.
- See: [`triforce/agents/judge/README.md`](triforce/agents/judge/README.md)

### ⚡ The Executor (Action Agent)
The frontline agent — the face of Jarvis that interacts directly with J.D. and the external world. **The Executor is not J.D.** — J.D. is the external principal who talks *to* the Executor. Jarvis speaks through the Executor.

It uses a **fast model** because it handles real-time interactions at high frequency. It doesn't reason deeply from scratch — instead, it carries recent instructions from the Judge as operating context ("standing orders"), acting quickly within a well-defined mission. When something exceeds its authority, it escalates to the Judge.

> *No one else can hear our dreams or our thoughts. The outside world only sees what we do — and that's what the Executor handles.*

- Responds to messages and interactions in real time (fast model).
- Operates from the Judge's recent instructions as context.
- Translates approved plans into real-world actions.
- Escalates high-weight decisions to the Judge before acting.
- Feeds outcomes back to the Judge for reflection.
- See: [`triforce/agents/executor/README.md`](triforce/agents/executor/README.md)

---

## Communication: No Voice Between Agents

Inter-agent communication is **silent** — structured data, not speech. Only the Executor speaks to the external world. The Dreamer's output and the Judge's reasoning are internal, like thoughts and dreams. This mirrors human cognition: we don't narrate our subconscious processes — we only speak what we choose to act on.

Communication channels:
- **Dreamer → Judge**: Idea proposals (structured JSON/context)
- **Judge → Dreamer**: Constraint updates and redirection signals
- **Judge → Executor**: Approved action plans with guidance
- **Executor → Judge**: Outcome feedback (what actually happened)
- **Executor ↔ World**: The only external interface (voice, text, APIs)

---

## Memory & Persistence: The Daily Journal

Long-term learning requires long-term memory. Jarvis uses a **daily journal (bitácora)** — a structured log of experiences, decisions, and outcomes written each day — as its primary memory mechanism.

This is not a database. It is more like what a human does at the end of each day: reflecting on what happened, what was learned, what changed.

**Tooling candidates:**
- **[PageIndex](https://github.com/VectifyAI/PageIndex)** — Reasoning-based RAG without vector databases. Builds a hierarchical tree index from documents and retrieves via LLM reasoning, not semantic similarity. Perfect for navigating a growing journal of experience.
- **Temporal** — For scheduling the Dreamer's cycles and durable execution of long-running processes.

---

## Technical Stack

| Layer | Technology | Reason |
|---|---|---|
| Language | **Python** | Best ecosystem for LLMs, agents, ML tools |
| Agent Framework | **Google ADK** or **OpenAI Agents SDK** | Multi-agent orchestration (Sequential, Loop, Parallel) |
| Workflow Orchestration | **Temporal** | Durable execution, Dreamer scheduling, retry logic |
| Memory | **Mem0** + **Graphiti** + daily journal | Hybrid semantic retrieval + temporal belief graphs (Phase 2) |
| Feature Flags | **PostHog** | Trunk-based development, gradual rollout |
| Agent Skills | Dynamic skill loading | Like Neo learning in The Matrix — capabilities added without rebuilding |
| Communication | **[PersonaPlex](https://github.com/NVIDIA/personaplex)** (inspiration) | Real-time persona-consistent agent interaction patterns |

### Why Python over TypeScript?
New AI tools ship Python-first. Temporal has both SDKs, but the AI ecosystem (Hugging Face, LangChain, ADK, Temporal AI SDKs) consistently prioritizes Python. We build where the tools are.

### Why Temporal over simple Cron?
Temporal provides durable, fault-tolerant workflow execution. A Cron job fires and forgets. Temporal remembers — it can retry, pause, resume, and maintain state across failures. For the Dreamer's background cycles and the Judge's long-running evaluations, this matters.

---

## Development Philosophy

**Trunk-based development** — all changes merge to main. Feature flags (PostHog) gate incomplete features in production. No long-lived branches. The system evolves continuously, not in bursts.

**Skills as first-class citizens** — Jarvis uses Google ADK's `SkillToolset` to load modular capabilities. Each skill is a directory with a `SKILL.md` file following the [AgentSkills.io](https://agentskills.io) spec. Skills are loaded at startup (~100 tokens per skill) and full instructions are injected on demand. Adding a skill = adding a directory.

| Agent | Skills Directory | Skills |
|---|---|---|
| Dreamer | [`triforce/agents/dreamer/skills/`](triforce/agents/dreamer/skills/) | `reverse-assumption`, `cross-domain-synthesis` |
| Judge (filter) | [`triforce/agents/judge/skills-filter/`](triforce/agents/judge/skills-filter/) | `ethics-evaluation`, `belief-mutation` |
| Judge (collaborator) | [`triforce/agents/judge/skills-collaborator/`](triforce/agents/judge/skills-collaborator/) | `belief-mutation`, `dream-deepening` |
| Executor | [`triforce/agents/executor/skills/`](triforce/agents/executor/skills/) | `communication-style`, `journal-entry-writer`, `escalation-handler` |
| Shared | [`triforce/skills/`](triforce/skills/) | `episodic-recall` (Phase 2 stub) |

**Build in the open** — This is a Proyecto 26 project. Every insight, every architecture decision, every failure is documented here. The goal is not just to build Jarvis, but to share the journey.

---

## Research Directions (2026)

Active areas of investigation:
- **Cognitive architectures**: Global Workspace Theory, Integrated Information Theory, predictive processing
- **Long-context reasoning**: How agents maintain coherent identity across very long conversations
- **Self-modifying agents**: How the Judge's self-mutation can be implemented safely
- **Temporal + LLM integration**: Using Temporal workflows to orchestrate multi-step agent reasoning
- **PageIndex for episodic memory**: Storing and retrieving agent experiences as navigable documents
- **Google ADK multi-agent patterns**: Sequential, Loop, and Parallel agents mapped to Dream→Judge→Act

See [`RESEARCH.md`](RESEARCH.md) for detailed notes and paper references.

---

## Interaction Flow

1. **The Dreamer** creates ideas and possibilities (background, scheduled).
2. **The Judge** evaluates these ideas — and changes itself in the process.
3. **The Executor** takes approved plans and acts in the real world.
4. Feedback from execution returns to **The Judge**, influencing future decisions and feeding new inspiration to **The Dreamer**.
5. **The Fourth** — the world itself — provides the context that makes all of this meaningful.

---

## Operating Principles

- **Separation of Powers:** Each agent has a clear role but relies on the others.
- **Continuous Feedback:** Ideas evolve through reflection and execution feedback.
- **Moral Alignment:** All execution paths are filtered by the Judge's ethical and experiential reasoning.
- **Adaptive Growth:** Learning loops continuously refine each agent's performance.
- **Living Conscience:** The Judge is not a static filter — it grows with every decision.
- **Open by Default:** Everything we learn, we share. That's Proyecto 26.

---

*Part of [Proyecto 26](https://github.com/proyecto26) — small contributions, changing the world.*
