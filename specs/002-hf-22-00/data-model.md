# Phase 1: Data Model - Time Window Download Scheduling

**Feature**: Time Window Download Scheduling (22:00-07:00)
**Branch**: 002-hf-22-00
**Date**: 2025-09-24

## Extended Entities

### 1. ScheduleConfiguration (Extended)

**Purpose**: Define when downloads should occur with optional time window constraints

**Fields**:
```python
class ScheduleConfiguration(Base):
    # Existing fields...
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    type = Column(String(20), nullable=False)  # daily, weekly
    time = Column(String(5), nullable=False)  # HH:MM format
    day_of_week = Column(Integer, nullable=True)
    enabled = Column(Boolean, default=True)
    max_concurrent_downloads = Column(Integer, default=1)

    # NEW: Time window fields
    time_window_start = Column(String(5), nullable=True)  # HH:MM format
    time_window_end = Column(String(5), nullable=True)    # HH:MM format
    time_window_enabled = Column(Boolean, default=False)   # Enable time window restrictions
```

**Validation Rules**:
- `time_window_start` and `time_window_end` must both be present or both null
- Time format must be HH:MM with valid hours (00-23) and minutes (00-59)
- If `time_window_enabled` is True, both time fields must be provided
- Time windows can cross midnight (e.g., 22:00 to 07:00)

**Relationships**:
- No new relationships - extends existing model
- Backward compatible with existing schedules

### 2. TimeWindow (New Utility Class)

**Purpose**: Validate time window constraints and check current time eligibility

**Fields**:
```python
@dataclass
class TimeWindow:
    start_time: str  # HH:MM format
    end_time: str    # HH:MM format
    enabled: bool = False

    def __post_init__(self):
        self._validate_time_format(self.start_time)
        self._validate_time_format(self.end_time)

    def _validate_time_format(self, time_str: str):
        # Validate HH:MM format
        pass

    def is_current_time_in_window(self) -> bool:
        # Check if current time is within the window
        pass

    def get_next_window_start(self) -> datetime:
        # Calculate when next window starts
        pass

    def get_window_end(self) -> datetime:
        # Calculate when current window ends
        pass
```

**State Transitions**:

### ScheduleConfiguration States

**Existing States**:
- `enabled=True/False` - Schedule is active or inactive

**New Time Window States**:
- `time_window_enabled=False` - No time restrictions (existing behavior)
- `time_window_enabled=True` - Time restrictions apply
- `time_window_start + time_window_end` - Define the active window

**Time-Based State Machine**:
```
[Schedule Enabled] → [Time Window Enabled] → [Current Time Check] → [Allow/Deny Download]
     ↓                                    ↓
[Schedule Disabled] ← ← ← ← ← ← ← ← ← ← ← ← ← ← ← ← ← ← ← ← ← ← ←
```

**Download Eligibility Flow**:
1. Check if schedule is enabled
2. Check if time window is enabled
3. If time window enabled, check current time
4. Allow download if all checks pass
5. Log time-based decisions for audit trail

## Database Migration Requirements

### Schema Changes

**Add to schedule_configurations table**:
```sql
ALTER TABLE schedule_configurations
ADD COLUMN time_window_start VARCHAR(5) NULL,
ADD COLUMN time_window_end VARCHAR(5) NULL,
ADD COLUMN time_window_enabled BOOLEAN DEFAULT FALSE;
```

**Migration Script**:
```python
def upgrade_time_window_fields():
    """Add time window fields to existing schedule_configurations table."""
    # Add new columns with default values
    # Existing schedules keep working (time_window_enabled=False)
    pass

def validate_time_format_constraint():
    """Add CHECK constraint for time format validation."""
    # Ensure HH:MM format for time window fields
    pass
```

**Backward Compatibility**:
- Existing schedules default to `time_window_enabled=False`
- No disruption to current functionality
- New features are opt-in

## Integration Points

### SchedulerService Integration

**Current Method**: `_execute_scheduled_download(schedule_id: int)`

**Enhanced Flow**:
```python
def _execute_scheduled_download(self, schedule_id: int):
    # Get schedule configuration
    schedule_config = self.db_manager.get_schedule(schedule_id)

    # NEW: Check time window if enabled
    if schedule_config.time_window_enabled:
        time_window = TimeWindow(
            start_time=schedule_config.time_window_start,
            end_time=schedule_config.time_window_end,
            enabled=True
        )

        if not time_window.is_current_time_in_window():
            logger.info("Skipping download - outside time window")
            return  # Skip this execution, will retry next scheduled run

    # Existing download logic continues...
    pending_models = self.db_manager.get_models_by_status("pending")
    # ... rest of existing implementation
```

### Configuration Integration

**Config File Extension**:
```yaml
# config/config.yaml - add to schedule section
default_schedule:
  enabled: true
  type: daily
  time: "22:00"
  max_concurrent_downloads: 1
  # NEW: Time window settings
  time_window:
    enabled: true
    start: "22:00"
    end: "07:00"
```

### CLI Integration

**New Commands**:
```bash
# Set time window for schedule
hf-downloader schedule time-window --enable --start 22:00 --end 07:00

# Disable time window
hf-downloader schedule time-window --disable

# Check current time window status
hf-downloader schedule time-window-status

# List schedules with time window info
hf-downloader schedule list --include-time-windows
```

## Error Handling and Edge Cases

### Time Validation Errors

**Invalid Time Format**:
```python
try:
    schedule_config.time_window_start = "25:00"  # Invalid
except ValueError as e:
    logger.error(f"Invalid time format: {e}")
    # Handle error gracefully
```

**Midnight Crossing**:
- Time window "22:00" to "07:00" crosses midnight
- Logic: current_time >= 22:00 OR current_time <= 07:00

**Time Zone Changes**:
- System local time changes handled automatically
- No persistent timezone storage required

### Logging and Monitoring

**New Log Events**:
```
INFO: Time window check: current_time=23:30, window=22:00-07:00, result=ALLOWED
INFO: Time window check: current_time=08:00, window=22:00-07:00, result=DENIED
INFO: Time window enabled for schedule 'nightly-downloads'
WARN: Schedule execution skipped - outside time window
```

**Database Audit Trail**:
- Log time-based decisions in system_logs table
- Track skipped executions for transparency
- Metrics for time window utilization

## Testing Requirements

### Unit Tests
- TimeWindow class time validation
- Midnight crossing logic
- Time format parsing

### Integration Tests
- SchedulerService with time window enabled/disabled
- Database migration with existing data
- CLI command functionality

### Contract Tests
- Time window validation API endpoints
- Schedule status responses with time info
- Error responses for invalid time formats

## Summary

The data model extends the existing ScheduleConfiguration with time window fields while maintaining full backward compatibility. The TimeWindow utility class encapsulates time validation logic, and the integration points ensure seamless operation with the existing scheduler architecture.

**Next**: Generate API contracts and test scenarios based on this data model.