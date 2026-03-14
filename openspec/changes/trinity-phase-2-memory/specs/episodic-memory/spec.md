## ADDED Requirements

### Requirement: EpisodicMemory class
The system SHALL implement an `EpisodicMemory` class in `triforce/memory/episodic.py` that wraps Mem0 with ChromaDB as the embedded vector backend.

#### Scenario: EpisodicMemory initialization
- **WHEN** `EpisodicMemory()` is instantiated
- **THEN** it creates a Mem0 client configured with ChromaDB embedded (persisted to `CHROMA_PATH`) and the configured embedding backend (Ollama or Gemini)

#### Scenario: Ollama embedding backend
- **WHEN** `EMBEDDING_BACKEND=ollama` (default) and `OLLAMA_HOST` is set
- **THEN** `EpisodicMemory` uses Ollama `nomic-embed-text` for all embedding operations

#### Scenario: Gemini embedding backend
- **WHEN** `EMBEDDING_BACKEND=gemini` and `GOOGLE_API_KEY` is set
- **THEN** `EpisodicMemory` uses Gemini embedding API for all embedding operations

### Requirement: Journal entry indexing
The system SHALL index each `JournalEntry` section into Mem0 after a successful write.

#### Scenario: DreamCycle section indexing
- **WHEN** `index_journal_entry(entry)` is called with a `JournalEntry` that contains a `DreamCycle`
- **THEN** each idea in the DreamCycle is indexed as a separate Mem0 memory with metadata: `date`, `section="dream"`, `cognitive_load_score`

#### Scenario: Judgment section indexing
- **WHEN** `index_journal_entry(entry)` is called with a `JournalEntry` containing `Judgment` objects
- **THEN** each judgment is indexed with metadata: `date`, `section="judgment"`, `action_weight`, `verdict`

#### Scenario: Execution section indexing
- **WHEN** `index_journal_entry(entry)` is called with a `JournalEntry` containing `Execution` objects
- **THEN** each execution is indexed with metadata: `date`, `section="execution"`, `outcome`

### Requirement: Hybrid retrieval
The system SHALL support hybrid semantic + BM25 retrieval via Mem0.

#### Scenario: Episodic recall with top-k results
- **WHEN** `recall_similar(query, top_k=5)` is called
- **THEN** it returns up to `top_k` `EpisodicResult` objects ranked by relevance, formatted as ActMem-style reasoning chains

#### Scenario: EpisodicResult reasoning chain format
- **WHEN** `recall_similar()` returns results
- **THEN** each `EpisodicResult` SHALL include: `episode_id`, `date`, `section`, `content`, `relevance_score`, `reasoning_chain` (formatted as "Context: X → Implication: Y → Confidence: Z"), `source_anchor`

### Requirement: Reinforcement on retrieval
The system SHALL support resetting the FadeMem decay clock when a memory is found relevant.

#### Scenario: Memory reinforcement
- **WHEN** `reinforce(entry_id)` is called
- **THEN** the FadeMem strength for that entry is reset to 1.0 (decay clock restart)

### Requirement: ADK tool upgrade
The `recall_similar_decisions` ADK tool SHALL use `EpisodicMemory.recall_similar()` instead of scanning the flat JSON belief store.

#### Scenario: Tool returns reasoning chains
- **WHEN** the Judge calls `recall_similar_decisions(query="should I trust external APIs?")` during awake mode
- **THEN** the tool returns a formatted string of relevant past decisions as reasoning chains, not raw JSON
