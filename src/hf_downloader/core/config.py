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

    # Failed model retry settings
    retry_failed_models: bool = True
    max_failed_retries: int = 3
    retry_reset_hours: int = 24

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

    # Time window configuration is now nested under default_schedule

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
        if os.getenv("HF_DOWNLOADER_RETRY_FAILED_MODELS"):
            config.retry_failed_models = os.getenv("HF_DOWNLOADER_RETRY_FAILED_MODELS").lower() in ("true", "1", "yes")
        if os.getenv("HF_DOWNLOADER_MAX_FAILED_RETRIES"):
            config.max_failed_retries = int(os.getenv("HF_DOWNLOADER_MAX_FAILED_RETRIES"))
        if os.getenv("HF_DOWNLOADER_RETRY_RESET_HOURS"):
            config.retry_reset_hours = int(os.getenv("HF_DOWNLOADER_RETRY_RESET_HOURS"))
        if os.getenv("HF_DOWNLOADER_TIMEOUT"):
            config.timeout_seconds = int(os.getenv("HF_DOWNLOADER_TIMEOUT"))
        if os.getenv("HF_DOWNLOADER_DB_PATH"):
            config.database_path = os.getenv("HF_DOWNLOADER_DB_PATH")

        # Handle time window environment variables (now nested in default_schedule)
        if os.getenv("HF_DOWNLOADER_TIME_WINDOW_ENABLED"):
            if not config.default_schedule:
                config.default_schedule = {}
            if "time_window" not in config.default_schedule:
                config.default_schedule["time_window"] = {}
            config.default_schedule["time_window"]["enabled"] = os.getenv(
                "HF_DOWNLOADER_TIME_WINDOW_ENABLED"
            ).lower() in ["true", "1", "yes", "on"]
        if os.getenv("HF_DOWNLOADER_TIME_WINDOW_START"):
            if not config.default_schedule:
                config.default_schedule = {}
            if "time_window" not in config.default_schedule:
                config.default_schedule["time_window"] = {}
            config.default_schedule["time_window"]["start_time"] = os.getenv(
                "HF_DOWNLOADER_TIME_WINDOW_START"
            )
        if os.getenv("HF_DOWNLOADER_TIME_WINDOW_END"):
            if not config.default_schedule:
                config.default_schedule = {}
            if "time_window" not in config.default_schedule:
                config.default_schedule["time_window"] = {}
            config.default_schedule["time_window"]["end_time"] = os.getenv(
                "HF_DOWNLOADER_TIME_WINDOW_END"
            )
        if os.getenv("HF_DOWNLOADER_TIME_WINDOW_TIMEZONE"):
            if not config.default_schedule:
                config.default_schedule = {}
            if "time_window" not in config.default_schedule:
                config.default_schedule["time_window"] = {}
            config.default_schedule["time_window"]["timezone"] = os.getenv(
                "HF_DOWNLOADER_TIME_WINDOW_TIMEZONE"
            )

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
        if self.retry_failed_models and self.max_failed_retries < 0:
            errors.append("max_failed_retries must be non-negative when retry_failed_models is enabled")
        if self.retry_failed_models and self.retry_reset_hours <= 0:
            errors.append("retry_reset_hours must be positive when retry_failed_models is enabled")

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

        # Validate time window configuration if nested in default_schedule
        if self.default_schedule and "time_window" in self.default_schedule:
            tw_errors = self._validate_time_window(self.default_schedule["time_window"])
            errors.extend(tw_errors)

        if errors:
            raise ValueError(f"Configuration validation failed: {'; '.join(errors)}")

        return True

    def _validate_time_window(self, time_window: dict[str, Any]) -> list[str]:
        """Validate time window configuration."""
        errors = []

        # Check required fields
        if not isinstance(time_window.get("enabled"), bool):
            errors.append("time_window.enabled must be a boolean")

        # Validate time format
        start_time = time_window.get("start_time", "22:00")
        end_time = time_window.get("end_time", "07:00")

        if not self._validate_time_format(start_time):
            errors.append(f"Invalid start_time format: {start_time}. Expected HH:MM")

        if not self._validate_time_format(end_time):
            errors.append(f"Invalid end_time format: {end_time}. Expected HH:MM")

        # Validate timezone
        timezone = time_window.get("timezone", "local")
        valid_timezones = ["local", "UTC+8"]
        if timezone not in valid_timezones:
            errors.append(
                f"Unsupported timezone: {timezone}. Supported timezones: {', '.join(valid_timezones)}"
            )

        # Validate weekend configuration
        weekend_enabled = time_window.get("weekend_enabled", False)
        if not isinstance(weekend_enabled, bool):
            errors.append("time_window.weekend_enabled must be a boolean")

        weekend_days = time_window.get("weekend_days", [])
        if weekend_enabled and not isinstance(weekend_days, list):
            errors.append("time_window.weekend_days must be a list when weekend_enabled is true")

        if isinstance(weekend_days, list):
            valid_days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
            for day in weekend_days:
                if not isinstance(day, str) or day.lower() not in valid_days:
                    errors.append(f"Invalid weekend day: {day}. Valid days: {', '.join(valid_days)}")

        return errors

    def _validate_time_format(self, time_str: str) -> bool:
        """Validate time format HH:MM."""
        if not time_str or len(time_str) != 5:
            return False

        if time_str[2] != ":":
            return False

        try:
            hours = int(time_str[:2])
            minutes = int(time_str[3:5])

            if hours < 0 or hours > 23:
                return False
            if minutes < 0 or minutes > 59:
                return False

            return True
        except ValueError:
            return False


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
                "time_window_enabled": os.getenv("HF_DOWNLOADER_TIME_WINDOW_ENABLED"),
                "time_window_start": os.getenv("HF_DOWNLOADER_TIME_WINDOW_START"),
                "time_window_end": os.getenv("HF_DOWNLOADER_TIME_WINDOW_END"),
                "time_window_timezone": os.getenv("HF_DOWNLOADER_TIME_WINDOW_TIMEZONE"),
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
                    elif key in [
                        "time_window_enabled",
                        "time_window_start",
                        "time_window_end",
                        "time_window_timezone",
                    ]:
                        # Handle time window nested configuration (now under default_schedule)
                        if not config.default_schedule:
                            config.default_schedule = {}
                        if "time_window" not in config.default_schedule:
                            config.default_schedule["time_window"] = {}

                        # Map environment variable names to time window keys
                        tw_key_map = {
                            "time_window_enabled": "enabled",
                            "time_window_start": "start_time",
                            "time_window_end": "end_time",
                            "time_window_timezone": "timezone",
                        }

                        tw_key = tw_key_map.get(key, key)
                        if key == "time_window_enabled":
                            config.default_schedule["time_window"][tw_key] = (
                                value.lower()
                                in [
                                    "true",
                                    "1",
                                    "yes",
                                    "on",
                                ]
                            )
                        else:
                            config.default_schedule["time_window"][tw_key] = value
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
