# Tasks: Time Window Download Scheduling

**Input**: Design documents from `/specs/002-hf-22-00/`
**Prerequisites**: plan.md (required), research.md, data-model.md, contracts/, quickstart.md
**Branch**: 002-hf-22-00

## Execution Flow (main)
```
1. Load plan.md from feature directory
   → ✓ Found implementation plan for time window scheduling
   → Extract: Python 3.11+, SQLAlchemy, schedule library, existing CLI structure
2. Load design documents:
   → data-model.md: Extended ScheduleConfiguration + TimeWindow class
   → contracts/time_window_api.yaml: 4 endpoints, validation schemas
   → research.md: Decisions on boundary behavior, timezone, offline handling
   → quickstart.md: User scenarios and CLI command examples
3. Generate tasks by category:
   → Setup: Database migration, time window utility
   → Tests: Contract tests, integration tests, validation tests
   → Core: Model extension, time window service, scheduler integration
   → Integration: CLI commands, configuration updates, logging
   → Polish: Unit tests, documentation, optimization
4. Apply task rules:
   → Different files = mark [P] for parallel
   → Same file = sequential (no [P])
   → Tests before implementation (TDD)
5. Number tasks sequentially (T001, T002...)
6. Generate dependency graph
7. Create parallel execution examples
8. Validate task completeness:
   → ✓ All contracts have tests
   → ✓ All entities have models
   → ✓ All endpoints implemented
```

## Format: `[ID] [P?] Description`
- **[P]**: Can run in parallel (different files, no dependencies)
- Include exact file paths in descriptions

## Phase 3.1: Setup & Migration

### Database Schema Extension
- [ ] T001 Create database migration script for time window fields in `scripts/migrations/add_time_window_fields.py`
- [ ] T002 [P] Extend ScheduleConfiguration model with time window fields in `src/hf_downloader/models/database.py`

### Time Window Utility
- [ ] T003 [P] Create TimeWindow utility class in `src/hf_downloader/services/time_window.py`

## Phase 3.2: Tests First (TDD) ⚠️ MUST COMPLETE BEFORE 3.3

### Contract Tests
- [ ] T004 [P] Contract test GET /api/v1/schedules/{id}/time-window in `tests/contract/test_time_window_get.py`
- [ ] T005 [P] Contract test PUT /api/v1/schedules/{id}/time-window in `tests/contract/test_time_window_put.py`
- [ ] T006 [P] Contract test DELETE /api/v1/schedules/{id}/time-window in `tests/contract/test_time_window_delete.py`
- [ ] T007 [P] Contract test GET /api/v1/time-window/status in `tests/contract/test_time_window_status.py`
- [ ] T008 [P] Contract test POST /api/v1/time-window/validate in `tests/contract/test_time_window_validate.py`

### Integration Tests
- [ ] T009 [P] Integration test time window download scheduling in `tests/integration/test_time_window_scheduling.py`
- [ ] T010 [P] Integration test midnight crossing logic in `tests/integration/test_midnight_crossing.py`
- [ ] T011 [P] Integration test boundary behavior at 07:00 cutoff in `tests/integration/test_boundary_behavior.py`

### Unit Tests
- [ ] T012 [P] Unit test TimeWindow time validation in `tests/unit/test_time_window_validation.py`
- [ ] T013 [P] Unit test TimeWindow current time check in `tests/unit/test_time_window_current_check.py`

## Phase 3.3: Core Implementation (ONLY after tests are failing)

### Model Extensions
- [ ] T014 Add time window fields to ScheduleConfiguration model (already defined in T002, implement validation)

### Time Window Service
- [ ] T015 [P] Implement TimeWindow class time validation in `src/hf_downloader/services/time_window.py`
- [ ] T016 [P] Implement TimeWindow class current time check in `src/hf_downloader/services/time_window.py`
- [ ] T017 [P] Implement TimeWindow class midnight crossing logic in `src/hf_downloader/services/time_window.py`

### Scheduler Integration
- [ ] T018 Modify SchedulerService._execute_scheduled_download() to check time windows in `src/hf_downloader/services/scheduler.py`
- [ ] T019 Add time window decision logging to SchedulerService in `src/hf_downloader/services/scheduler.py`

### Database Operations
- [ ] T020 Add time window CRUD methods to DatabaseManager in `src/hf_downloader/models/database.py`
- [ ] T021 Implement time window validation in database operations in `src/hf_downloader/models/database.py`

## Phase 3.4: Integration

### CLI Commands
- [ ] T022 [P] Add time window CLI commands in `src/hf_downloader/cli/schedule_commands.py`
- [ ] T023 [P] Add time window status CLI command in `src/hf_downloader/cli/time_window_commands.py`
- [ ] T024 [P] Add time window validation CLI command in `src/hf_downloader/cli/time_window_commands.py`

### Configuration Integration
- [ ] T025 Extend Config class with time window settings in `src/hf_downloader/core/config.py`
- [ ] T026 Update default config.yaml with time window example in `config/config.yaml`

### API Endpoints
- [ ] T027 Implement GET /api/v1/schedules/{id}/time-window endpoint
- [ ] T028 Implement PUT /api/v1/schedules/{id}/time-window endpoint
- [ ] T029 Implement DELETE /api/v1/schedules/{id}/time-window endpoint
- [ ] T030 Implement GET /api/v1/time-window/status endpoint
- [ ] T031 Implement POST /api/v1/time-window/validate endpoint

### Error Handling and Logging
- [ ] T032 Add time window specific error handling in `src/hf_downloader/services/scheduler.py`
- [ ] T033 Add time window event logging in `src/hf_downloader/services/scheduler.py`
- [ ] T034 Add time window audit logging to database operations in `src/hf_downloader/models/database.py`

## Phase 3.5: Polish

### Performance and Optimization
- [ ] T035 Optimize time window check performance (cache current time) in `src/hf_downloader/services/time_window.py`
- [ ] T036 Add database indexes for time window queries in `scripts/migrations/add_time_window_indexes.py`

### Documentation and Examples
- [ ] T037 [P] Update CLI help text for time window commands in `src/hf_downloader/cli/schedule_commands.py`
- [ ] T038 [P] Add time window examples to README.md in `README.md`
- [ ] T039 [P] Create time window migration guide in `docs/time_window_migration.md`

### Final Testing
- [ ] T040 [P] Run comprehensive integration test following quickstart.md scenarios
- [ ] T041 [P] Performance test time window validation overhead
- [ ] T042 [P] Test backward compatibility with existing schedules

## Dependencies

### Critical Dependencies
- T001 must complete before T002 (migration before model changes)
- T004-T013 must complete before T014-T034 (TDD: tests before implementation)
- T015-T017 must complete before T018 (TimeWindow class before scheduler integration)

### Parallel Execution Groups
```
# Group 1: Can run together (different files)
T004, T005, T006, T007, T008  # Contract tests
T009, T010, T011              # Integration tests
T012, T013                    # Unit tests
T015, T016, T017              # TimeWindow service methods

# Group 2: Sequential dependencies
T001 → T002 → T020 → T021       # Database model and operations
T018 → T019 → T032 → T033      # Scheduler integration and logging
T022 → T023 → T024             # CLI commands
```

## Validation Checklist
- [ ✓] All contracts have corresponding tests (T004-T008)
- [ ✓] All entities have model tasks (ScheduleConfiguration: T002, TimeWindow: T003)
- [ ✓] All tests come before implementation
- [ ✓] Parallel tasks truly independent
- [ ✓] Each task specifies exact file path
- [ ✓] No task modifies same file as another [P] task

## Implementation Notes

### Key Design Decisions from Research
- **Boundary behavior**: Downloads in progress at 07:00 continue to completion
- **Time zone handling**: Use system local time (no conversion)
- **Offline behavior**: Missed windows are skipped (no catch-up)
- **Midnight crossing**: Support windows like 22:00-07:00

### Integration Points
- Extend existing `ScheduleConfiguration` model (backward compatible)
- Add time check to `SchedulerService._execute_scheduled_download()`
- Create new CLI commands under existing `hf-downloader schedule` namespace
- Extend configuration system with time window settings

### Testing Strategy
- Contract tests for API endpoints (T004-T008)
- Integration tests for user scenarios (T009-T011)
- Unit tests for validation logic (T012-T013)
- Performance tests for time check overhead (T041)
- Backward compatibility tests (T042)

### Success Criteria
- Time windows restrict download execution to specified hours
- Existing schedules continue working without modification
- CLI commands provide complete time window management
- API endpoints support all time window operations
- Performance impact is minimal (<1ms per check)