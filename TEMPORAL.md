# Temporal Quick-Start Guide

Durable execution layer for the Jarvis Trinity system. Makes Dreamer cycles,
Executor interactions, and nightly consolidation crash-proof.

## Prerequisites

- Python 3.11+
- Git
- Temporal CLI (for local dev)

## Setup

```bash
# Clone and install with Temporal dependencies
git clone <repo-url> && cd jarvis
pip install -e '.[temporal]'

# Or install everything (memory + temporal)
pip install -e '.[all]'

# Copy and configure environment
cp .env.example .env
# Edit .env with your GOOGLE_API_KEY
```

## Local Development

### 1. Start Temporal Server

```bash
# Install Temporal CLI if needed
# macOS: brew install temporal
# Other: https://docs.temporal.io/cli#install

temporal server start-dev
```

This starts a local Temporal server at `localhost:7233` with the Web UI at
`http://localhost:8233`.

### 2. Start the Jarvis Worker

```bash
python -m triforce.temporal.worker
```

The worker registers:
- **AwakeWorkflow** — Durable ReAct loop for user interactions
- **DreamWorkflow** — Scheduled Dreamer cycles with breakthrough detection
- **ConsolidationWorkflow** — Nightly memory consolidation

### 3. Run ADK Agents (Separate Terminal)

```bash
adk run triforce
```

ADK agents work independently of Temporal. Short interactions run inline via ADK.
High-weight actions (>=4) are routed to AwakeWorkflow for durable execution.

## Architecture

```
┌──────────────┐    ┌──────────────────┐    ┌──────────────────┐
│  ADK Agents  │    │ Temporal Server   │    │  Jarvis Worker   │
│              │───>│                  │───>│                  │
│  Dreamer     │    │  Task Queue:     │    │  Activities:     │
│  Judge       │    │  jarvis-trinity  │    │  generate_content│
│  Executor    │    │                  │    │  dynamic_tool    │
│  Root        │    │  Schedules:      │    │                  │
└──────────────┘    │  dream-cycle     │    │  Workflows:      │
                    │  consolidation   │    │  Awake/Dream/    │
                    └──────────────────┘    │  Consolidation   │
                                           └──────────────────┘
```

## Workflows

### AwakeWorkflow

Durable ReAct loop for user interactions. Each Gemini API call and tool invocation
is a separate Temporal Activity — if the worker crashes mid-loop, it resumes from
the last completed Activity.

### DreamWorkflow

Scheduled every 6 hours (configurable via `DREAM_INTERVAL_HOURS`). Runs
Dreamer→Judge-collaborator cycles until a breakthrough is detected or max
iterations (8) are reached. Uses SKIP overlap policy to prevent concurrent runs.

### ConsolidationWorkflow

Daily at 03:00 UTC (configurable via `CONSOLIDATION_HOUR_UTC`). Runs the memory
consolidation pipeline: FadeMem decay, episode compression, SSGM audit, and
journal tier summarization.

## Configuration

| Variable | Default | Description |
|---|---|---|
| `TEMPORAL_ADDRESS` | `localhost:7233` | Temporal server address |
| `TEMPORAL_NAMESPACE` | `default` | Temporal namespace |
| `DREAM_INTERVAL_HOURS` | `6` | Dream cycle schedule interval |
| `CONSOLIDATION_HOUR_UTC` | `3` | Nightly consolidation hour (UTC) |

## Web UI

With the local Temporal server running, view workflows at:
`http://localhost:8233`

You can see:
- Running and completed workflows
- Activity history and retry status
- Schedule next-run times
- Workflow input/output data
