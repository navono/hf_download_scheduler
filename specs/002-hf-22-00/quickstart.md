# Quickstart Guide: Time Window Download Scheduling

This guide demonstrates how to set up and use time window download scheduling in the HF Downloader.

## Prerequisites

- HF Downloader installed and configured
- Existing schedule set up (or create one)
- Python 3.11+ environment

## Setup Time Window Scheduling

### 1. Check Current Schedules

```bash
# List all schedules
hf-downloader schedule list

# Example output:
# ID  Name          Type    Time    Enabled  Time Window
# 1   nightly       daily   22:00   true     disabled
```

### 2. Enable Time Window for Existing Schedule

```bash
# Enable time window for schedule ID 1 (22:00 to 07:00)
hf-downloader schedule time-window --schedule-id 1 --enable --start 22:00 --end 07:00

# Verify the configuration
hf-downloader schedule show 1

# Example output:
# Schedule ID: 1
# Name: nightly
# Type: daily
# Time: 22:00
# Enabled: true
# Time Window: ENABLED (22:00 - 07:00)
```

### 3. Create New Schedule with Time Window

```bash
# Create a new schedule with time window restrictions
hf-downloader schedule create \
  --name "overnight-downloads" \
  --type daily \
  --time "22:00" \
  --time-window-enable \
  --time-window-start "22:00" \
  --time-window-end "07:00"

# Alternative: Set time window after creation
hf-downloader schedule create \
  --name "batch-downloads" \
  --type daily \
  --time "23:00"

# Then enable time window
hf-downloader schedule time-window \
  --schedule-id 2 \
  --enable \
  --start "23:00" \
  --end "06:00"
```

## Testing Time Window Behavior

### 1. Check Current Time Window Status

```bash
# Check if current time is within any active time windows
hf-downloader time-window status

# Example outputs:
# Outside time window (08:00):
# Current Time: 2025-09-24 08:00:00
# Active Schedules: 2
# Time Window Status: INACTIVE
# Next Window: 2025-09-24 22:00:00

# Inside time window (23:30):
# Current Time: 2025-09-24 23:30:00
# Active Schedules: 2
# Time Window Status: ACTIVE
# Downloads Allowed: YES
```

### 2. Test Schedule Execution

```bash
# Manually trigger schedule to test time window logic
hf-downloader schedule run --schedule-id 1

# Expected behavior:
# - If within time window: Downloads start
# - If outside time window: Message indicating skipped execution
```

### 3. Validate Time Window Configuration

```bash
# Validate time window format
hf-downloader time-window validate --start 22:00 --end 07:00

# Valid configuration:
# ✅ Time window is valid
# Duration: 9 hours (540 minutes)
# Crosses midnight: Yes

# Invalid configuration:
# ❌ Invalid time format: "25:00"
# Error: Hour must be between 00-23
```

## Adding Models to Download Queue

### 1. Add Models for Scheduled Download

```bash
# Add models to download queue
hf-downloader models add bert-base-uncased
hf-downloader models add gpt2

# Check pending models
hf-downloader models list --status pending

# Example output:
# ID  Name               Status    Added At
# 1   bert-base-uncased  pending   2025-09-24 10:00:00
# 2   gpt2               pending   2025-09-24 10:05:00
```

### 2. Monitor Download Progress

```bash
# Check active downloads
hf-downloader status

# Check download history
hf-downloader history

# View logs for time-based decisions
tail -f logs/hf_downloader.log | grep "time window"
```

## Common Scenarios

### Scenario 1: Normal Operation

```bash
# At 22:30 (within time window)
# Schedule triggers automatically
# Downloads start for pending models
# System logs: "Time window check: ALLOWED"

# At 07:30 (outside time window)
# Schedule triggers but skips downloads
# System logs: "Time window check: DENIED"
```

### Scenario 2: Schedule Outside Time Window

```bash
# Schedule set for 23:00 but time window is 22:00-07:00
# Behavior: Schedule runs at 23:00 and downloads start (within window)
```

### Scenario 3: Midnight Crossing

```bash
# Time window: 22:00-07:00 (crosses midnight)
# At 23:00: Within window ✓
# At 06:00: Within window ✓
# At 08:00: Outside window ✗
```

## Configuration File Example

Update `config/config.yaml` to include time window settings:

```yaml
# config/config.yaml
default_schedule:
  enabled: true
  type: daily
  time: "22:00"
  max_concurrent_downloads: 2
  # Time window settings
  time_window:
    enabled: true
    start: "22:00"
    end: "07:00"

# Monitoring settings
monitoring:
  health_check_interval: 60
  # Enable time window logging
  log_time_window_events: true
```

## Troubleshooting

### Time Window Not Working

1. **Check if time window is enabled**:
   ```bash
   hf-downloader schedule show [schedule-id]
   ```

2. **Verify time format**:
   ```bash
   hf-downloader time-window validate --start [time] --end [time]
   ```

3. **Check system time**:
   ```bash
   date
   ```

4. **Review logs**:
   ```bash
   grep -i "time window" logs/hf_downloader.log
   ```

### Downloads Not Starting

1. **Check time window status**:
   ```bash
   hf-downloader time-window status
   ```

2. **Verify schedule is enabled**:
   ```bash
   hf-downloader schedule list
   ```

3. **Check for pending models**:
   ```bash
   hf-downloader models list --status pending
   ```

### Invalid Time Format Error

```bash
# Correct format
hf-downloader schedule time-window --start 22:00 --end 07:00

# Incorrect formats (will cause errors):
# --start 22:00     (missing end time)
# --start 25:00     (invalid hour)
# --start 22:00:00  (invalid format)
```

## Monitoring and Logging

### Key Log Messages to Watch

```
INFO: Time window enabled for schedule 'nightly-downloads': 22:00-07:00
INFO: Time window check: current_time=23:30, window=22:00-07:00, result=ALLOWED
INFO: Time window check: current_time=08:00, window=22:00-07:00, result=DENIED
WARN: Schedule execution skipped - outside time window
INFO: Starting downloads within time window (2 models pending)
```

### Database Monitoring

```sql
-- Check schedule configurations with time windows
SELECT id, name, time_window_enabled, time_window_start, time_window_end
FROM schedule_configurations
WHERE time_window_enabled = true;

-- Check time-based decisions in system logs
SELECT log_type, message, created_at
FROM system_logs
WHERE log_type = 'info' AND message LIKE '%time window%'
ORDER BY created_at DESC
LIMIT 10;
```

## Next Steps

1. **Monitor the system** for the first few scheduled runs
2. **Adjust time windows** based on your network performance patterns
3. **Set up alerts** for missed download windows
4. **Review download logs** to optimize timing

## Support

For issues and questions:
- Check the logs: `logs/hf_downloader.log`
- Review system status: `hf-downloader status`
- Validate configuration: `hf-downloader config validate`