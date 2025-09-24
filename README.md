# HF Downloader

A scheduled Hugging Face model downloader with background processing, configuration management, and comprehensive monitoring capabilities.

## Features

- **Scheduled Downloads**: Configurable scheduling with daily and weekly options
- **Time Window Restrictions**: Configure specific time periods for downloads (e.g., 22:00-07:00)
- **Background Processing**: Daemon mode for continuous operation
- **Configuration Management**: YAML-based configuration with environment variable overrides
- **Database Integration**: SQLite-based persistence for models, schedules, and download sessions
- **CLI Interface**: Comprehensive command-line interface for management
- **Status Tracking**: Real-time download progress and status monitoring
- **Retry Logic**: Automatic retry mechanism for failed downloads
- **Concurrent Downloads**: Configurable concurrent download limits
- **UV Package Management**: Modern, fast dependency management

## Installation

1. **Clone the repository:**

   ```bash
   git clone <repository-url>
   cd schedule-download-models
   ```

2. **Install dependencies and Git hooks:**

   ```bash
   make install
   ```
   
   This will install all dependencies and set up the Git pre-commit hook that ensures code quality before each commit.

3. **Set up environment:**
   ```bash
   cp .env.example .env
   # Edit .env with your Hugging Face token and other settings
   ```

## Quick Start

### Basic Usage

```bash
# Start the downloader daemon
uv run hf-downloader start

# Check status
uv run hf-downloader status

# View available models
uv run hf-downloader models list

# Stop the daemon
uv run hf-downloader stop
```

### Configuration

The application uses YAML configuration files with environment variable overrides:

- **Development**: `config/development.yaml`
- **Production**: `config/production.yaml`
- **Default**: `config/default.yaml`

Example configuration:

```yaml
download_directory: ./models
log_level: INFO
max_retries: 5
timeout_seconds: 3600
concurrent_downloads: 1
default_schedule:
  enabled: true
  type: daily
  time: "22:00"
  max_concurrent_downloads: 1
  time_window:
    enabled: true
    start_time: "22:00"
    end_time: "07:00"
    timezone: "local"
```

### Models Configuration

Configure models to download in `config/models.json`. This JSON file provides comprehensive model management capabilities with detailed metadata and global settings.

#### File Structure

```json
{
  "models": [...],     // Array of model configurations
  "settings": {...},   // Global download settings
  "metadata": {...}    // Configuration metadata
}
```

#### Model Object Fields

Each model in the `models` array supports the following fields:

##### Required Fields

- **`name`** (string): Hugging Face model identifier

  - Format: `organization/model-name` or `username/model-name`
  - Example: `"facebook/bart-large-cnn"`, `"bert-base-uncased"`
  - Used to identify and download models from Hugging Face Hub

- **`enabled`** (boolean): Download status control
  - `true`: Include in download schedule
  - `false`: Skip this model (temporarily disabled)

- **`status`** (string): Model download status
  - Values: `"pending"` (default), `"downloading"`, `"completed"`, `"failed"`
  - Purpose: Track download progress and synchronize with database
  - Synchronization: Database status takes precedence over JSON status when conflicts exist
  - Example: `"pending"` for models ready to download, `"completed"` for successfully downloaded models

##### Optional Fields

- **`priority`** (string): Download priority level

  - Values: `"high"`, `"medium"` (default), `"low"`
  - Purpose: Determines download order - high priority models are downloaded first
  - Implementation: Models are ordered by priority in the download queue

#### Global Settings

The `settings` object contains global configuration options:

- **`auto_cleanup`** (boolean): Enable automatic cleanup of old downloads

  - Default: `false`

- **`cleanup_age_days`** (integer): Clean up downloads older than specified days

  - Default: `30`
  - Works with `auto_cleanup: true`

- **`max_total_size`** (string): Maximum total size for all models

  - Format: Number + unit (KB, MB, GB)
  - Purpose: Prevent excessive disk usage
  - Example: `"50GB"`

- **`check_frequency`** (string): How often to check for model updates
  - Values: `"daily"`, `"weekly"`, `"monthly"`
  - Default: `"daily"`

#### Metadata

The `metadata` object contains configuration file information:

- **`version`** (string): Configuration file version

  - Example: `"1.0"`

- **`created`** (string): File creation timestamp

  - Format: ISO 8601 (UTC)
  - Example: `"2025-01-01T00:00:00Z"`

- **`last_updated`** (string): Last modification timestamp
  - Format: ISO 8601 (UTC)
  - Example: `"2025-01-19T01:30:00Z"`

#### Complete Example

```json
{
  "models": [
    {
      "name": "Qwen/Qwen3-Omni-30B-A3B-Instruct",
      "priority": "high",
      "status": "pending",
      "enabled": true
    },
    {
      "name": "Alibaba-NLP/Tongyi-DeepResearch-30B-A3B",
      "priority": "medium",
      "status": "pending",
      "enabled": true
    },
    {
      "name": "zai-org/GLM-4.5-Air-FP8",
      "priority": "low",
      "status": "pending",
      "enabled": true
    }
  ],
  "settings": {
    "auto_cleanup": true,
    "cleanup_age_days": 30,
    "max_total_size": "100GB",
    "check_frequency": "weekly"
  },
  "metadata": {
    "version": "1.0",
    "created": "2025-01-01T00:00:00Z",
    "last_updated": "2025-01-19T01:30:00Z"
  }
}
```

#### Best Practices

1. **Required Fields**: Always include `name` and `enabled` for each model
2. **Naming**: Use standard Hugging Face model names
3. **Size Estimates**: Provide accurate estimates for better disk management
4. **Priority Setting**: Set priorities based on business requirements
5. **Tag Management**: Use consistent tag naming conventions
6. **Version Control**: Update timestamps when modifying configurations
7. **Disk Planning**: Consider total size when adding multiple models
8. **Cleanup Strategy**: Enable auto-cleanup for long-running operations

## CLI Commands

### Time Window Management

The downloader supports time window restrictions to limit downloads to specific time periods. This is useful for scheduling downloads during off-peak hours or to comply with network usage policies.

#### Key Features
- **Cross-midnight support**: Configure windows like 22:00-07:00 (next day)
- **Validation**: Ensures proper time format (HH:MM) and logical consistency
- **Real-time status**: Check if current time is within the configured window
- **Flexible configuration**: Enable/disable per schedule with different time ranges

#### Usage Examples

```bash
# Enable time window for a schedule (22:00 to 07:00 next day)
uv run hf-downloader schedule time-window 1 --enable --start-time "22:00" --end-time "07:00"

# Disable time window restrictions
uv run hf-downloader schedule time-window 1 --disable

# Check current time window status
uv run hf-downloader schedule time-window-status 1

# List all schedules (shows time window information)
uv run hf-downloader schedule list
```

#### Time Window Status Output

The `time-window-status` command provides detailed information:

```
Time Window Status for Schedule 1:
  Enabled: Yes
  Start Time: 22:00
  End Time: 07:00
  Currently Active: No
  Next Window Start: 2025-09-24T22:00:00
  Current Window End: None
  Crosses Midnight: Yes
  Duration Minutes: 540
```

### Daemon Management

```bash
# Start downloader (background by default)
uv run hf-downloader start
uv run hf-downloader start --foreground  # Run in foreground

# Stop downloader
uv run hf-downloader stop

# Check daemon status
uv run hf-downloader status

# View daemon logs
uv run hf-downloader logs
uv run hf-downloader logs --tail 50  # Last 50 lines
uv run hf-downloader logs --follow   # Follow logs
```

### Model Management

```bash
# List all models
uv run hf-downloader models list

# List models by status
uv run hf-downloader models list --status pending
uv run hf-downloader models list --status completed

# Add new model
uv run hf-downloader models add "bert-base-uncased" --priority "medium"

# Remove model
uv run hf-downloader models remove "bert-base-uncased"

# Update model status
uv run hf-downloader models update "bert-base-uncased" --status completed

# Update model priority
uv run hf-downloader models update "bert-base-uncased" --priority "high"
```

### Schedule Management

```bash
# List schedules
uv run hf-downloader schedule list

# Create daily schedule
uv run hf-downloader schedule create --type daily --time "23:00" --name "nightly"

# Create weekly schedule
uv run hf-downloader schedule create --type weekly --time "14:00" --day 5 --name "friday"

# Enable/disable schedule
uv run hf-downloader schedule enable 1
uv run hf-downloader schedule disable 1

# Set active schedule
uv run hf-downloader schedule set-active 1

# Configure time window for a schedule
uv run hf-downloader schedule time-window 1 --enable --start-time "22:00" --end-time "07:00"
uv run hf-downloader schedule time-window 1 --disable

# Check time window status
uv run hf-downloader schedule time-window-status 1
```

### Configuration Management

```bash
# View current configuration
uv run hf-downloader config show

# Update configuration
uv run hf-downloader config set log_level DEBUG
uv run hf-downloader config set max_retries 3

# Reset to defaults
uv run hf-downloader config reset

# Validate configuration
uv run hf-downloader config validate

# Export configuration
uv run hf-downloader config export --format json
uv run hf-downloader config export --format yaml
```

## Development

### Environment Setup

```bash
# Install development dependencies
uv sync --dev

# Run tests
uv run pytest

# Run tests with coverage
uv run pytest --cov=hf_downloader

# Run specific test categories
uv run pytest tests/unit/
uv run pytest tests/integration/
uv run pytest tests/contract/
```

### Code Quality

```bash
# Lint code
uv run ruff check .

# Format code
uv run ruff format .

# Type checking
uv run mypy .

# Run all quality checks
make check

# Install Git pre-commit hook for automatic linting before commits
make install-hooks
```

### Git Pre-commit Hook

This project includes a Git pre-commit hook that automatically runs `make lint-fix` before each commit to ensure code quality. If linting fails, the commit will be aborted.

To install the pre-commit hook:

```bash
make install-hooks
```

The pre-commit hook will:
1. Run `make lint-fix` to automatically fix linting issues when possible
2. Abort the commit if any linting errors remain
3. Allow the commit to proceed if all checks pass

### Development Commands

```bash
# Start development server
make dev

# Build project
make build

# Clean build artifacts
make clean
```

## Project Structure

```
schedule-download-models/
├── config/
│   ├── default.yaml         # Default configuration
│   ├── development.yaml     # Development settings
│   ├── production.yaml      # Production settings
│   └── models.json          # Models to download
├── src/hf_downloader/
│   ├── __init__.py
│   ├── cli/
│   │   ├── __init__.py
│   │   └── main.py          # CLI implementation
│   ├── core/
│   │   ├── __init__.py
│   │   └── config.py        # Configuration management
│   ├── models/
│   │   ├── __init__.py
│   │   └── database.py      # Database models
│   ├── services/
│   │   ├── __init__.py
│   │   ├── configuration.py # Configuration service
│   │   ├── downloader.py    # Download service
│   │   ├── scheduler.py     # Scheduling service
│   │   └── process_manager.py  # Process management
│   └── daemon/
│       ├── __init__.py
│       └── main.py          # Daemon implementation
├── tests/
│   ├── unit/                # Unit tests
│   ├── integration/         # Integration tests
│   └── contract/            # Contract tests
├── .env.example             # Environment variables template
├── Makefile                # Common commands
├── pyproject.toml          # Project configuration
└── README.md               # This file
```

## Configuration

### Default Configuration

By default, the application uses **`./config/default.yaml`** as the configuration file. This provides a base configuration suitable for development and general use.

### Configuration Files

The application supports multiple configuration environments:

- **`./config/default.yaml`** - Default configuration (used when no specific config is specified)
- **`./config/development.yaml`** - Development environment settings
- **`./config/production.yaml`** - Production environment settings

### Specifying Configuration

You can specify which configuration file to use in several ways:

#### 1. Command Line Flag (Recommended)
```bash
# Use a specific configuration file
uv run hf-downloader --config ./config/production.yaml status

# Use development configuration
uv run hf-downloader --config ./config/development.yaml start
```

#### 2. Environment Variable
```bash
# Set configuration path via environment variable
export HF_DOWNLOADER_CONFIG_PATH=./config/production.yaml
uv run hf-downloader status
```

#### 3. Default Behavior
When no configuration is specified, the application automatically uses `./config/default.yaml`:
```bash
# Uses default.yaml automatically
uv run hf-downloader status
```

### Configuration Loading Priority

The application loads configuration in this order (later items override earlier ones):

1. **Default values** (hardcoded defaults in the application)
2. **YAML configuration file** (specified or default)
3. **Environment variables** (only override if explicitly set)

### Environment Variables

Key environment variables that can override configuration file settings:

```bash
# Hugging Face Authentication
HF_TOKEN=your_hugging_face_token_here

# Application Configuration (overrides config file)
HF_DOWNLOADER_CONFIG_PATH=./config/custom.yaml
HF_DOWNLOADER_LOG_LEVEL=INFO
HF_DOWNLOADER_DOWNLOAD_DIR=./models

# Database Configuration
HF_DOWNLOADER_DB_PATH=./hf_downloader.db

# Process Management
HF_DOWNLOADER_PID_FILE=./hf_downloader.pid
HF_DOWNLOADER_FOREGROUND=false

# Network Configuration
HF_DOWNLOADER_TIMEOUT=3600
HF_DOWNLOADER_MAX_RETRIES=5
HF_DOWNLOADER_CONCURRENT_DOWNLOADS=2

# Time Window Configuration (nested under default_schedule)
HF_DOWNLOADER_TIME_WINDOW_ENABLED=true
HF_DOWNLOADER_TIME_WINDOW_START=22:00
HF_DOWNLOADER_TIME_WINDOW_END=07:00
HF_DOWNLOADER_TIME_WINDOW_TIMEZONE=local
```

### Configuration Examples

#### Development Setup
```bash
# Use development configuration
uv run hf-downloader --config ./config/development.yaml start --foreground
```

#### Production Setup
```bash
# Use production configuration
uv run hf-downloader --config ./config/production.yaml start
```

#### Custom Configuration
```bash
# Use custom configuration file
uv run hf-downloader --config ./config/my-config.yaml status
```

## Architecture

### Core Components

1. **Database Layer**: SQLAlchemy models for persistence
2. **Service Layer**: Business logic for downloads, scheduling, and configuration
3. **CLI Layer**: Command-line interface using Click
4. **Daemon Layer**: Background process management

### Key Features

- **Modular Architecture**: Clean separation of concerns
- **Configuration Service**: Centralized configuration management
- **Download Service**: Handles Hugging Face model downloads
- **Scheduler Service**: Manages download scheduling
- **Process Manager**: Daemon lifecycle management
- **Database Integration**: Persistent storage for all data

## Monitoring and Logging

### Logging

The application uses structured logging with configurable levels:

- DEBUG: Detailed debugging information
- INFO: General operational information
- WARNING: Warning conditions
- ERROR: Error conditions
- CRITICAL: Critical conditions

### Status Monitoring

Real-time monitoring of:

- Download progress and status
- Schedule execution
- System resource usage
- Error rates and retry attempts

## Testing

The project includes comprehensive test coverage:

- **Unit Tests**: Individual component testing
- **Integration Tests**: Service integration testing
- **Contract Tests**: API contract verification
- **E2E Tests**: End-to-end workflow testing

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=hf_downloader --cov-report=html
```

## Deployment

### Production Setup

1. **Configure production settings:**

   ```bash
   cp config/production.yaml config/active.yaml
   # Edit configuration as needed
   ```

2. **Set environment variables:**

   ```bash
   export HF_DOWNLOADER_CONFIG_PATH=./config/active.yaml
   export HF_TOKEN=your_production_token
   ```

3. **Start the service:**
   ```bash
   uv run hf-downloader start
   ```

### Service Management

For production deployment, consider using systemd or similar service managers:

```ini
# /etc/systemd/system/hf-downloader.service
[Unit]
Description=HF Downloader Service
After=network.target

[Service]
Type=forking
User=hf-downloader
WorkingDirectory=/opt/hf-downloader
ExecStart=/opt/hf-downloader/.venv/bin/hf-downloader start
ExecStop=/opt/hf-downloader/.venv/bin/hf-downloader stop
Restart=always

[Install]
WantedBy=multi-user.target
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Ensure all tests pass
6. Update documentation as needed
7. Submit a pull request

### Development Guidelines

- Follow the existing code style
- Write comprehensive tests
- Update documentation
- Use type hints
- Follow the modular architecture

## License

This project is licensed under the MIT License.

## Acknowledgments

- [Hugging Face](https://huggingface.co/) for the model hub
- [Click](https://click.palletsprojects.com/) for CLI framework
- [SQLAlchemy](https://www.sqlalchemy.org/) for ORM
- [UV](https://docs.astral.sh/uv/) for package management
- [Schedule](https://schedule.readthedocs.io/) for task scheduling
