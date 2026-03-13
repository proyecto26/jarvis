## ADDED Requirements

### Requirement: Dreamer A2A server deployment
The Dreamer agent SHALL be deployable as an independent A2A server using ADK's `adk deploy cloud_run --a2a` command, wrapped by `A2aAgentExecutor` which translates A2A protocol tasks/messages to ADK events.

#### Scenario: Dreamer deployed to Cloud Run
- **WHEN** `adk deploy cloud_run --a2a dreamer_agent` is executed
- **THEN** the Dreamer agent SHALL be deployed as a Cloud Run service that accepts A2A JSON-RPC 2.0 requests and serves its Agent Card at `/.well-known/agent.json`

#### Scenario: Dreamer service responds to A2A task
- **WHEN** an A2A `tasks/send` request is sent to the Dreamer service endpoint
- **THEN** the service SHALL process the task through the Dreamer LlmAgent and return dream content as an A2A response message

### Requirement: Judge A2A server deployment
The Judge agent SHALL be deployable as an independent A2A server with both filter and collaborator modes accessible via A2A messages.

#### Scenario: Judge deployed to Cloud Run
- **WHEN** `adk deploy cloud_run --a2a judge_agent` is executed
- **THEN** the Judge agent SHALL be deployed as a Cloud Run service that accepts A2A requests and serves its Agent Card

#### Scenario: Judge A2A server handles filter mode request
- **WHEN** an A2A task message includes filter-mode context (action evaluation request)
- **THEN** the Judge service SHALL respond with a verdict, reasoning, and action weight

#### Scenario: Judge A2A server handles collaborator mode request
- **WHEN** an A2A task message includes collaborator-mode context (dream evaluation request)
- **THEN** the Judge service SHALL respond with dream deepening feedback, depth assessment, and optionally a breakthrough declaration

### Requirement: Dockerfile per agent
Each Trinity agent SHALL have its own Dockerfile that builds an independently deployable container image containing the agent code, dependencies, and A2A server wrapper.

#### Scenario: Dreamer Dockerfile builds successfully
- **WHEN** `docker build -f dreamer/Dockerfile .` is executed
- **THEN** a container image SHALL be produced that can run the Dreamer A2A server on the configured port

#### Scenario: Each Dockerfile is minimal and agent-specific
- **WHEN** an agent's Dockerfile is inspected
- **THEN** it SHALL install only the dependencies required by that specific agent (not the entire triforce package)

### Requirement: Docker Compose for local development
The system SHALL provide a `docker-compose.yml` file that runs all three Trinity agents as separate containers with A2A networking configured.

#### Scenario: Docker Compose starts all agents
- **WHEN** `docker compose up` is executed
- **THEN** three services SHALL start: `dreamer` on port 8001, `judge` on port 8002, and `executor` on port 8003, each running their respective A2A server

#### Scenario: Docker Compose enables inter-agent communication
- **WHEN** all services are running via Docker Compose
- **THEN** the Executor container SHALL be able to reach the Dreamer at `http://dreamer:8001` and the Judge at `http://judge:8002` using Docker's internal DNS

#### Scenario: Docker Compose uses local Agent Cards
- **WHEN** the Docker Compose environment is configured
- **THEN** Agent Cards SHALL be mounted or embedded with URLs pointing to Docker Compose service hostnames

### Requirement: Cloud Run deployment configuration
Each agent service SHALL include Cloud Run deployment configuration specifying memory, CPU, scaling, and environment variables.

#### Scenario: Dreamer Cloud Run config uses higher resources
- **WHEN** the Dreamer service is deployed to Cloud Run
- **THEN** it SHALL be configured with higher memory (at least 1Gi) and CPU allocation to support the heavy model (gemini-2.0-pro)

#### Scenario: Executor Cloud Run config uses minimal resources
- **WHEN** the Executor service is deployed to Cloud Run
- **THEN** it SHALL be configured with lower resource allocation matching its fast model (gemini-2.0-flash) requirements

### Requirement: Health check endpoints
Each A2A agent service SHALL expose a health check endpoint at `/health` that returns HTTP 200 when the service is ready to accept A2A requests.

#### Scenario: Health check returns healthy
- **WHEN** a GET request is made to `/health` on a running agent service
- **THEN** the service SHALL return HTTP 200 with a JSON body containing `{"status": "healthy", "agent": "<agent_name>"}`

#### Scenario: Health check used by Cloud Run
- **WHEN** Cloud Run performs a startup probe
- **THEN** it SHALL use the `/health` endpoint to determine if the service is ready to receive traffic
