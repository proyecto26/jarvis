## 1. Agent Card Definitions

- [ ] 1.1 Create `dreamer/agent.json` Agent Card with name, description, skills (generate_dreams), input/output modes, and configurable URL
- [ ] 1.2 Create `judge/agent.json` Agent Card with dual-mode skills (filter_evaluate, collaborate_dream), input/output modes, and configurable URL
- [ ] 1.3 Create `executor/agent.json` Agent Card with execution skills, text+JSON input/output modes, and configurable URL
- [ ] 1.4 Implement Agent Card URL resolution from environment variables (`DREAMER_A2A_URL`, `JUDGE_A2A_URL`, `EXECUTOR_A2A_URL`) with Docker Compose defaults

## 2. A2A Server Wrappers

- [ ] 2.1 Create Dreamer A2A server entry point using ADK's `A2aAgentExecutor` bridge
- [ ] 2.2 Create Judge A2A server entry point with support for filter and collaborator mode messages
- [ ] 2.3 Create Executor A2A server entry point (for optional full-distributed mode)
- [ ] 2.4 Add `/health` endpoint to each A2A server returning `{"status": "healthy", "agent": "<name>"}`

## 3. RemoteA2aAgent Connections

- [ ] 3.1 Create agent factory module that instantiates local or `RemoteA2aAgent` based on `AGENT_MODE` environment variable
- [ ] 3.2 Wire Executor to use `RemoteA2aAgent` for Dreamer when `AGENT_MODE=a2a`
- [ ] 3.3 Wire Executor to use `RemoteA2aAgent` for Judge when `AGENT_MODE=a2a`
- [ ] 3.4 Wire sleep LoopAgent to use `RemoteA2aAgent` for Judge collaborator in A2A mode
- [ ] 3.5 Support mixed mode: allow individual agents to be remote or local based on which `*_A2A_URL` vars are set

## 4. A2A Message Payload Translation

- [ ] 4.1 Implement state-to-A2A-message serializer: encode session state keys (`dream_seeds`, `judge_verdict`, `action_weight`, etc.) as JSON payload in A2A messages
- [ ] 4.2 Implement A2A-message-to-state deserializer: unpack JSON payload from A2A response into local session state
- [ ] 4.3 Verify `{ variable? }` prompt templates work identically in both local and A2A modes
- [ ] 4.4 Add A2A timeout configuration: 30s default for Judge, 120s for Dreamer

## 5. Error Handling and Graceful Degradation

- [ ] 5.1 Implement Dreamer unavailable fallback: skip dream cycle, log warning, inform user
- [ ] 5.2 Implement Judge unavailable fallback: use default permissive verdict in awake mode, abort dream loop in sleep mode
- [ ] 5.3 Implement A2A timeout handling with degraded-mode behavior matching unreachable-service behavior
- [ ] 5.4 Add structured logging for all A2A calls (request/response, latency, errors)

## 6. Docker Compose Local Development

- [ ] 6.1 Create Dockerfile for Dreamer agent service
- [ ] 6.2 Create Dockerfile for Judge agent service
- [ ] 6.3 Create Dockerfile for Executor agent service (client mode)
- [ ] 6.4 Create `docker-compose.yml` with three services: dreamer (port 8001), judge (port 8002), executor (port 8003) with internal networking
- [ ] 6.5 Configure Agent Cards with Docker Compose hostnames as default URLs
- [ ] 6.6 Add `.env.a2a.example` with all A2A-related environment variables documented

## 7. Cloud Run Deployment

- [ ] 7.1 Create Cloud Run deployment script for Dreamer using `adk deploy cloud_run --a2a`
- [ ] 7.2 Create Cloud Run deployment script for Judge using `adk deploy cloud_run --a2a`
- [ ] 7.3 Configure Cloud Run resource allocation: Dreamer (1Gi+ memory, higher CPU), Executor (lower resources)
- [ ] 7.4 Document Cloud Run deployment steps and Agent Card URL configuration

## 8. Migration Verification

- [ ] 8.1 Create dream loop equivalence test: same seed through local and A2A modes, verify response structure
- [ ] 8.2 Create awake pipeline equivalence test: same request through local and A2A modes, verify verdict structure
- [ ] 8.3 Verify backward compatibility: all Phase 1 tests pass with `AGENT_MODE=local`
- [ ] 8.4 Test partial migration: Dreamer remote + Judge local, verify mixed mode works
- [ ] 8.5 Test rollback: switch from `AGENT_MODE=a2a` to `AGENT_MODE=local` and verify all agents revert to in-process

## 9. Documentation and Cross-Framework Guide

- [ ] 9.1 Document Agent Card schema and required skills for each Trinity role
- [ ] 9.2 Write cross-framework replacement guide: how to build a non-ADK agent that can replace a Trinity member
- [ ] 9.3 Update project README with Phase 3 architecture diagram and deployment instructions
