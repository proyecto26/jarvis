## Context

Phase 1 established the Trinity architecture (Dreamer, Judge, Executor) as a working multi-agent system using Google ADK. All three agents run in a single Python process, communicating via ADK session state (`tool_context.state`). This works for local development but creates fundamental limitations:

- **Scaling**: The Dreamer requires heavy models (gemini-2.0-pro) but runs infrequently (Temporal-scheduled dream cycles). Keeping it in the same process as the fast Executor wastes resources.
- **Independence**: Updating one agent requires redeploying the entire system.
- **Interoperability**: The agents are locked into ADK — no path to swap in a LangChain or CrewAI agent.

Google's Agent-to-Agent (A2A) protocol solves these problems with standardized JSON-RPC 2.0 communication, Agent Cards for discovery, and framework-agnostic design. ADK natively supports A2A via `RemoteA2aAgent` and `adk deploy cloud_run --a2a`.

Key constraints:
- Must maintain backward compatibility with Phase 1 single-process mode
- A2A protocol spec at https://a2a-protocol.org/
- ADK's `RemoteA2aAgent` reads Agent Cards from local files or URLs
- Deployment target: Cloud Run (production), Docker Compose (development)

## Goals / Non-Goals

**Goals:**
- Deploy each Trinity agent as an independent A2A-compatible service
- Define Agent Cards (agent.json) describing each agent's capabilities and endpoint
- Wire `RemoteA2aAgent` connections for distributed agent communication
- Phased migration: Dreamer first → Judge second → Executor as client
- Docker Compose setup for local distributed development
- Cloud Run deployment configuration for production
- Enable cross-framework agent replacement via A2A protocol compliance

**Non-Goals:**
- Streaming or push notification support (Phase 3 uses synchronous A2A calls)
- Authentication/authorization between agents (added in production hardening)
- Agent Card registry or dynamic discovery service (agents use known endpoints)
- Temporal integration (separate Phase 3 concern — this focuses on A2A distribution)
- Multi-cloud deployment (Cloud Run only in Phase 3)
- Load balancing or auto-scaling policies (Cloud Run handles this natively)

## Decisions

### 1. Dreamer as first A2A service

**Choice**: Extract Dreamer as the first independently deployed A2A service.

**Rationale**: Dreamer is the ideal first candidate because:
- Uses the heaviest model (gemini-2.0-pro) — benefits most from independent scaling
- Runs on Temporal schedules during sleep cycles — no real-time latency requirement
- Has the simplest interface: receives seed context, returns dream content via state
- Failure is non-critical: if Dreamer is unreachable, the system degrades gracefully (no dreams, but Executor still works)

**Alternative considered**: Starting with Judge. Rejected — Judge is called in both awake (filter) and sleep (collaborator) modes, making it a higher-risk extraction. Dreamer's simpler interaction pattern makes it a safer first move.

### 2. Judge as second A2A service

**Choice**: Extract Judge as the second A2A service after Dreamer is stable.

**Rationale**: Judge uses a medium model and operates event-driven — it evaluates when called, doesn't need to be co-located with the Executor. Once Dreamer proves the A2A pattern works, Judge follows the same deployment template. Judge's dual-mode behavior (filter/collaborator) is expressed through A2A message content, not protocol differences.

**Alternative considered**: Keeping Judge in-process permanently. Rejected — independent deployment enables model-specific scaling and cross-framework replacement.

### 3. Executor as A2A client (not server)

**Choice**: Executor remains the frontline process and acts as an A2A client that orchestrates remote calls to Dreamer and Judge via `RemoteA2aAgent`.

**Rationale**: Executor is the user-facing agent — it needs the lowest latency and handles real-time interaction. Making it a remote service would add unnecessary network hops for every user interaction. Instead, it uses `RemoteA2aAgent` to call Dreamer and Judge as sub-agents, reading their Agent Cards for discovery.

**Alternative considered**: All three as remote services with a thin gateway. Rejected — adds complexity and latency for the most latency-sensitive agent.

### 4. Agent Cards as local JSON files (development) and hosted endpoints (production)

**Choice**: During development, Agent Cards are local JSON files read by `RemoteA2aAgent`. In production, each A2A server hosts its card at `/.well-known/agent.json` (A2A convention) and the service URL in the card points to the Cloud Run endpoint.

**Rationale**: ADK's `RemoteA2aAgent` accepts both file paths and URLs for `agent_card` parameter. Local files avoid network dependencies during development. Production URLs enable true service discovery.

**Alternative considered**: Central agent registry. Rejected — three agents don't need a registry; direct card references are simpler and more reliable.

### 5. Docker Compose for local distributed development

**Choice**: Provide a `docker-compose.yml` that runs each Trinity agent as a separate container, mimicking the distributed production setup locally.

**Rationale**: Developers need to test A2A communication without deploying to Cloud Run. Docker Compose gives each agent its own process and network endpoint while remaining easy to start/stop. Agent Cards use container hostnames (e.g., `http://dreamer:8001`).

**Alternative considered**: Running multiple `adk web` instances on different ports. Feasible but fragile — Docker Compose formalizes the multi-service setup and matches production topology.

### 6. Cloud Run deployment via `adk deploy cloud_run --a2a`

**Choice**: Use ADK's built-in Cloud Run deployment with the `--a2a` flag, which wraps agents with `A2aAgentExecutor` and serves the Agent Card automatically.

**Rationale**: ADK provides first-class A2A deployment support. The `--a2a` flag handles: wrapping the agent with the A2A executor bridge, serving the Agent Card at the well-known path, and translating A2A tasks/messages to ADK events/state. No custom server code needed.

**Alternative considered**: Custom FastAPI/Flask A2A server. Rejected — reinvents what ADK already provides.

### 7. Session state to A2A message translation

**Choice**: Inter-agent communication that currently uses session state keys (`dream_seeds`, `judge_verdict`, etc.) will be translated to A2A message content. The sending agent encodes state as structured JSON in the A2A message; the receiving agent's A2A executor unpacks it back into local session state.

**Rationale**: A2A protocol uses messages (text, JSON, files) not shared memory. The translation layer preserves the same state key conventions from Phase 1 while transmitting them as A2A message payloads. This means agent prompts and tools don't change — only the transport layer changes.

**Alternative considered**: Redesigning inter-agent data flow for A2A from scratch. Rejected — maintaining state key compatibility means Phase 1 agent code works in both modes.

### 8. Backward-compatible dual-mode execution

**Choice**: Support both single-process (Phase 1) and distributed (Phase 3) execution modes via environment configuration. An `AGENT_MODE` environment variable (`local` or `a2a`) controls whether agents are instantiated as local ADK agents or `RemoteA2aAgent` references.

**Rationale**: Teams need to develop locally without Docker. Existing Phase 1 tests and workflows must keep working. A simple environment flag lets the same codebase serve both modes.

**Alternative considered**: Separate codebases for local and distributed. Rejected — code duplication and divergence risk.

## Risks / Trade-offs

**[Risk] A2A protocol maturity** — A2A is a relatively new protocol; SDK and tooling may have gaps.
→ Mitigation: Use ADK's built-in A2A support which is maintained by Google. Pin `a2a-sdk` version. Keep agent logic framework-agnostic so migration is possible.

**[Risk] Network latency in dream loops** — Sleep mode iterates Dreamer↔Judge up to 8 times. Each iteration now involves network calls instead of in-process state passing.
→ Mitigation: Dream loops are explicitly non-real-time (Temporal-scheduled, no user waiting). Added latency (50-200ms per hop) is acceptable for 8 iterations. Monitor loop duration; if needed, co-locate Dreamer and Judge in the same region.

**[Risk] State serialization overhead** — Session state (dream_seeds, judge_verdict, etc.) must be serialized to JSON for A2A messages and deserialized on the other side.
→ Mitigation: State values are already simple types (strings, lists, numbers). Pydantic models from Phase 1 handle serialization naturally. No binary or complex objects in state.

**[Risk] Partial deployment failures** — One agent service may be down while others are up.
→ Mitigation: Executor detects remote agent unavailability and falls back to degraded mode (e.g., skip dream cycle if Dreamer unreachable, use cached Judge beliefs if Judge unreachable). Cloud Run provides automatic restarts and health checks.

**[Trade-off] Increased operational complexity** — Three services instead of one process means more deployment, monitoring, and debugging surface area.
→ Accepted: This is the inherent cost of distribution. Docker Compose mitigates local complexity. Cloud Run handles production operations. The benefits (independent scaling, framework flexibility) outweigh the cost.

**[Trade-off] No authentication between agents in Phase 3** — Agent-to-agent calls are unauthenticated.
→ Accepted: Phase 3 targets development and early production. Cloud Run's IAM can restrict access at the infrastructure level. Application-level auth is a production hardening concern.

## Migration Plan

### Step 1: Extract Dreamer as A2A service
1. Create `dreamer/agent.json` Agent Card
2. Create Dockerfile for Dreamer service
3. Deploy Dreamer with `adk deploy cloud_run --a2a`
4. In Executor's config, replace local Dreamer agent with `RemoteA2aAgent` pointing to Dreamer's Agent Card
5. Verify dream loops work over A2A
6. Rollback: Set `AGENT_MODE=local` to revert to in-process Dreamer

### Step 2: Extract Judge as A2A service
1. Create `judge/agent.json` Agent Card (with dual-mode skills: filter, collaborator)
2. Create Dockerfile for Judge service
3. Deploy Judge with `adk deploy cloud_run --a2a`
4. Update Executor and Dreamer to use `RemoteA2aAgent` for Judge
5. Verify awake pipeline (Judge filter → Executor) and sleep loop (Dreamer → Judge collaborator) work over A2A
6. Rollback: Set `AGENT_MODE=local` to revert to in-process Judge

### Step 3: Production hardening
1. Add health check endpoints to each service
2. Configure Cloud Run scaling policies
3. Add structured logging and tracing across A2A calls
4. Document Agent Card schema for third-party replacements

## Open Questions

- **Agent Card versioning**: How to handle Agent Card schema evolution as capabilities grow? A2A spec supports `version` field but no formal versioning protocol.
- **State consistency**: In distributed mode, how to handle partial failures mid-dream-loop? (e.g., Dreamer completes iteration 3, Judge fails on evaluation — should the loop retry or abort?)
- **Cross-region deployment**: Should Dreamer and Judge be co-located in the same region for dream loop latency, or is region-independent deployment acceptable?
