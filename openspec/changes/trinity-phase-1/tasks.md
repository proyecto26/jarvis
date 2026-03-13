## 1. Project Scaffolding

- [ ] 1.1 Create `pyproject.toml` with project metadata, Python 3.11+ requirement, and dependencies: `google-adk`, `pydantic`, `python-dotenv`
- [ ] 1.2 Create `triforce/__init__.py` with package-level exports
- [ ] 1.3 Create `triforce/config.py` with environment-based model configuration (`DREAMER_MODEL`, `JUDGE_MODEL`, `EXECUTOR_MODEL` with defaults)
- [ ] 1.4 Create `.env.example` with required environment variables (Gemini API key, model names)
- [ ] 1.5 Add `journal/` to `.gitignore` and create `journal/.gitkeep`
- [ ] 1.6 Create `memory/judge_beliefs.json` with initial empty structure `{"beliefs": []}`

## 2. State Tools

- [ ] 2.1 Create `triforce/tools/__init__.py`
- [ ] 2.2 Implement `append_to_state` tool in `triforce/tools/state_tools.py` — accepts key name and value, appends to list keys or sets scalar keys in session state
- [ ] 2.3 Verify `append_to_state` handles both list append and scalar set operations

## 3. Dreamer Agent

- [ ] 3.1 Create `triforce/agents/dreamer/__init__.py`
- [ ] 3.2 Define Dreamer instruction template in `triforce/agents/dreamer/prompts.py` with `{ dream_seeds? }` and `{ dream_deepening? }` placeholders
- [ ] 3.3 Implement Dreamer agent in `triforce/agents/dreamer/agent.py` — ADK `Agent` with high-reasoning model, `append_to_state` as only tool

## 4. Judge Agent

- [ ] 4.1 Create `triforce/agents/judge/__init__.py`
- [ ] 4.2 Define `FILTER_PROMPT` in `triforce/agents/judge/prompts.py` — evaluates action weight, ethics, alignment, reversibility; outputs verdict to state
- [ ] 4.3 Define `COLLABORATOR_PROMPT` in `triforce/agents/judge/prompts.py` — connects ideas to experience, detects breakthroughs, uses exit_loop
- [ ] 4.4 Implement Judge filter agent in `triforce/agents/judge/agent.py` — ADK `Agent` with filter prompt, `append_to_state` and `recall_similar_decisions` tools
- [ ] 4.5 Implement Judge collaborator agent in `triforce/agents/judge/agent.py` — ADK `Agent` with collaborator prompt, `append_to_state` and `exit_loop` tools

## 5. Executor Agent

- [ ] 5.1 Create `triforce/agents/executor/__init__.py`
- [ ] 5.2 Define Executor instruction template in `triforce/agents/executor/prompts.py` with `{ judge_verdict? }` and `{ executor_guidance? }` placeholders
- [ ] 5.3 Implement Executor agent in `triforce/agents/executor/agent.py` — ADK `Agent` with fast model, reads Judge verdict from state, records execution outcomes

## 6. Operating Modes

- [ ] 6.1 Create `triforce/modes/__init__.py`
- [ ] 6.2 Implement awake mode in `triforce/modes/awake.py` — ADK `SequentialAgent` named `awake_pipeline` with sub-agents `[judge_filter, executor]`
- [ ] 6.3 Implement sleep mode in `triforce/modes/sleep.py` — ADK `LoopAgent` named `dream_state` with sub-agents `[dreamer, judge_collaborator]`, `max_iterations=8`
- [ ] 6.4 Implement reflective mode in `triforce/modes/reflective.py` — ADK `LlmAgent` named `reflective_session` with Judge reasoning and journal context access

## 7. Root Dispatcher

- [ ] 7.1 Implement root agent in `triforce/root_agent.py` — ADK `LlmAgent` named `jarvis` with sub-agents `[awake_pipeline, dream_state, reflective_session]` and mode-routing instruction
- [ ] 7.2 Create `triforce/__main__.py` entry point for `python -m triforce` execution

## 8. Journal Memory System

- [ ] 8.1 Create `triforce/memory/__init__.py`
- [ ] 8.2 Define Pydantic models in `triforce/memory/schema.py` — `JournalEntry`, `DreamCycle`, `Judgment`, `Execution`, `Learning`, `BeliefMutation`, `JournalMetadata`
- [ ] 8.3 Implement journal file I/O in `triforce/memory/journal.py` — create/load daily Markdown files, append to sections, atomic write pattern
- [ ] 8.4 Implement beliefs load/save in `triforce/memory/beliefs.py` — read/write `judge_beliefs.json`, add/update/remove beliefs with strength scores and timestamps
- [ ] 8.5 Implement `write_journal_entry` ADK tool in `triforce/tools/journal_tools.py` — validates against schema, appends to today's journal
- [ ] 8.6 Implement `read_journal` ADK tool in `triforce/tools/journal_tools.py` — reads today's journal or a specific date's entry

## 9. Integration and Verification

- [ ] 9.1 Verify `adk run triforce` discovers and starts the root agent
- [ ] 9.2 Test awake mode: send a request → Judge evaluates → Executor responds
- [ ] 9.3 Test sleep mode: trigger "dream" → LoopAgent cycles Dreamer/Judge → exit_loop on breakthrough or max iterations
- [ ] 9.4 Test reflective mode: trigger "reflect" → reflective session processes recent context
- [ ] 9.5 Verify journal entries are created and structured correctly after each mode
- [ ] 9.6 Verify `judge_beliefs.json` updates after high-weight judgments
