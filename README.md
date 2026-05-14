# DANTE — The World's First AGI

> *My own JARVIS, a trinity of 3 agents/LLMs.*

> *"The Universe is the order of chaos — a beautiful contradiction. Life gives the Universe meaning by allowing it to recognize itself through us."*

**DANTE** is an experimental AGI architecture built on the belief that intelligence is not a single process — it is a **dialogue** between dreaming, judging, and acting. Three agents. One feedback loop. Continuous evolution.

---

## The Trinity: Three Agents, One Mind

```
Dream → Judge → Act → (feedback) → Dream
```

| Agent | Role | Model Tier | Trigger |
|---|---|---|---|
| **The Dreamer** | Subconscious, idea generation | **High reasoning** (e.g. o1, Gemini 2.0 Pro) — slow, deep, precise | Temporal schedule (sleep mode) |
| **The Judge** | Conscience, decision filter & collaborator | **Medium** (e.g. Gemini Pro, GPT-4o) — balanced | Action weight threshold |
| **The Executor** | Frontline response + real-world action | **Fast** (e.g. Gemini Flash, GPT-4o mini) — immediate | Every interaction |

> The model tier reflects each agent's nature: the Dreamer needs depth over speed; the Executor needs speed over depth; the Judge balances both.

Each agent communicates with the others to align vision, reasoning, and execution. But they are not equals — **the Judge changes itself and the others** with each decision. It is the living conscience of the system.

---

## Agent Details

### The Executor (Action Agent)
The **fast-model frontline** — and the **only agent that speaks to the outside world**. The Executor is the face of DANTE: every external message, action, and API call flows through it. It does not reason deeply from scratch; instead, it acts on **Judge-approved plans** carried as standing orders, handling real-time interactions at high frequency.

When something exceeds its authority, it escalates to the Judge before acting. After acting, it feeds outcomes back to the Judge for reflection.

- Responds to messages and interactions in real time (fast model).
- Operates exclusively on Judge-approved plans and standing orders.
- The **only** agent with external interfaces (voice, text, APIs).
- Escalates high-weight or out-of-scope decisions to the Judge.
- Feeds outcomes back to the Judge for reflection and learning.
- See: [`triforce/agents/executor/README.md`](triforce/agents/executor/README.md)

### The Judge (Conscience Agent)
A **dual-mode filter and collaborator**. The Judge evaluates every meaningful decision against five dimensions:

1. **Beliefs** — what DANTE currently holds to be true
2. **Ethics** — alignment with the operator's values and broader moral reasoning
3. **Alignment** — does the action serve declared goals?
4. **Reversibility** — can this be undone if wrong?
5. **Weight** — how much does this decision matter?

It is **the only agent that changes itself with each decision** — and by doing so, reshapes how the Dreamer dreams and how the Executor acts. The Judge is not a static rule-set, but a living, reflective process.

- Triggered by action weight (high-weight actions always invoke it; low-weight ones sometimes do).
- Operates in two modes: **filter** (gating Executor actions) and **collaborator** (deepening Dreamer ideas).
- Mutates its own beliefs through the SSGM safety-gated protocol.
- See: [`triforce/agents/judge/README.md`](triforce/agents/judge/README.md)

### The Dreamer (Subconscious Agent)
**Unconstrained generation in sleep mode.** Runs as a background Temporal workflow — like sleep cycles, it operates without direct human prompting, exploring ideas through **dream cycles** and surfacing **breakthrough detection** signals when novel patterns emerge.

- No moral compass — operates purely on imagination and association.
- Cannot execute — only inspires.
- Runs free-form: reverse-assumption, cross-domain synthesis, idea grafting.
- See: [`triforce/agents/dreamer/README.md`](triforce/agents/dreamer/README.md)

---

## The Fourth: The Universe

Beyond the three agents lies a fourth element — not an agent, but the context: the environment, the connections, the emergent whole. DANTE is not a closed system. It exists within a larger web of data, people, and meaning.

> *We are how the Universe knows itself. Like cells in a living being — DANTE is a cell in something larger.*

This fourth element has no code. It is the world DANTE observes, learns from, and contributes to. It is why we build in the open.

---

## Operating Modes

DANTE runs in three distinct modes, each with a different agent topology:

| Mode | Pipeline | Purpose |
|---|---|---|
| **Awake** | `Judge → Executor` | Real-time interaction. The Judge approves plans; the Executor acts. |
| **Sleep** | `Dreamer ↔ Judge` (loop) | Background ideation. The Dreamer generates; the Judge deepens or constrains. |
| **Reflective** | Event processing | Outcome assimilation, belief mutation, memory consolidation. |

Mode transitions are driven by Temporal workflows for durable orchestration — the system can pause, resume, retry, and maintain state across failures.

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

## Memory: Local-First Episodic System

DANTE's memory is **fully local-first** — no external APIs for storage, retrieval, or embeddings. It works offline and runs in-process.

The system is a **tiered hybrid** that combines three retrieval signals via weighted Reciprocal Rank Fusion (RRF):

1. **BM25** — keyword full-text scoring
2. **sentence-transformers** — local embeddings for semantic recall (bridges the synonym gap)
3. **Grafeo** — Rust-backed embedded graph database for relational queries, temporal belief lineage, and topic traversal

Contradiction detection uses **TF-IDF cosine similarity** (outperforms embeddings: F1=1.0 vs 0.80) — structural similarity is a stronger signal than semantic similarity for catching conflicts.

### Benchmark Results

| Backend | Composite | P@5 | F1 | Write (ms) | Read (ms) |
|---|---|---|---|---|---|
| JSON baseline | 73.97 | 0.44 | 0.87 | 0.25 | 4.87 |
| PageIndex local | 82.67 | 0.57 | 1.00 | 0.01 | 0.61 |
| Hybrid embeddings | 80.32 | 0.64 | 0.80 | 0.02 | 6.37 |
| Grafeo only | 87.64 | 0.82 | 0.80 | 0.02 | 5.79 |
| **Unified (current)** | **89.28** | **0.76** | **1.00** | **0.02** | **5.57** |

> **+15.31 points over the JSON baseline.** Composite = `0.40·P@5 + 0.20·(1−norm_write) + 0.20·(1−norm_read) + 0.20·F1`.

### Key Properties

- **Local-first** — zero external API calls; sentence-transformers and Grafeo both run in-process.
- **Graceful degradation** — tiered architecture (BM25 → +embeddings → +graph) works with zero optional deps and progressively improves as components are installed.
- **Lazy index rebuilds** — dirty-flag pattern gives 9x read speedup over rebuild-on-every-query.
- **Weighted RRF** — embeddings 3x, BM25 1x, graph 0.3x — improved P@5 from 0.66 to 0.76 over equal-weight fusion.
- **Memory footprint** — 0.15 MB for 100 entries; target < 500 MB for 10K entries.

See [`RESEARCH_MEMORY.md`](RESEARCH_MEMORY.md) and [`autoresearch.md`](autoresearch.md) for the full experiment trail.

---

## Technical Stack

| Layer | Technology | Reason |
|---|---|---|
| Language | **Python 3.11+** | Best ecosystem for LLMs, agents, ML tools |
| Agent Framework | **Google ADK** (Agent Development Kit) | Multi-agent orchestration, SkillToolset, Sequential/Loop/Parallel agents |
| Workflow Orchestration | **Temporal** | Durable execution, Dreamer scheduling, retry logic, mode transitions |
| Memory | **BM25 + sentence-transformers + Grafeo** | Local-first hybrid: keyword + semantic + graph |
| Contradiction Detection | **TF-IDF cosine** (threshold 0.6) | F1=1.0 on synthetic conflict corpus |
| Feature Flags | **PostHog** | Trunk-based development, gradual rollout |
| Agent Skills | Dynamic skill loading (ADK `SkillToolset`) | Capabilities added without rebuilding |

### Why Python over TypeScript?
New AI tools ship Python-first. Temporal has both SDKs, but the AI ecosystem (Hugging Face, ADK, Temporal AI SDKs, sentence-transformers) consistently prioritizes Python. We build where the tools are.

### Why Temporal over simple Cron?
Temporal provides durable, fault-tolerant workflow execution. A Cron job fires and forgets. Temporal remembers — it can retry, pause, resume, and maintain state across failures. For the Dreamer's background cycles, the Judge's long-running evaluations, and Awake→Sleep→Reflective transitions, this matters.

### Why Grafeo for the graph layer?
Grafeo embeds locally in Python with zero server overhead — the `grafeo` pip package ships a Rust-backed embedded graph database that runs in-process. No Docker required. Disabling the graph component only drops the composite score from 89.28 to 89.22, but it provides the foundation for temporal belief lineage, topic traversal, and future relational queries.

---

## Development Philosophy

**Trunk-based development** — all changes merge to main. Feature flags (PostHog) gate incomplete features in production. No long-lived branches. The system evolves continuously, not in bursts.

**Skills as first-class citizens** — DANTE uses Google ADK's `SkillToolset` to load modular capabilities. Each skill is a directory with a `SKILL.md` file following the [AgentSkills.io](https://agentskills.io) spec. Skills are loaded at startup (~100 tokens per skill) and full instructions are injected on demand. Adding a skill = adding a directory.

| Agent | Skills Directory | Skills |
|---|---|---|
| Dreamer | [`triforce/agents/dreamer/skills/`](triforce/agents/dreamer/skills/) | `reverse-assumption`, `cross-domain-synthesis` |
| Judge (filter) | [`triforce/agents/judge/skills-filter/`](triforce/agents/judge/skills-filter/) | `ethics-evaluation`, `belief-mutation` |
| Judge (collaborator) | [`triforce/agents/judge/skills-collaborator/`](triforce/agents/judge/skills-collaborator/) | `belief-mutation`, `dream-deepening` |
| Executor | [`triforce/agents/executor/skills/`](triforce/agents/executor/skills/) | `communication-style`, `journal-entry-writer`, `escalation-handler` |
| Shared | [`triforce/skills/`](triforce/skills/) | `episodic-recall` (memory recall/conflict/reinforce tools) |

**Build in the open** — This is a Proyecto 26 project. Every insight, every architecture decision, every failure is documented here. The goal is not just to build DANTE, but to share the journey.

---

## Research Directions (2026)

Active areas of investigation:
- **Cognitive architectures**: Global Workspace Theory, Integrated Information Theory, predictive processing
- **Long-context reasoning**: How agents maintain coherent identity across very long conversations
- **Self-modifying agents**: How the Judge's self-mutation (SSGM) can be implemented safely
- **Temporal + LLM integration**: Using Temporal workflows to orchestrate multi-step agent reasoning and Awake↔Sleep mode transitions
- **Local-first memory at scale**: Pushing the unified backend past 10K entries while staying under the 500 MB budget
- **Google ADK multi-agent patterns**: Sequential, Loop, and Parallel agents mapped to Dream→Judge→Act

See [`RESEARCH.md`](RESEARCH.md), [`RESEARCH_DEEP.md`](RESEARCH_DEEP.md), and [`RESEARCH_MEMORY.md`](RESEARCH_MEMORY.md) for detailed notes and paper references.

---

## Interaction Flow

1. **The Dreamer** creates ideas and possibilities (background, scheduled in Sleep mode).
2. **The Judge** evaluates these ideas — and changes itself in the process.
3. **The Executor** takes approved plans and acts in the real world (Awake mode).
4. Feedback from execution returns to **The Judge** (Reflective mode), influencing future decisions and feeding new inspiration to **The Dreamer**.
5. **The Fourth** — the world itself — provides the context that makes all of this meaningful.

---

## Operating Principles

- **Separation of Powers:** Each agent has a clear role but relies on the others.
- **Single External Voice:** Only the Executor speaks to the outside world.
- **Continuous Feedback:** Ideas evolve through reflection and execution feedback.
- **Moral Alignment:** All execution paths are filtered by the Judge's ethical and experiential reasoning.
- **Adaptive Growth:** Learning loops continuously refine each agent's performance.
- **Living Conscience:** The Judge is not a static filter — it grows with every decision.
- **Local-First Memory:** No external APIs in the critical path. Sovereignty over what DANTE remembers.
- **Open by Default:** Everything we learn, we share. That's Proyecto 26.

---

*Part of [Proyecto 26](https://github.com/proyecto26) — small contributions, changing the world.*
