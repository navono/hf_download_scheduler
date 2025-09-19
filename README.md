# schedule-download-models

Schedule Download Models project

## Features
- **Prefect** workflow orchestration
- **Dask** distributed computing
- **Loguru** structured logging
- **Ruff** linting and formatting
- **UV** package management
- **Click** CLI support
- **pydub** audio processing

## Installation

1. **Clone the template:**
   ```bash
   copier copy <template-source> schedule-download-models
   ```

2. **Install dependencies:**
   ```bash
   cd schedule-download-models
   uv sync
   ```

## Usage

### Development

```bash
# Start the development server
make dev

# Run locally (without Prefect server)
make local
```
### Prefect Operations

```bash
# Reset Prefect to local mode
make prefect-reset

# Create work pool
make prefect-create-work-pool

# Start worker
make prefect-worker

# Deploy flow
make prefect-deploy

# Run deployed flow
make prefect-run
```

### Remote Setup

```bash
# Setup remote worker
make remote-worker-setup

# Start remote worker
make remote-worker-start

# Deploy to remote server
make remote-deploy
```

## Project Structure

```
schedule-download-models/
├── config/
│   └── config.yaml          # Configuration file
├── src/
│   ├── __init__.py
│   ├── app.py              # Main application logic
│   ├── main.py             # Entry point
│   └── utils/              # Utility modules
│       ├── __init__.py
│       ├── config.py       # Configuration management
│       ├── custom_logging.py
│       ├── dask.py         # Dask utilities
│       └── utils.py
├── Makefile                # Common commands
├── pyproject.toml          # Project configuration
├── copier.yml              # Template configuration
└── README.md               # This file
```

## Configuration

The configuration is managed through `config/config.yaml`:

- **HTTP Server**: Port 13000
- **Dask Cluster**: Scheduler port 8786, Dashboard port 8787
- **Logging**: Level INFO, rotation 1 days, retention 5 days

## Development

### Code Quality

```bash
# Lint code
uv run ruff check .

# Format code
uv run ruff format .
```

### Testing
To enable testing, set `include_tests: true` when generating the project.

## Template Variables

This template uses the following variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `project_name` | Project name | `py-project-template` |
| `project_description` | Project description | `Add your description here` |
| `author_name` | Author name | `""` |
| `author_email` | Author email | `""` |
| `python_version` | Python version | `3.12` |
| `use_prefect` | Enable Prefect | `true` |
| `use_dask` | Enable Dask | `true` |
| `use_click` | Enable Click CLI | `true` |
| `use_pydub` | Enable pydub | `true` |
| `http_port` | HTTP server port | `13000` |
| `dask_scheduler_port` | Dask scheduler port | `8786` |
| `dask_dashboard_port` | Dask dashboard port | `8787` |
| `log_level` | Logging level | `INFO` |
| `log_rotation` | Log rotation period | `1 days` |
| `log_retention` | Log retention period | `5 days` |

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

This project is licensed under the MIT License.

## Acknowledgments

- [Copier](https://copier.readthedocs.io/) for project templating
- [Prefect](https://www.prefect.io/) for workflow orchestration
- [Dask](https://dask.org/) for distributed computing
- [UV](https://docs.astral.sh/uv/) for package management
- [Ruff](https://github.com/astral-sh/ruff) for linting and formatting