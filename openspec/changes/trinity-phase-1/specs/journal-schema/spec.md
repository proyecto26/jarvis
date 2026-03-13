## ADDED Requirements

### Requirement: Daily journal file structure
The system SHALL store journal entries as structured Markdown files in a `journal/` directory, one file per day, named `YYYY-MM-DD.md`.

#### Scenario: Journal file created for today
- **WHEN** a journal write occurs and no file exists for today's date
- **THEN** a new file `journal/YYYY-MM-DD.md` is created with the full schema template

#### Scenario: Journal file appended for today
- **WHEN** a journal write occurs and a file already exists for today
- **THEN** the new content is appended to the appropriate section of the existing file

### Requirement: Journal entry schema sections
Each daily journal file SHALL contain the following sections: Metadata, Dreams (Dreamer output), Judgments (Judge output), Executions (Executor output), Learnings, Judge Self-Mutations, Open Questions, and Connections.

#### Scenario: Complete schema present in new entry
- **WHEN** a new daily journal file is created
- **THEN** all eight sections are present as Markdown headers with empty content

### Requirement: Metadata section contents
The Metadata section SHALL include: date, mode cycles count (awake/reflective/sleep), active skills list, and dominant theme.

#### Scenario: Metadata populated
- **WHEN** a journal entry is finalized for the day
- **THEN** the Metadata section reflects the actual mode cycles, skills used, and primary theme of the day

### Requirement: Dreams section records Dreamer output
The Dreams section SHALL record each dream cycle with: seed that triggered it, branches explored, depth reached, and breakthrough (if any).

#### Scenario: Dream cycle recorded
- **WHEN** a sleep mode cycle completes
- **THEN** the Dreams section is updated with the cycle's seeds, branches, depth, and any breakthrough

### Requirement: Judgments section records Judge decisions
The Judgments section SHALL record each significant judgment with: action description, action weight, verdict, reasoning, and any self-mutations triggered.

#### Scenario: High-weight judgment recorded
- **WHEN** the Judge makes a decision with action_weight >= 6
- **THEN** the Judgments section is updated with the full decision record including original action, verdict, reasoning, and any belief changes

### Requirement: Executions section records Executor actions
The Executions section SHALL record each action with: action description, status (completed/failed/partial), outcome description, and artifacts produced.

#### Scenario: Execution recorded
- **WHEN** the Executor completes an action
- **THEN** the Executions section is updated with action, status, outcome, and any artifacts

### Requirement: Judge Self-Mutations section
The Judge Self-Mutations section SHALL record any changes to the Judge's belief model, including: belief text, whether it was added/updated/removed, strength score, and timestamp.

#### Scenario: Mutation recorded
- **WHEN** the Judge updates `judge_beliefs.json`
- **THEN** the Self-Mutations section of today's journal is updated with the change details

### Requirement: Journal Pydantic schema
The system SHALL define Pydantic models in `triforce/memory/schema.py` for: `JournalEntry`, `DreamCycle`, `Judgment`, `Execution`, `Learning`, `BeliefMutation`, and `JournalMetadata`.

#### Scenario: Schema validation
- **WHEN** journal data is prepared for writing
- **THEN** it is validated against the Pydantic model before being written to the Markdown file

### Requirement: write_journal_entry ADK tool
The system SHALL provide a `write_journal_entry` ADK tool that accepts a section name and content dict, validates it against the schema, and appends it to today's journal file.

#### Scenario: Tool writes to correct section
- **WHEN** an agent calls `write_journal_entry` with section `dreams` and a dream cycle dict
- **THEN** the content is validated and appended to the Dreams section of today's journal

### Requirement: Journal directory gitignored
The `journal/` directory SHALL be added to `.gitignore` since it contains personal data. A `journal/.gitkeep` file SHALL be committed to preserve the directory structure.

#### Scenario: Journal excluded from git
- **WHEN** a developer runs `git status` after journal entries are written
- **THEN** journal files do not appear as untracked or modified

### Requirement: Judge beliefs file structure
The `memory/judge_beliefs.json` file SHALL contain a JSON object with a `beliefs` array, where each belief has: `id` (string), `text` (string), `strength` (float 0.0-1.0), `created_at` (ISO datetime), `updated_at` (ISO datetime), and `source_decision` (string reference to the judgment that created it).

#### Scenario: Beliefs file structure
- **WHEN** `judge_beliefs.json` is read
- **THEN** it contains a valid JSON object with a `beliefs` array of belief objects matching the defined structure

#### Scenario: New beliefs file initialization
- **WHEN** the system starts and no `judge_beliefs.json` exists
- **THEN** an empty beliefs file is created with `{"beliefs": []}` content
