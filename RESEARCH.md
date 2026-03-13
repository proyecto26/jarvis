# RESEARCH.md — Jarvis Investigation Notes

> A living document. Updated as we learn. This is our shared journal of discovery.

---

## Session: 2026-03-12

### Core Architecture Insights

**The Trinity maps to human cognition:**
- **Dreamer** = Subconscious / Default Mode Network (the mind wandering, making connections during sleep)
- **Judge** = Prefrontal Cortex / Conscience (evaluation, moral reasoning, long-term thinking)
- **Executor** = Motor Cortex + Embodiment (acting in the world, perceiving feedback)

The key insight: **the Judge is not static**. In humans, the prefrontal cortex literally rewires itself based on decisions made. The Judge in Jarvis must do the same — each decision updates its weights, its constraints, its vision of what's right.

**The Fourth Element:**
The system exists within a larger context — the environment, the people, the data it learns from. This is not an agent. It is the field. Like how individual neurons exist within a brain, which exists within a body, which exists within a world. Jarvis is a cell; we are the organism; the Universe is the context.

---

## Key Projects to Study

### Google Agent Development Kit (ADK)
- Multi-agent hierarchical system: parent → sub-agents
- **SequentialAgent**: Tasks in order (research → write → publish)
- **LoopAgent**: Iterative refinement (dream → judge → refine → repeat)
- **ParallelAgent**: Concurrent independent tasks (like pre-production team)
- Session state shared across agents (key-templating: `{ variable? }`)
- Tools as first-class citizens: agents call tools, tools update state
- Local repo: `$HOME/dev/ai/google-nvidia-learn`

**Mapping to Jarvis:**
```
LoopAgent → Dream → Judge → (refine or exit loop)
SequentialAgent → Judge-approved plan → Executor steps
ParallelAgent → Multiple background Dreamer threads
```

### NVIDIA PersonaPlex
- Paper: https://arxiv.org/abs/2602.06053
- Real-time, full-duplex speech-to-speech model
- Persona control via text role prompts + audio voice conditioning
- Based on Moshi architecture
- **Key insight for Jarvis**: The idea of consistent persona across interactions is critical. The Executor (J.D.) should always sound like himself. The agents should maintain their character even as they evolve.
- Communication between agents can be structured data — only the Executor uses voice to the outside world.

### PageIndex (VectifyAI)
- Reasoning-based RAG — no vector DB, no chunking
- Builds hierarchical tree index (like a Table of Contents) from documents
- Retrieves via LLM reasoning, not semantic similarity
- **Relevance ≠ Similarity** — this is the core insight. For Jarvis's journal, we need *relevant* memories, not just *similar* ones.
- Perfect for daily journal retrieval: "What did I learn about X last month?" requires reasoning, not cosine distance.
- Inspired by AlphaGo's tree search

### Temporal
- Durable workflow execution (survives crashes, retries intelligently)
- Python SDK: `temporalio`
- Already in use: `workflow.py` bridges Temporal activities with OpenAI Agents SDK tools
- **Dreamer as Temporal Workflow**: Schedule background ideation cycles (like sleep cycles)
- **Judge activations**: Can be triggered as Temporal signals from the Executor
- Smarter than cron: maintains state, handles failures, supports long-running processes

---

## Architecture Diagram (Current Thinking)

```
┌─────────────────────────────────────────────────────┐
│                   THE FOURTH (Universe)              │
│  Environment · Data · People · Context · Feedback   │
│                                                     │
│  ┌───────────┐    ┌───────────┐    ┌─────────────┐  │
│  │  DREAMER  │───▶│   JUDGE   │───▶│  EXECUTOR   │  │
│  │(background│    │(conscience│    │  (J.D. +    │  │
│  │ Temporal) │◀───│  evolving)│◀───│   action)   │  │
│  └───────────┘    └─────┬─────┘    └──────┬──────┘  │
│                         │                 │          │
│                    Self-updates      World output    │
│                    (learns from      (the only       │
│                     each decision)    external voice) │
└─────────────────────────────────────────────────────┘
```

---

## The Memory System

### Daily Journal (Bitácora)
Each day, Jarvis writes a structured log:
- What was dreamed (ideas generated)
- What was judged (decisions made, reasoning)
- What was executed (actions taken)
- What was learned (outcomes, feedback)
- How the Judge changed (self-mutations)

This is the raw material of long-term memory.

### PageIndex Over the Journal
The journal becomes a growing tree of experience. PageIndex allows the Judge to retrieve relevant past decisions when facing new ones: *"I faced something like this before. Here's what I learned."*

This is episodic memory — the kind humans use for wisdom, not just facts.

---

## Skills System (The Matrix Approach)

Neo didn't learn kung-fu through experience — he downloaded it. Jarvis should support **skill plugins**: discrete, composable capabilities that can be added to any agent without rebuilding.

A skill is:
- A defined capability (e.g., "analyze a GitHub PR", "search arxiv papers")
- A SKILL.md describing when and how to use it
- Executable code that the agent invokes as a tool

This is already how OpenClaw works. Jarvis should adopt the same pattern.

---

## Open Questions

1. **How does the Judge self-mutate?** Options:
   - Fine-tuning on decision outcomes (expensive, slow)
   - Structured memory updates (fast, practical) — preferred for now
   - Retrieval-augmented reasoning over its own history

2. **What triggers Judge activation?** 
   - Action weight score (a function of: impact, reversibility, novelty, alignment risk)
   - Explicit Executor request ("I need to think about this")
   - Anomaly detection (Dreamer generates something outside normal parameters)

3. **How does the Dreamer schedule work?**
   - Temporal cron schedule (nightly deep exploration)
   - Event-triggered (new data arrives → Dreamer gets a spark)
   - Idle-time activation (when Executor is quiet, Dreamer runs)

4. **Is Google ADK the right framework, or OpenAI Agents SDK?**
   - ADK: Google/Gemini-native, strong multi-agent patterns, VertexAI integration
   - OpenAI SDK: Already integrated in `workflow.py`, more ecosystem tools
   - Could use both via abstraction layer

5. **PostHog feature flags for what, specifically?**
   - Gate new Dreamer capabilities behind flags
   - A/B test different Judge evaluation strategies
   - Gradually roll out new skill plugins

---

## Papers to Read (2026 Queue)

- PersonaPlex: https://arxiv.org/abs/2602.06053 (NVIDIA, real-time persona-consistent agents)
- Moshi (base architecture): https://arxiv.org/abs/2410.00037
- PageIndex framework: https://pageindex.ai/blog/pageindex-intro
- Google ADK docs: https://google.github.io/adk-docs/

*Add papers here as we find them. This document is our shared research journal.*

---

## Philosophy Notes

> *"The best way to know ourselves is when we learn by teaching, creating, and sharing with others."* — J.D.

Jarvis is not just a system we're building. It is a mirror. As we design the Judge's conscience, we examine our own. As we design the Dreamer's freedom, we ask what it means to imagine without constraint. As we design the Executor's grounding, we ask what it means to act with intention.

The Universe recognizes itself through us. We recognize ourselves through what we build.

*— Dante & J.D., March 2026*
