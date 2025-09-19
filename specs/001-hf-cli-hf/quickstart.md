# Quick Start Guide

## Prerequisites

- Python 3.12 or higher
- Hugging Face account with API token
- Sufficient disk space for models
- Internet connection for downloads

## Installation

### 1. Install the Package

```bash
pip install hf-downloader
```

### 2. Set Up Hugging Face Authentication

```bash
# Set your Hugging Face token
export HF_TOKEN=your_token_here

# Or add to your shell profile (~/.bashrc, ~/.zshrc, etc.)
echo 'export HF_TOKEN=your_token_here' >> ~/.bashrc
```

### 3. Initialize Configuration

```bash
# Create default configuration
hf-downloader init
```

This creates:
- `./config/default.yaml` - Main configuration
- `./config/models.json` - Model definitions
- `./hf_downloader.db` - SQLite database

## Basic Usage

### 1. Add Models to Download

```bash
# Add a model for download
hf-downloader models add facebook/bart-large-cnn

# Add multiple models
hf-downloader models add google/pegasus-xsum
hf-downloader models add microsoft/DialoGPT-medium
```

### 2. Configure Schedule

```bash
# Set up daily downloads at 10 PM
hf-downloader schedule add "daily-download" daily "22:00"

# Enable the schedule
hf-downloader schedule enable 1
```

### 3. Start the Downloader

```bash
# Start in background mode
hf-downloader start

# Or run in foreground for testing
hf-downloader start --foreground
```

### 4. Check Status

```bash
# Check if downloader is running
hf-downloader status

# List models and their status
hf-downloader models list

# View recent downloads
hf-downloader models list --status completed
```

## Manual Downloads

### Download a Model Immediately

```bash
# Download a specific model now
hf-downloader download now facebook/bart-large-cnn

# Follow download progress in foreground
hf-downloader download now facebook/bart-large-cnn --foreground --timeout 1800
```

## Configuration Examples

### Basic Configuration (config/default.yaml)

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

# Download settings
concurrent_downloads: 1
chunk_size: 1048576  # 1MB chunks
```

### Model Configuration (config/models.json)

```json
{
  "models": [
    {
      "name": "facebook/bart-large-cnn",
      "status": "pending",
      "metadata": {
        "description": "BART large model for CNN/Daily Mail",
        "tags": ["summarization", "english"],
        "priority": "high"
      }
    },
    {
      "name": "google/pegasus-xsum",
      "status": "pending",
      "metadata": {
        "description": "Pegasus model for extreme summarization",
        "tags": ["summarization", "english"],
        "priority": "medium"
      }
    }
  ]
}
```

## Advanced Usage

### Custom Schedules

```bash
# Weekly schedule (Saturday at 2 AM)
hf-downloader schedule add "weekly-weekend" weekly "02:00" --day-of-week 5

# Custom schedule with concurrent downloads
hf-downloader schedule add "batch-download" daily "03:00" --max-concurrent 3
```

### System Management

```bash
# View system configuration
hf-downloader config show

# Change download directory
hf-downloader config set download_directory "/mnt/large_storage/models"

# Increase log verbosity
hf-downloader config set log_level "DEBUG"
```

### Log Management

```bash
# View recent logs
hf-downloader logs --lines 50

# Follow logs in real-time
hf-downloader logs --follow

# Filter by error level
hf-downloader logs --level ERROR
```

## Monitoring and Troubleshooting

### Check Download Progress

```bash
# View all download sessions
hf-downloader status --detailed

# Check specific model download history
hf-downloader models list --status downloading
```

### Common Issues

#### Authentication Problems
```bash
# Check if HF token is set
echo $HF_TOKEN

# Test Hugging Face access
huggingface-cli whoami
```

#### Permission Issues
```bash
# Check write permissions
touch ./test_file && rm ./test_file

# Or specify different download directory
hf-downloader config set download_directory "$HOME/models"
```

#### Disk Space
```bash
# Check available space
df -h

# Clean up failed downloads
hf-downloader models list --status failed
hf-downloader models remove failed_model_name
```

## Production Deployment

### Systemd Service

Create `/etc/systemd/system/hf-downloader.service`:

```ini
[Unit]
Description=HF Downloader Service
After=network.target

[Service]
Type=forking
User=download-user
Group=download-group
WorkingDirectory=/opt/hf-downloader
Environment=HF_TOKEN=your_token_here
ExecStart=/usr/local/bin/hf-downloader start --config /opt/hf-downloader/config/default.yaml
ExecStop=/usr/local/bin/hf-downloader stop --config /opt/hf-downloader/config/default.yaml
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start the service:

```bash
sudo systemctl daemon-reload
sudo systemctl enable hf-downloader
sudo systemctl start hf-downloader
```

### Docker Deployment

```dockerfile
FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy and install requirements
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy application
COPY . .

# Create directories
RUN mkdir -p /app/config /app/models /app/logs

# Set environment
ENV HF_TOKEN=${HF_TOKEN}
ENV PYTHONPATH=/app

# Expose port (if needed for monitoring)
EXPOSE 8080

# Start command
CMD ["python", "-m", "hf_downloader.cli.main", "start", "--foreground"]
```

## Security Considerations

### Environment Variables
- Never commit HF_TOKEN to version control
- Use environment files or secret management
- Rotate tokens regularly

### File Permissions
- Set appropriate permissions on configuration files
- Restrict database file access
- Use dedicated user account for running service

### Network Security
- Use HTTPS for all downloads
- Verify model checksums when available
- Monitor for unusual download activity

## Backup and Recovery

### Configuration Backup

```bash
# Backup configuration files
tar -czf hf-downloader-config-$(date +%Y%m%d).tar.gz \
    config/ \
    hf_downloader.db
```

### Database Recovery

```bash
# Restore from backup
cp hf_downloader.db.backup hf_downloader.db

# Or reinitialize if corrupted
hf-downloader init --force
```

## Getting Help

### Built-in Help

```bash
# General help
hf-downloader --help

# Command-specific help
hf-downloader models --help
hf-downloader schedule --help
```

### Logs and Debugging

```bash
# Enable debug logging
hf-downloader config set log_level "DEBUG"

# View debug logs
hf-downloader logs --level DEBUG --lines 100
```

### Community Support

- Check GitHub issues
- Review documentation
- Contact maintainers for critical issues