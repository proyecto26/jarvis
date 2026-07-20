# Temporal Quick-Start Guide

Durable execution layer for the Jarvis Trinity system. Makes Dreamer cycles,
Executor interactions, and nightly consolidation crash-proof.

## Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (dependency + venv manager)
- Git
- Temporal CLI (for local dev)

## Setup

```bash
# Clone and install with Temporal dependencies (uv manages the .venv)
git clone <repo-url> && cd jarvis
uv sync --extra temporal

# Or install everything (memory + temporal + server + dev)
uv sync --all-extras

# Copy and configure environment
cp .env.example .env
# Edit .env with your GOOGLE_API_KEY
```

All Python commands below assume uv (`uv run …`). Every module still imports
without `temporalio` installed — the durable layer degrades gracefully when the
extra is not synced.

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
uv run python -m triforce.temporal.worker
```

The worker registers:
- **AwakeWorkflow** — Durable ReAct loop for user interactions
- **DreamWorkflow** — Scheduled Dreamer cycles with breakthrough detection
- **ConsolidationWorkflow** — Nightly memory consolidation

### 3. Create the Schedules (once)

```bash
uv run python -m triforce.temporal.schedules
```

Idempotently registers the Dream and Consolidation Temporal Schedules (safe to
re-run — existing schedules are not duplicated). Needs the server running and a
worker on the `jarvis-trinity` task queue to actually execute the scheduled
workflows.

### 4. Run ADK Agents (Separate Terminal)

```bash
uv run adk run triforce
```

ADK agents work independently of Temporal. **By default, every interaction runs
in-process via ADK — nothing here starts a Temporal workflow.** Durable
execution is strictly opt-in:

- Set `DANTE_DURABLE_AWAKE=on` to give the Executor the
  `escalate_to_durable_workflow` tool.
- With the flag on, the Executor may escalate a high-weight (`action_weight >=
  4`) or long-running task to the durable `AwakeWorkflow` by calling that tool.
- Escalation degrades gracefully: if the Temporal server or the `temporal`
  extra is unavailable, the tool returns a message and the Executor completes
  the task in-process. It never crashes a turn.

Full Judge-verdict → workflow routing (auto-escalating on the Judge's
`action_weight` without an explicit tool call) is a documented next step; today
the escalation is the tool + flag described above.

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

**Opt-in only.** This workflow does not run for normal turns. It is started from
production solely via `run_awake_workflow` in `triforce/temporal/client.py`,
which the Executor's `escalate_to_durable_workflow` tool calls when
`DANTE_DURABLE_AWAKE=on`. With the flag off, the Executor never has that tool and
all work stays in-process.

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
| `TEMPORAL_TASK_QUEUE` | `jarvis-trinity` | Task queue for workers + workflows |
| `DREAM_INTERVAL_HOURS` | `6` | Dream cycle schedule interval |
| `CONSOLIDATION_HOUR_UTC` | `3` | Nightly consolidation hour (UTC) |
| `DANTE_DURABLE_AWAKE` | `off` | Opt-in: give the Executor the durable escalation tool |

## Web UI

With the local Temporal server running, view workflows at:
`http://localhost:8233`

You can see:
- Running and completed workflows
- Activity history and retry status
- Schedule next-run times
- Workflow input/output data
