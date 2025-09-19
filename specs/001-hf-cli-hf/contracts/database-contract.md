# Database Contract Specification

## Database Schema

### Tables

#### 1. models
```sql
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
```

#### 2. schedule_configurations
```sql
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
```

#### 3. download_sessions
```sql
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
```

#### 4. system_configurations
```sql
CREATE TABLE system_configurations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key TEXT NOT NULL UNIQUE,
    value TEXT NOT NULL,
    description TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

## Database Operations Contract

### Model Operations

#### Create Model
```python
def create_model(name: str, size_bytes: Optional[int] = None, metadata: Optional[dict] = None) -> Model:
    """
    Create a new model record.

    Args:
        name: Hugging Face model identifier
        size_bytes: Model size in bytes (optional)
        metadata: Additional model metadata (optional)

    Returns:
        Model object

    Raises:
        IntegrityError: Model name already exists
        ValueError: Invalid model name
    """
```

#### Get Model
```python
def get_model(model_id: int) -> Optional[Model]:
    """
    Get model by ID.

    Args:
        model_id: Model primary key

    Returns:
        Model object or None
    """
```

#### Get Model by Name
```python
def get_model_by_name(name: str) -> Optional[Model]:
    """
    Get model by name.

    Args:
        name: Hugging Face model identifier

    Returns:
        Model object or None
    """
```

#### Update Model Status
```python
def update_model_status(model_id: int, status: str, download_path: Optional[str] = None) -> bool:
    """
    Update model status and optionally download path.

    Args:
        model_id: Model primary key
        status: New status ('pending', 'downloading', 'completed', 'failed', 'paused')
        download_path: Local file system path (optional)

    Returns:
        True if update successful, False otherwise

    Raises:
        ValueError: Invalid status transition
    """
```

#### Get Models by Status
```python
def get_models_by_status(status: str) -> List[Model]:
    """
    Get all models with specified status.

    Args:
        status: Model status to filter by

    Returns:
        List of Model objects
    """
```

### Schedule Operations

#### Create Schedule
```python
def create_schedule(name: str, type: str, time: str, day_of_week: Optional[int] = None,
                   max_concurrent_downloads: int = 1) -> ScheduleConfiguration:
    """
    Create a new schedule configuration.

    Args:
        name: Schedule name
        type: Schedule type ('daily', 'weekly', 'custom')
        time: Time in HH:MM format
        day_of_week: Day of week (0-6) for weekly schedules
        max_concurrent_downloads: Maximum concurrent downloads

    Returns:
        ScheduleConfiguration object

    Raises:
        ValueError: Invalid schedule configuration
    """
```

#### Get Active Schedule
```python
def get_active_schedule() -> Optional[ScheduleConfiguration]:
    """
    Get the currently enabled schedule.

    Returns:
        ScheduleConfiguration object or None
    """
```

#### Enable Schedule
```python
def enable_schedule(schedule_id: int) -> bool:
    """
    Enable a schedule and disable all others.

    Args:
        schedule_id: Schedule primary key

    Returns:
        True if successful, False otherwise
    """
```

### Download Session Operations

#### Create Download Session
```python
def create_download_session(model_id: int, schedule_id: Optional[int] = None) -> DownloadSession:
    """
    Create a new download session.

    Args:
        model_id: Model primary key
        schedule_id: Schedule primary key (optional)

    Returns:
        DownloadSession object
    """
```

#### Update Download Session
```python
def update_download_session(session_id: int, status: str, bytes_downloaded: Optional[int] = None,
                          total_bytes: Optional[int] = None, error_message: Optional[str] = None) -> bool:
    """
    Update download session progress.

    Args:
        session_id: Session primary key
        status: New status
        bytes_downloaded: Bytes downloaded so far
        total_bytes: Total file size
        error_message: Error message if failed

    Returns:
        True if update successful, False otherwise
    """
```

#### Get Download History
```python
def get_download_history(model_id: int, limit: int = 10) -> List[DownloadSession]:
    """
    Get download history for a model.

    Args:
        model_id: Model primary key
        limit: Maximum number of records to return

    Returns:
        List of DownloadSession objects
    """
```

### System Configuration Operations

#### Get System Configuration
```python
def get_system_config(key: str, default: Optional[str] = None) -> Optional[str]:
    """
    Get system configuration value.

    Args:
        key: Configuration key
        default: Default value if not found

    Returns:
        Configuration value or default
    """
```

#### Set System Configuration
```python
def set_system_config(key: str, value: str, description: Optional[str] = None) -> bool:
    """
    Set system configuration value.

    Args:
        key: Configuration key
        value: Configuration value
        description: Key description (optional)

    Returns:
        True if successful, False otherwise
    """
```

## Database Initialization

#### Initialize Database
```python
def initialize_database(db_path: str) -> bool:
    """
    Initialize database with schema and default data.

    Args:
        db_path: Path to SQLite database file

    Returns:
        True if successful, False otherwise
    """
```

#### Database Migration
```python
def migrate_database(db_path: str, target_version: int) -> bool:
    """
    Migrate database to target version.

    Args:
        db_path: Path to SQLite database file
        target_version: Target schema version

    Returns:
        True if successful, False otherwise
    """
```

## Error Handling

### Database Errors
- `DatabaseError`: General database error
- `ConnectionError`: Database connection failed
- `IntegrityError`: Constraint violation
- `OperationalError`: Database operation error

### Validation Errors
- `ValidationError`: Invalid input data
- `ConstraintError`: Business rule violation
- `NotFoundError`: Record not found
- `StateTransitionError`: Invalid state transition

## Performance Considerations

### Indexes
- Index on `models(status)` for filtering
- Index on `schedule_configurations(enabled)` for active schedule lookup
- Index on `download_sessions(status, model_id)` for download tracking
- Index on `system_configurations(key)` for configuration lookup

### Connection Pooling
- Single connection for CLI operations
- Connection reuse for background operations
- Proper connection cleanup on shutdown

### Transactions
- Atomic updates for model status changes
- Transaction isolation for concurrent operations
- Rollback on error conditions