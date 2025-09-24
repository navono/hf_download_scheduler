# Implementation Plan: Time Window Download Scheduling

**Branch**: `002-hf-22-00` | **Date**: 2025-09-24 | **Spec**: `/specs/002-hf-22-00/spec.md`
**Input**: Feature specification from `/specs/002-hf-22-00/spec.md`

## Execution Flow (/plan command scope)
```
1. Load feature spec from Input path
   → ✓ Found and analyzed scheduled download feature spec
2. Fill Technical Context (scan for NEEDS CLARIFICATION)
   → Detected Python CLI project with existing scheduler
   → Set Structure Decision: extend existing single project structure
3. Evaluate Constitution Check section below
   → No violations detected - extending existing architecture
   → Update Progress Tracking: Initial Constitution Check
4. Execute Phase 0 → research.md
   → Addressing 3 NEEDS CLARIFICATION items from spec
5. Execute Phase 1 → contracts, data-model.md, quickstart.md, agent-specific template file
6. Re-evaluate Constitution Check section
   → Verify no new violations introduced
   → Update Progress Tracking: Post-Design Constitution Check
7. Plan Phase 2 → Describe task generation approach
8. STOP - Ready for /tasks command
```

**IMPORTANT**: The /plan command STOPS at step 7. Phases 2-4 are executed by other commands:
- Phase 2: /tasks command creates tasks.md
- Phase 3-4: Implementation execution (manual or via tools)

## Summary
The feature requires adding time window control (22:00-07:00) to the existing HF downloader scheduler. The system must automatically start downloads only during this time window, process queue items sequentially, and continue with the next item after each completion. This extends the existing scheduler service with time-based constraints.

## Technical Context
**Language/Version**: Python 3.11+ (existing codebase)
**Primary Dependencies**: schedule, SQLAlchemy, huggingface_hub, loguru (existing)
**Storage**: SQLite (existing database with schedule_configurations table)
**Testing**: pytest (existing test structure)
**Target Platform**: Linux server (CLI daemon application)
**Project Type**: Single project (CLI tool with services)
**Performance Goals**: Minimal CPU/memory overhead for time checks
**Constraints**: Must integrate with existing scheduler architecture
**Scale/Scope**: Single daemon managing multiple download sessions

## Constitution Check
*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**Simplicity**:
- Projects: [1] (extend existing hf_downloader project)
- Using framework directly? (extending existing schedule library usage)
- Single data model? (extending existing ScheduleConfiguration model)
- Avoiding patterns? (no new patterns - using existing service architecture)

**Architecture**:
- EVERY feature as library? (extending existing scheduler service library)
- Libraries listed: [scheduler service (extension), time window controller]
- CLI per library: [existing CLI with new time-window commands]
- Library docs: llms.txt format planned?

**Testing (NON-NEGOTIABLE)**:
- RED-GREEN-Refactor cycle enforced? (will follow existing test patterns)
- Git commits show tests before implementation? (will follow constitutional requirements)
- Order: Contract→Integration→E2E→Unit strictly followed? (following existing structure)
- Real dependencies used? (using existing SQLite database for tests)
- Integration tests for: new scheduler methods, time window validation
- FORBIDDEN: Implementation before test, skipping RED phase

**Observability**:
- Structured logging included? (extending existing loguru logging)
- Frontend logs → backend? (CLI-only, unified logging stream)
- Error context sufficient? (will add time-specific error messages)

**Versioning**:
- Version number assigned? (will increment existing version)
- BUILD increments on every change? (following existing versioning)
- Breaking changes handled? (backward-compatible extension)

## Project Structure

### Documentation (this feature)
```
specs/[###-feature]/
├── plan.md              # This file (/plan command output)
├── research.md          # Phase 0 output (/plan command)
├── data-model.md        # Phase 1 output (/plan command)
├── quickstart.md        # Phase 1 output (/plan command)
├── contracts/           # Phase 1 output (/plan command)
└── tasks.md             # Phase 2 output (/tasks command - NOT created by /plan)
```

### Source Code (repository root)
```
# Option 1: Single project (DEFAULT)
src/
├── models/
├── services/
├── cli/
└── lib/

tests/
├── contract/
├── integration/
└── unit/

# Option 2: Web application (when "frontend" + "backend" detected)
backend/
├── src/
│   ├── models/
│   ├── services/
│   └── api/
└── tests/

frontend/
├── src/
│   ├── components/
│   ├── pages/
│   └── services/
└── tests/

# Option 3: Mobile + API (when "iOS/Android" detected)
api/
└── [same as backend above]

ios/ or android/
└── [platform-specific structure]
```

**Structure Decision**: Option 1 (DEFAULT) - extending existing single project structure

## Phase 0: Outline & Research

**Research tasks for NEEDS CLARIFICATION items**:
1. Research time window boundary behavior (what happens at 07:00?)
2. Research time zone handling strategy
3. Research offline system behavior during scheduled windows

**Consolidate findings** in `research.md` using format:
- Decision: [what was chosen]
- Rationale: [why chosen]
- Alternatives considered: [what else evaluated]

**Output**: research.md with all NEEDS CLARIFICATION resolved

## Phase 1: Design & Contracts
*Prerequisites: research.md complete*

1. **Extract entities from feature spec** → `data-model.md`:
   - Extend ScheduleConfiguration with time window fields
   - Add TimeWindow entity for validation
   - Define state transitions for time-based scheduling

2. **Generate API contracts** from functional requirements:
   - Time window validation endpoints
   - Schedule status queries with time information
   - Output OpenAPI/GraphQL schema to `/contracts/`

3. **Generate contract tests** from contracts:
   - Time window validation tests
   - Schedule execution within time bounds
   - Tests must fail (no implementation yet)

4. **Extract test scenarios** from user stories:
   - Time-based download start/stop scenarios
   - Queue continuation within time window
   - Quickstart test = validation steps

5. **Update agent file incrementally**:
   - Add time window scheduling concepts
   - Preserve existing context
   - Update recent changes

**Output**: data-model.md, /contracts/*, failing tests, quickstart.md, agent-specific file

## Phase 2: Task Planning Approach
*This section describes what the /tasks command will do - DO NOT execute during /plan*

**Task Generation Strategy**:
- Load `/templates/tasks-template.md` as base
- Generate tasks from Phase 1 design docs (contracts, data model, quickstart)
- Time window validation contract → contract test task [P]
- ScheduleConfiguration extension → model migration task [P]
- Time window service → implementation task
- Each user story → integration test task
- Implementation tasks to make tests pass

**Ordering Strategy**:
- TDD order: Tests before implementation
- Database migration before service changes
- Service extension before CLI updates
- Mark [P] for parallel execution (independent files)

**Estimated Output**: 20-25 numbered, ordered tasks in tasks.md

**IMPORTANT**: This phase is executed by the /tasks command, NOT by /plan

## Phase 3+: Future Implementation
*These phases are beyond the scope of the /plan command*

**Phase 3**: Task execution (/tasks command creates tasks.md)  
**Phase 4**: Implementation (execute tasks.md following constitutional principles)  
**Phase 5**: Validation (run tests, execute quickstart.md, performance validation)

## Complexity Tracking
*No constitutional violations detected - no complexity tracking required*


## Progress Tracking
*This checklist is updated during execution flow*

**Phase Status**:
- [x] Phase 0: Research complete (/plan command)
- [x] Phase 1: Design complete (/plan command)
- [x] Phase 2: Task planning complete (/plan command - describe approach only)
- [x] Phase 3: Tasks generated (/tasks command)
- [ ] Phase 4: Implementation complete
- [ ] Phase 5: Validation passed

**Gate Status**:
- [x] Initial Constitution Check: PASS
- [x] Post-Design Constitution Check: PASS
- [x] All NEEDS CLARIFICATION resolved
- [x] Complexity deviations documented

**Artifacts Generated**:
- [x] research.md - Resolved all NEEDS CLARIFICATION items
- [x] data-model.md - Extended ScheduleConfiguration with time window fields
- [x] contracts/time_window_api.yaml - OpenAPI specification
- [x] quickstart.md - User validation scenarios and setup guide
- [x] tasks.md - 42 detailed implementation tasks following TDD principles

---
*Based on Constitution v2.1.1 - See `/memory/constitution.md`*