"""
Configuration management for HF Downloader.

This module handles loading and managing application configuration
from YAML files and environment variables.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class Config:
    """Application configuration."""

    download_directory: str = "./models"
    log_level: str = "INFO"
    max_retries: int = 5
    timeout_seconds: int = 3600
    database_path: str = "./hf_downloader.db"
    pid_file: str = "./hf_downloader.pid"
    foreground: bool = False
    concurrent_downloads: int = 1
    models_file: str = "./config/models.json"

    # Hugging Face specific
    hf_token: str | None = field(default_factory=lambda: os.getenv("HF_TOKEN"))

    # Logging - all logging config is under log field
    log: dict[str, Any] = field(
        default_factory=lambda: {
            "level": "INFO",
            "file": "./logs/hf_downloader.log",
            "max_size": 10 * 1024 * 1024,  # 10MB
            "backup_count": 5,
            "rotation": "1 days",
            "retention": "5 days",
            "format": "<level>{level: <8}</level> <green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> - <blue>[{process.id}]</blue> - <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
        }
    )

    # Network
    chunk_size: int = 1024 * 1024  # 1MB
    user_agent: str = "hf-downloader/1.0.0"

    # Default schedule configuration
    default_schedule: dict[str, Any] | None = None

    # Monitoring configuration
    monitoring: dict[str, Any] = field(
        default_factory=lambda: {
            "health_check_interval": 300,  # 5 minutes
        }
    )

    @classmethod
    def from_file(cls, config_path: str) -> "Config":
        """Load configuration from YAML file."""
        config_file = Path(config_path)
        if not config_file.exists():
            return cls()

        with open(config_file) as f:
            config_data = yaml.safe_load(f) or {}

        return cls(**config_data)

    @classmethod
    def from_env(cls) -> "Config":
        """Load configuration from environment variables."""
        config = cls()

        # Override with environment variables
        if os.getenv("HF_DOWNLOADER_DOWNLOAD_DIR"):
            config.download_directory = os.getenv("HF_DOWNLOADER_DOWNLOAD_DIR")
        if os.getenv("HF_DOWNLOADER_LOG_LEVEL"):
            config.log_level = os.getenv("HF_DOWNLOADER_LOG_LEVEL")
        if os.getenv("HF_DOWNLOADER_MAX_RETRIES"):
            config.max_retries = int(os.getenv("HF_DOWNLOADER_MAX_RETRIES"))
        if os.getenv("HF_DOWNLOADER_TIMEOUT"):
            config.timeout_seconds = int(os.getenv("HF_DOWNLOADER_TIMEOUT"))
        if os.getenv("HF_DOWNLOADER_DB_PATH"):
            config.database_path = os.getenv("HF_DOWNLOADER_DB_PATH")

        return config

    def to_dict(self) -> dict[str, Any]:
        """Convert configuration to dictionary."""
        return {
            "download_directory": self.download_directory,
            "log_level": self.log_level,
            "max_retries": self.max_retries,
            "timeout_seconds": self.timeout_seconds,
            "database_path": self.database_path,
            "pid_file": self.pid_file,
            "foreground": self.foreground,
            "concurrent_downloads": self.concurrent_downloads,
            "models_file": self.models_file,
            "hf_token": self.hf_token,
            "chunk_size": self.chunk_size,
            "user_agent": self.user_agent,
            "log": self.log,
            "default_schedule": self.default_schedule,
            "monitoring": self.monitoring,
        }

    def save_to_file(self, config_path: str):
        """Save configuration to YAML file."""
        config_file = Path(config_path)
        config_file.parent.mkdir(parents=True, exist_ok=True)

        with open(config_file, "w") as f:
            yaml.dump(self.to_dict(), f, default_flow_style=False)

    def validate(self) -> bool:
        """Validate configuration values."""
        errors = []

        if self.max_retries < 0:
            errors.append("max_retries must be non-negative")

        if self.timeout_seconds <= 0:
            errors.append("timeout_seconds must be positive")

        if self.concurrent_downloads < 1 or self.concurrent_downloads > 10:
            errors.append("concurrent_downloads must be between 1 and 10")

        if self.chunk_size <= 0:
            errors.append("chunk_size must be positive")

        if self.log_level not in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
            errors.append(
                "log_level must be one of: DEBUG, INFO, WARNING, ERROR, CRITICAL"
            )

        if errors:
            raise ValueError(f"Configuration validation failed: {'; '.join(errors)}")

        return True


class ConfigManager:
    """Manages application configuration."""

    def __init__(self, config_path: str | None = None):
        """Initialize config manager."""
        self.config_path = config_path or "./config/default.yaml"
        self._config = None

    def load_config(self) -> Config:
        """Load configuration from file and environment."""
        if self._config is None:
            # Load from file first
            config = Config.from_file(self.config_path)

            # Override with specific environment variables if set
            env_overrides = {
                "download_directory": os.getenv("HF_DOWNLOADER_DOWNLOAD_DIR"),
                "log_level": os.getenv("HF_DOWNLOADER_LOG_LEVEL"),
                "max_retries": os.getenv("HF_DOWNLOADER_MAX_RETRIES"),
                "timeout_seconds": os.getenv("HF_DOWNLOADER_TIMEOUT"),
                "database_path": os.getenv("HF_DOWNLOADER_DB_PATH"),
                "pid_file": os.getenv("HF_DOWNLOADER_PID_FILE"),
                "models_file": os.getenv("HF_DOWNLOADER_MODELS_FILE"),
                "chunk_size": os.getenv("HF_DOWNLOADER_CHUNK_SIZE"),
                "user_agent": os.getenv("HF_DOWNLOADER_USER_AGENT"),
                "concurrent_downloads": os.getenv("HF_DOWNLOADER_CONCURRENT_DOWNLOADS"),
            }

            for key, value in env_overrides.items():
                if value is not None:  # Only override if env var is set
                    if key in [
                        "max_retries",
                        "timeout_seconds",
                        "chunk_size",
                        "concurrent_downloads",
                    ]:
                        setattr(config, key, int(value))
                    elif key in ["foreground"]:
                        setattr(
                            config, key, value.lower() in ["true", "1", "yes", "on"]
                        )
                    else:
                        setattr(config, key, value)

            # Validate configuration
            config.validate()
            self._config = config

        return self._config

    def reload_config(self) -> Config:
        """Reload configuration from file and environment."""
        self._config = None
        return self.load_config()

    def get_config(self) -> Config:
        """Get current configuration."""
        return self.load_config()

    def update_config(self, updates: dict[str, Any]) -> Config:
        """Update configuration with new values."""
        config = self.load_config()

        for key, value in updates.items():
            if hasattr(config, key):
                setattr(config, key, value)

        config.validate()
        self._config = config
        return config

    def save_config(self):
        """Save current configuration to file."""
        config = self.get_config()
        config.save_to_file(self.config_path)

    @property
    def models_file_path(self) -> str:
        """Get models file path."""
        return self.get_config().models_file
