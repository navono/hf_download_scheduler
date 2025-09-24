# Phase 0: Research - Time Window Download Scheduling

**Feature**: Time Window Download Scheduling (22:00-07:00)
**Branch**: 002-hf-22-00
**Date**: 2025-09-24

## Research Findings

### 1. Time Window Boundary Behavior (07:00 cutoff)

**Decision**: Downloads in progress at 07:00 will continue to completion, but new downloads will not start until the next time window.

**Rationale**:
- Prevents data corruption from abrupt termination
- Maintains download integrity and resume capability
- Aligns with user expectation of completing started downloads
- Existing scheduler already handles graceful completion

**Alternatives considered**:
- Hard stop at 07:00 (rejected): Could corrupt partial downloads
- Pause and resume (rejected): Complex implementation, resume may not work reliably
- Queue remaining for next day (accepted as complementary approach)

### 2. Time Zone Handling Strategy

**Decision**: Use system local time for all time window calculations.

**Rationale**:
- CLI application runs on local system
- Users expect time windows based on their local time
- Simplifies implementation without timezone conversion complexity
- Consistent with existing scheduler behavior (uses local time for schedule execution)

**Alternatives considered**:
- UTC time (rejected): Confusing for users to calculate local→UTC conversion
- Configurable timezone (rejected): Adds complexity for minimal benefit
- User-specified timezone (rejected): Overkill for this use case

### 3. Offline System Behavior During Scheduled Windows

**Decision**: Missed scheduled windows are skipped and will execute in the next available window.

**Rationale**:
- Simple and predictable behavior
- Avoids complex catch-up logic that could overwhelm network
- Users can manually trigger downloads if needed
- System status logs will indicate missed windows for transparency

**Alternatives considered**:
- Queue all missed downloads for next execution (rejected): Could cause network congestion
- Exponential backoff retry (rejected): Too complex for scheduler context)
- User notification system (rejected): Outside scope of current feature)

## Implementation Considerations

### Existing Architecture Analysis

**Current Scheduler Capabilities**:
- Uses `schedule` library for job scheduling
- Supports daily and weekly schedules
- Has database-backed schedule persistence
- Handles concurrent download limits
- Already has status tracking and logging

**Integration Points**:
- Extend `ScheduleConfiguration` model with time window fields
- Add time validation to `SchedulerService._execute_scheduled_download()`
- Create `TimeWindowController` utility class
- Update CLI commands to expose time window configuration

**Database Schema Impact**:
- Add `time_window_start` and `time_window_end` fields to `schedule_configurations`
- Backward compatible - existing schedules without time windows run normally
- Migration script needed for existing installations

### Performance Considerations

**Time Check Overhead**:
- Time validation is O(1) operation - minimal performance impact
- Cache current time to avoid repeated system calls
- Only check time when scheduler runs (once per minute maximum)

**Memory Impact**:
- TimeWindowController is lightweight utility class
- No additional persistent storage required
- Minimal logging overhead for time-based events

## Risk Assessment

**Low Risk**:
- Extending existing, well-tested scheduler architecture
- Time validation is simple logic addition
- Database changes are additive (backward compatible)

**Medium Risk**:
- Edge cases around midnight time window crossing
- Integration with existing download retry logic
- User experience for paused/resumed downloads

**Mitigation Strategies**:
- Comprehensive testing of time boundary conditions
- Graceful degradation if time validation fails
- Clear logging for time-based decisions

## Technology Choices

**Schedule Library Integration**:
- Continue using existing `schedule` library
- Add time window validation before job execution
- Leverage existing job management infrastructure

**Time Handling**:
- Use Python's `datetime` module for time operations
- Local time via `datetime.now()`
- Simple time comparison logic

**Database Changes**:
- Add time window fields as VARCHAR(5) for HH:MM format
- Maintain existing schedule structure for compatibility
- Use default values for backward compatibility

## Conclusion

All NEEDS CLARIFICATION items from the specification have been resolved with practical, implementable decisions. The approach extends the existing architecture minimally while providing the required time window functionality.

**Next Steps**: Proceed to Phase 1 - Design & Contracts