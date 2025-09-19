# Data Model Design

## Entity Relationships

```
Schedule Configuration (1) ←→ (N) Download Session
                      ↓
                 Model (1) ←→ (N) Download Session
```

## Core Entities

### 1. Model
Represents a Hugging Face model to be downloaded

**Fields:**
- `id` (Integer, Primary Key)
- `name` (String, Required) - Hugging Face model identifier (e.g., "facebook/bart-large-cnn")
- `status` (Enum: 'pending', 'downloading', 'completed', 'failed', 'paused')
- `size_bytes` (BigInteger, Optional) - Model size in bytes
- `download_path` (String, Optional) - Local file system path
- `created_at` (DateTime, Default=now)
- `updated_at` (DateTime, Default=now, Auto-update)
- `metadata` (JSON, Optional) - Additional model metadata

**Validation Rules:**
- `name` must be valid Hugging Face model identifier format
- `status` transitions follow: pending → downloading → (completed|failed)
- `size_bytes` must be non-negative if present
- `download_path` must be absolute path if present

### 2. Schedule Configuration
Defines when downloads should occur

**Fields:**
- `id` (Integer, Primary Key)
- `name` (String, Required) - Human-readable schedule name
- `type` (Enum: 'daily', 'weekly', 'custom')
- `time` (String, Required) - HH:MM format in 24-hour time
- `day_of_week` (Integer, Optional) - 0-6 (Monday-Sunday), required for weekly type
- `enabled` (Boolean, Default=True)
- `max_concurrent_downloads` (Integer, Default=1)
- `created_at` (DateTime, Default=now)
- `updated_at` (DateTime, Default=now, Auto-update)

**Validation Rules:**
- `time` must be valid HH:MM format
- `day_of_week` required when type='weekly'
- `max_concurrent_downloads` must be between 1 and 10
- Only one schedule can be enabled at a time

### 3. Download Session
Tracks individual download attempts

**Fields:**
- `id` (Integer, Primary Key)
- `model_id` (Foreign Key → Model.id, Required)
- `schedule_id` (Foreign Key → ScheduleConfiguration.id, Optional)
- `status` (Enum: 'started', 'in_progress', 'completed', 'failed', 'cancelled')
- `started_at` (DateTime, Default=now)
- `completed_at` (DateTime, Optional)
- `bytes_downloaded` (BigInteger, Default=0)
- `total_bytes` (BigInteger, Optional)
- `error_message` (Text, Optional)
- `retry_count` (Integer, Default=0)
- `metadata` (JSON, Optional) - Download session metadata

**Validation Rules:**
- `model_id` must reference existing model
- `completed_at` must be after `started_at` if present
- `bytes_downloaded` cannot exceed `total_bytes` if both present
- `retry_count` must be non-negative

### 4. System Configuration
Global application settings

**Fields:**
- `id` (Integer, Primary Key)
- `key` (String, Required, Unique) - Configuration key
- `value` (String, Required) - Configuration value
- `description` (Text, Optional)
- `created_at` (DateTime, Default=now)
- `updated_at` (DateTime, Default=now, Auto-update)

**Validation Rules:**
- `key` must be alphanumeric with underscores
- Predefined keys: 'download_directory', 'log_level', 'max_retries', 'timeout_seconds'

## State Transition Diagrams

### Model Status Transitions
```
pending → downloading → completed
               ↓
              failed → pending (retry)
```

### Download Session Status Transitions
```
started → in_progress → completed
                    ↓
                   failed → cancelled
```

## Database Schema (SQL)

```sql
-- Models table
CREATE TABLE models (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL CHECK (status IN ('pending', 'downloading', 'completed', 'failed', 'paused')),
    size_bytes BIGINT,
    download_path TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    metadata JSON
);

-- Schedule configurations table
CREATE TABLE schedule_configurations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    type TEXT NOT NULL CHECK (type IN ('daily', 'weekly', 'custom')),
    time TEXT NOT NULL CHECK (time LIKE '__:_'),
    day_of_week INTEGER CHECK (day_of_week BETWEEN 0 AND 6),
    enabled BOOLEAN DEFAULT 1,
    max_concurrent_downloads INTEGER DEFAULT 1 CHECK (max_concurrent_downloads BETWEEN 1 AND 10),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Download sessions table
CREATE TABLE download_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    model_id INTEGER NOT NULL,
    schedule_id INTEGER,
    status TEXT NOT NULL CHECK (status IN ('started', 'in_progress', 'completed', 'failed', 'cancelled')),
    started_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    completed_at DATETIME,
    bytes_downloaded BIGINT DEFAULT 0,
    total_bytes BIGINT,
    error_message TEXT,
    retry_count INTEGER DEFAULT 0,
    metadata JSON,
    FOREIGN KEY (model_id) REFERENCES models(id),
    FOREIGN KEY (schedule_id) REFERENCES schedule_configurations(id)
);

-- System configuration table
CREATE TABLE system_configurations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key TEXT NOT NULL UNIQUE,
    value TEXT NOT NULL,
    description TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for performance
CREATE INDEX idx_models_status ON models(status);
CREATE INDEX idx_schedule_configurations_enabled ON schedule_configurations(enabled);
CREATE INDEX idx_download_sessions_status ON download_sessions(status);
CREATE INDEX idx_download_sessions_model_id ON download_sessions(model_id);
CREATE INDEX idx_system_configurations_key ON system_configurations(key);
```

## Data Access Patterns

### Common Queries
1. Get all pending models: `SELECT * FROM models WHERE status = 'pending'`
2. Get active schedule: `SELECT * FROM schedule_configurations WHERE enabled = 1`
3. Get download history for model: `SELECT * FROM download_sessions WHERE model_id = ? ORDER BY started_at DESC`
4. Get system configuration: `SELECT * FROM system_configurations WHERE key = ?`

### Business Logic Constraints
1. Only one schedule can be enabled at a time
2. Model cannot be downloaded if already in 'downloading' state
3. Download sessions cannot be modified after completion
4. System configuration keys are predefined

## Migration Strategy
1. Version 1: Initial schema creation
2. Future versions: Add migration scripts with version tracking
3. Backup strategy: SQLite file backup before schema changes