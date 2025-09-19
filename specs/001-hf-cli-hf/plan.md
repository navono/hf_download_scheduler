# Implementation Plan: Scheduled HF CLI Downloader

**Branch**: `[001-hf-cli-hf]` | **Date**: 2025-09-19 | **Spec**: [D:/sourcecode/schedule-download-models/specs/001-hf-cli-hf/spec.md](D:/sourcecode/schedule-download-models/specs/001-hf-cli-hf/spec.md)
**Input**: Feature specification from `/specs/001-hf-cli-hf/spec.md`

## Execution Flow (/plan command scope)
```
1. Load feature spec from Input path
   → If not found: ERROR "No feature spec at {path}"
2. Fill Technical Context (scan for NEEDS CLARIFICATION)
   → Detect Project Type from context (web=frontend+backend, mobile=app+api)
   → Set Structure Decision based on project type
3. Evaluate Constitution Check section below
   → If violations exist: Document in Complexity Tracking
   → If no justification possible: ERROR "Simplify approach first"
   → Update Progress Tracking: Initial Constitution Check
4. Execute Phase 0 → research.md
   → If NEEDS CLARIFICATION remain: ERROR "Resolve unknowns"
5. Execute Phase 1 → contracts, data-model.md, quickstart.md, agent-specific template file
6. Re-evaluate Constitution Check section
   → If new violations: Refactor design, return to Phase 1
   → Update Progress Tracking: Post-Design Constitution Check
7. Plan Phase 2 → Describe task generation approach (DO NOT create tasks.md)
8. STOP - Ready for /tasks command
```

**IMPORTANT**: The /plan command STOPS at step 7. Phases 2-4 are executed by other commands:
- Phase 2: /tasks command creates tasks.md
- Phase 3-4: Implementation execution (manual or via tools)

## Summary
Create a scheduled HF CLI downloader that automatically downloads Hugging Face models based on configurable schedules, using Python 3.12 with SQLite for local data persistence and modular architecture with comprehensive e2e testing.

## Technical Context
**Language/Version**: Python 3.12
**Primary Dependencies**: huggingface_hub, schedule, click, sqlite3
**Storage**: SQLite database for model download tracking
**Testing**: pytest with e2e testing requirements
**Target Platform**: Linux/Windows/macOS CLI application
**Project Type**: single (CLI tool with background service capability)
**Performance Goals**: Handle multiple concurrent downloads efficiently
**Constraints**: Minimal resource usage, graceful error handling
**Scale/Scope**: Single-user tool supporting 10-100 models

## Constitution Check
*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**Simplicity**:
- Projects: [3] (core, cli, tests) - within limit ✓
- Using framework directly? (no wrapper classes) ✓
- Single data model? (SQLite database with model tables) ✓
- Avoiding patterns? (no Repository/UoW without proven need) ✓

**Architecture**:
- EVERY feature as library? (core functionality as library + CLI wrapper) ✓
- Libraries listed: [core (download/schedule logic), cli (interface), tests (validation)]
- CLI per library: [main CLI with --help/--version/--format]
- Library docs: llms.txt format planned? ✓

**Testing (NON-NEGOTIABLE)**:
- RED-GREEN-Refactor cycle enforced? (test MUST fail first) ✓
- Git commits show tests before implementation? ✓
- Order: Contract→Integration→E2E→Unit strictly followed? ✓
- Real dependencies used? (actual DBs, not mocks) ✓
- Integration tests for: new libraries, contract changes, shared schemas? ✓
- FORBIDDEN: Implementation before test, skipping RED phase ✓

**Observability**:
- Structured logging included? ✓
- Frontend logs → backend? (CLI unified stream) ✓
- Error context sufficient? ✓

**Versioning**:
- Version number assigned? (MAJOR.MINOR.BUILD) ✓
- BUILD increments on every change? ✓
- Breaking changes handled? (parallel tests, migration plan) ✓

## Project Structure

### Documentation (this feature)
```
specs/[001-hf-cli-hf]/
├── plan.md              # This file (/plan command output)
├── research.md          # Phase 0 output (/plan command) ✓ COMPLETED
├── data-model.md        # Phase 1 output (/plan command) ✓ COMPLETED
├── quickstart.md        # Phase 1 output (/plan command) ✓ COMPLETED
├── contracts/           # Phase 1 output (/plan command) ✓ COMPLETED
│   ├── cli-contract.md
│   └── database-contract.md
└── tasks.md             # Phase 2 output (/tasks command - NOT created by /plan)
```

### Source Code (repository root)
```
src/
├── hf_downloader/
│   ├── __init__.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── downloader.py     # Main download logic
│   │   ├── scheduler.py      # Schedule management
│   │   ├── database.py       # SQLite operations
│   │   └── config.py         # Configuration handling
│   ├── cli/
│   │   ├── __init__.py
│   │   └── main.py          # CLI interface
│   └── models/
│       ├── __init__.py
│       └── database.py       # Database models
├── config/
│   ├── default.yaml          # Default configuration
│   └── models.json           # Model definitions
└── requirements.txt

tests/
├── contract/
├── integration/
├── e2e/
└── unit/
```

**Structure Decision**: Option 1 (Single project for CLI tool)

## Phase 0: Research ✓ COMPLETED
**Output**: research.md with all NEEDS CLARIFICATION resolved

**Key Decisions Made**:
- HF_TOKEN environment variable for authentication
- `schedule` library for task scheduling
- `click` framework for CLI interface
- SQLite with SQLAlchemy for data persistence
- YAML + JSON hybrid for configuration management
- Python daemon pattern for background processes

## Phase 1: Design & Contracts ✓ COMPLETED
**Output**: data-model.md, /contracts/*, quickstart.md

**Deliverables Created**:
- Complete data model with 4 core entities (Model, ScheduleConfiguration, DownloadSession, SystemConfiguration)
- Full database schema with relationships and constraints
- CLI contract with all commands and options
- Database operations contract with full API
- Comprehensive quickstart guide for users

## Phase 2: Task Planning Approach
*This section describes what the /tasks command will do - DO NOT execute during /plan*

**Task Generation Strategy**:
- Load `/templates/tasks-template.md` as base
- Generate tasks from Phase 1 design docs (contracts, data model, quickstart)
- Each contract → contract test task [P]
- Each entity → model creation task [P] 
- Each user story → integration test task
- Implementation tasks to make tests pass

**Ordering Strategy**:
- TDD order: Tests before implementation 
- Dependency order: Models before services before CLI
- Mark [P] for parallel execution (independent files)

**Estimated Output**: 25-30 numbered, ordered tasks in tasks.md

**IMPORTANT**: This phase is executed by the /tasks command, NOT by /plan

## Phase 3+: Future Implementation
*These phases are beyond the scope of the /plan command*

**Phase 3**: Task execution (/tasks command creates tasks.md)  
**Phase 4**: Implementation (execute tasks.md following constitutional principles)  
**Phase 5**: Validation (run tests, execute quickstart.md, performance validation)

## Complexity Tracking
*Fill ONLY if Constitution Check has violations that must be justified*

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| None identified | N/A | N/A |

## Progress Tracking
*This checklist is updated during execution flow*

**Phase Status**:
- [x] Phase 0: Research complete (/plan command) ✓
- [x] Phase 1: Design complete (/plan command) ✓
- [x] Phase 2: Task planning complete (/plan command - describe approach only) ✓
- [ ] Phase 3: Tasks generated (/tasks command)
- [ ] Phase 4: Implementation complete
- [ ] Phase 5: Validation passed

**Gate Status**:
- [x] Initial Constitution Check: PASS ✓
- [x] Post-Design Constitution Check: PASS ✓
- [x] All NEEDS CLARIFICATION resolved ✓
- [x] Complexity deviations documented ✓

---
*Based on Constitution v2.1.1 - See `/memory/constitution.md`*
