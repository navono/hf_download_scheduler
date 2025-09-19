# CLI Contract Specification

## Command Structure

### Main Command
```
hf-downloader [OPTIONS] COMMAND [ARGS]
```

### Global Options
- `--version` - Show version and exit
- `--help` - Show help message and exit
- `--config PATH` - Path to configuration file (default: ./config/default.yaml)
- `--verbose` - Enable verbose logging
- `--format {json,text}` - Output format (default: text)

### Commands

#### 1. start
Start the downloader in background mode

```bash
hf-downloader start [OPTIONS]
```

**Options:**
- `--foreground` - Run in foreground (default: background)
- `--models PATH` - Path to models.json file (default: ./config/models.json)
- `--pid PATH` - PID file path (default: ./hf-downloader.pid)

**Returns:**
- Success: `{"status": "started", "pid": 12345}`
- Error: `{"status": "error", "message": "already running"}`

#### 2. stop
Stop the running downloader

```bash
hf-downloader stop [OPTIONS]
```

**Options:**
- `--pid PATH` - PID file path (default: ./hf-downloader.pid)

**Returns:**
- Success: `{"status": "stopped"}`
- Error: `{"status": "error", "message": "not running"}`

#### 3. status
Check downloader status

```bash
hf-downloader status [OPTIONS]
```

**Options:**
- `--pid PATH` - PID file path (default: ./hf-downloader.pid)

**Returns:**
- Running: `{"status": "running", "pid": 12345, "uptime": "2h 30m"}`
- Stopped: `{"status": "stopped"}`

#### 4. models
Manage model definitions

```bash
hf-downloader models [OPTIONS] COMMAND
```

##### 4.1 list
List all models

```bash
hf-downloader models list [OPTIONS]
```

**Options:**
- `--status {all,pending,downloading,completed,failed}` - Filter by status
- `--format {json,table}` - Output format

**Returns:**
```json
{
  "models": [
    {
      "id": 1,
      "name": "facebook/bart-large-cnn",
      "status": "pending",
      "size_bytes": 1625567890,
      "download_path": null,
      "created_at": "2025-09-19T10:30:00Z"
    }
  ]
}
```

##### 4.2 add
Add a new model

```bash
hf-downloader models add [OPTIONS] MODEL_NAME
```

**Options:**
- `--models PATH` - Path to models.json file

**Returns:**
- Success: `{"status": "added", "model": MODEL_NAME}`
- Error: `{"status": "error", "message": "model already exists"}`

##### 4.3 remove
Remove a model

```bash
hf-downloader models remove [OPTIONS] MODEL_NAME
```

**Returns:**
- Success: `{"status": "removed", "model": MODEL_NAME}`
- Error: `{"status": "error", "message": "model not found"}`

#### 5. schedule
Manage download schedules

```bash
hf-downloader schedule [OPTIONS] COMMAND
```

##### 5.1 list
List all schedules

```bash
hf-downloader schedule list [OPTIONS]
```

**Returns:**
```json
{
  "schedules": [
    {
      "id": 1,
      "name": "daily-download",
      "type": "daily",
      "time": "22:00",
      "enabled": true,
      "max_concurrent_downloads": 1
    }
  ]
}
```

##### 5.2 add
Add a new schedule

```bash
hf-downloader schedule add [OPTIONS] NAME TYPE TIME
```

**Options:**
- `--day-of-week INTEGER` - Day of week (0-6, for weekly schedules)
- `--max-concurrent INTEGER` - Max concurrent downloads

**Returns:**
- Success: `{"status": "added", "schedule": NAME}`

##### 5.3 enable
Enable a schedule

```bash
hf-downloader schedule enable [OPTIONS] SCHEDULE_ID
```

**Returns:**
- Success: `{"status": "enabled", "schedule": SCHEDULE_ID}`

##### 5.4 disable
Disable a schedule

```bash
hf-downloader schedule disable [OPTIONS] SCHEDULE_ID
```

**Returns:**
- Success: `{"status": "disabled", "schedule": SCHEDULE_ID}`

#### 6. download
Manual download commands

```bash
hf-downloader download [OPTIONS] COMMAND
```

##### 6.1 now
Download a model immediately

```bash
hf-downloader download now [OPTIONS] MODEL_NAME
```

**Options:**
- `--foreground` - Run in foreground
- `--timeout INTEGER` - Timeout in seconds

**Returns:**
- Success: `{"status": "completed", "model": MODEL_NAME, "path": "/path/to/model"}`
- Error: `{"status": "error", "message": "download failed"}`

#### 7. logs
View logs

```bash
hf-downloader logs [OPTIONS]
```

**Options:**
- `--lines INTEGER` - Number of lines to show (default: 100)
- `--follow` - Follow log output
- `--level {DEBUG,INFO,WARNING,ERROR}` - Filter by log level

#### 8. config
Manage configuration

```bash
hf-downloader config [OPTIONS] COMMAND
```

##### 8.1 show
Show current configuration

```bash
hf-downloader config show [OPTIONS]
```

**Returns:**
```json
{
  "config": {
    "download_directory": "/models",
    "log_level": "INFO",
    "max_retries": 5,
    "timeout_seconds": 3600
  }
}
```

##### 8.2 set
Set configuration value

```bash
hf-downloader config set [OPTIONS] KEY VALUE
```

**Returns:**
- Success: `{"status": "updated", "key": KEY, "value": VALUE}`

## Error Response Format

All commands return consistent error responses:

```json
{
  "status": "error",
  "error_code": "ERROR_TYPE",
  "message": "Human readable error message",
  "details": {}
}
```

### Common Error Codes
- `INVALID_ARGUMENT` - Invalid command line arguments
- `FILE_NOT_FOUND` - Configuration or models file not found
- `PERMISSION_DENIED` - Insufficient permissions
- `ALREADY_RUNNING` - Downloader already running
- `NOT_RUNNING` - Downloader not running
- `NETWORK_ERROR` - Network connectivity issues
- `DISK_SPACE` - Insufficient disk space
- `CONFIGURATION_ERROR` - Invalid configuration

## Configuration File Format

### default.yaml
```yaml
# General settings
download_directory: "./models"
log_level: "INFO"
max_retries: 5
timeout_seconds: 3600

# Database settings
database_path: "./hf_downloader.db"

# Process settings
pid_file: "./hf_downloader.pid"
foreground: false
```

### models.json
```json
{
  "models": [
    {
      "name": "facebook/bart-large-cnn",
      "status": "pending",
      "metadata": {
        "description": "BART large model for CNN/Daily Mail",
        "tags": ["summarization", "english"]
      }
    }
  ]
}
```

## Signal Handling

The downloader handles the following signals:
- `SIGTERM` - Graceful shutdown
- `SIGINT` - Graceful shutdown
- `SIGHUP` - Reload configuration