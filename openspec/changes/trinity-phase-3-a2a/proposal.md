## Why

Phase 1 proves the Trinity architecture works as a single-process ADK system — Dreamer, Judge, and Executor communicate via session state within one runtime. But the vision for Jarvis demands independent scalability: the Dreamer needs a heavy model and runs on Temporal schedules (no real-time latency requirement), the Judge evaluates asynchronously, and the Executor must stay fast on the frontline. Phase 3 introduces the Agent-to-Agent (A2A) protocol so each Trinity agent can be deployed as an independent service, discovered via Agent Cards, and called over JSON-RPC 2.0 — enabling distributed deployment, independent scaling, and cross-framework agent replacement.

## What Changes

- Deploy each Trinity agent (Dreamer, Judge, Executor) as an independent A2A-compatible service with its own Agent Card (`agent.json`)
- Implement `RemoteA2aAgent` connections so agents discover and call each other over the A2A protocol (JSON-RPC 2.0 over HTTPS)
- Dreamer becomes the first A2A service: heavy model, Temporal-scheduled, no real-time latency requirement — ideal candidate for remote deployment
- Judge becomes the second A2A service: medium model, event-driven, callable remotely by Executor or Dreamer
- Executor stays as the frontline A2A client: fast model, orchestrates calls to Dreamer and Judge as remote sub-agents
- Define Agent Card schemas for each Trinity agent describing capabilities, skills, input/output modes
- Deployment strategy using Cloud Run (production) and local Docker Compose (development)
- Enable cross-framework agent replacement: any A2A-compatible agent can replace a Trinity member as long as it serves a compatible Agent Card

## Capabilities

### New Capabilities
- `a2a-agent-cards`: Agent Card definitions (agent.json) for each Trinity agent — name, description, skills, input/output modes, URL, and capabilities metadata
- `a2a-service-deployment`: Deployment configuration for Trinity agents as independent A2A servers — Dockerfiles, Cloud Run configs, Docker Compose for local development
- `a2a-remote-connections`: RemoteA2aAgent wiring so Executor discovers and calls Dreamer/Judge remotely, and Dreamer can call Judge within dream loops
- `a2a-migration-strategy`: Phased migration path from Phase 1 (same-process ADK) to Phase 3 (distributed A2A services) — Dreamer first, then Judge, Executor last

### Modified Capabilities
- `operating-modes`: Communication model changes from ADK session state (Phase 1) to A2A protocol (Phase 3) — mode routing now crosses service boundaries via JSON-RPC 2.0

## Impact

- **New code**: A2A server wrappers, Agent Card JSON files, Docker/Cloud Run deployment configs, RemoteA2aAgent connection setup
- **Dependencies**: `a2a-sdk`, Docker, Cloud Run SDK (optional for deployment)
- **Infrastructure**: Each agent becomes a deployable service (Cloud Run or Docker container) with its own endpoint
- **Existing code**: `triforce/` package restructured — agents separated into independently deployable modules while maintaining backward compatibility for single-process mode
- **Protocol**: Inter-agent communication shifts from in-process session state to A2A JSON-RPC 2.0 over HTTPS
- **Interoperability**: Any A2A-compatible agent (regardless of framework — ADK, LangChain, CrewAI, custom) can replace a Trinity member
