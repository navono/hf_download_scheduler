"""
Configuration service for HF Downloader.

This service provides integration between the configuration management system
and the database, enabling persistent configuration storage and retrieval.
"""

import json
from datetime import UTC, datetime
from typing import Any

from ..core.config import Config, ConfigManager
from ..models.database import DatabaseManager, SystemConfiguration


class ConfigurationService:
    """Service for managing configuration integration with database."""

    def __init__(self, db_manager: DatabaseManager, config_manager: ConfigManager):
        """Initialize configuration service."""
        self.db_manager = db_manager
        self.config_manager = config_manager

    def load_and_sync_config(self) -> Config:
        """Load configuration and sync with database."""
        # Load configuration from files and environment
        config = self.config_manager.load_config()

        # Sync configuration to database
        self._sync_config_to_database(config)

        return config

    def _sync_config_to_database(self, config: Config):
        """Sync configuration values to database."""
        config_mappings = {
            "download_directory": (
                "Directory for downloaded models",
                config.download_directory,
            ),
            "log_level": ("Logging level", config.log_level),
            "max_retries": ("Maximum download retries", str(config.max_retries)),
            "timeout_seconds": (
                "Download timeout in seconds",
                str(config.timeout_seconds),
            ),
            "database_path": ("Database file path", config.database_path),
            "pid_file": ("PID file path", config.pid_file),
            "concurrent_downloads": (
                "Maximum concurrent downloads",
                str(config.concurrent_downloads),
            ),
            "models_file": ("Models configuration file", config.models_file),
            "log_file": ("Log file path", config.log_file or ""),
            "log_max_size": ("Maximum log size in bytes", str(config.log_max_size)),
            "log_backup_count": (
                "Number of log backup files",
                str(config.log_backup_count),
            ),
            "chunk_size": ("Download chunk size in bytes", str(config.chunk_size)),
            "user_agent": ("User agent string", config.user_agent),
        }

        for key, (description, value) in config_mappings.items():
            self.db_manager.set_system_config(key, value, description)

    def get_config_from_database(self) -> dict[str, Any]:
        """Get all configuration values from database."""
        config_dict = {}

        # Get all system configurations from database
        with self.db_manager.get_session() as session:
            configs = session.query(SystemConfiguration).all()
            for config in configs:
                config_dict[config.key] = config.value

        return config_dict

    def update_config_and_persist(self, updates: dict[str, Any]) -> Config:
        """Update configuration and persist to both file and database."""
        # Update configuration in memory
        config = self.config_manager.update_config(updates)

        # Persist to file
        self.config_manager.save_config()

        # Sync to database
        self._sync_config_to_database(config)

        return config

    def get_config_value(self, key: str, default: Any = None) -> Any:
        """Get configuration value with fallback order: memory -> database -> default."""
        # First try from current config in memory
        config = self.config_manager.get_config()
        if hasattr(config, key):
            value = getattr(config, key)
            if value is not None:
                return value

        # Then try from database
        db_value = self.db_manager.get_system_config(key)
        if db_value is not None:
            # Convert to appropriate type
            return self._convert_config_value(key, db_value)

        # Finally use default
        return default

    def _convert_config_value(self, key: str, value: str) -> Any:
        """Convert string value from database to appropriate type."""
        int_keys = [
            "max_retries",
            "timeout_seconds",
            "concurrent_downloads",
            "log_max_size",
            "log_backup_count",
            "chunk_size",
        ]
        bool_keys = ["foreground"]

        if key in int_keys:
            return int(value)
        elif key in bool_keys:
            return value.lower() in ["true", "1", "yes", "on"]
        else:
            return value

    def get_config_history(self, key: str, limit: int = 10) -> list[dict[str, Any]]:
        """Get configuration change history for a specific key."""
        # This would require adding a configuration history table
        # For now, return empty list as placeholder
        return []

    def export_config(self, format: str = "json") -> str:
        """Export current configuration in specified format."""
        config = self.config_manager.get_config()

        if format.lower() == "json":
            return json.dumps(config.to_dict(), indent=2)
        elif format.lower() == "yaml":
            import yaml

            return yaml.dump(config.to_dict(), default_flow_style=False)
        else:
            raise ValueError(f"Unsupported export format: {format}")

    def import_config(self, config_data: str, format: str = "json") -> Config:
        """Import configuration from string and sync with database."""
        if format.lower() == "json":
            config_dict = json.loads(config_data)
        elif format.lower() == "yaml":
            import yaml

            config_dict = yaml.safe_load(config_data)
        else:
            raise ValueError(f"Unsupported import format: {format}")

        return self.update_config_and_persist(config_dict)

    def validate_config_integrity(self) -> dict[str, Any]:
        """Validate integrity between configuration sources."""
        config = self.config_manager.get_config()
        db_config = self.get_config_from_database()

        discrepancies = []
        for key, value in config.to_dict().items():
            if key in db_config:
                db_value = self._convert_config_value(key, db_config[key])
                # Handle None vs empty string equivalence for certain fields
                if value is None and db_value == "":
                    continue  # Consider None and empty string as equivalent
                if value != db_value:
                    discrepancies.append(
                        {"key": key, "file_value": value, "database_value": db_value}
                    )

        return {
            "is_consistent": len(discrepancies) == 0,
            "discrepancies": discrepancies,
            "config_source": "file",
            "database_config": db_config,
        }

    def reset_config_to_defaults(self) -> Config:
        """Reset configuration to default values and persist."""
        # Create default config
        default_config = Config()

        # Update config manager with defaults
        for key, value in default_config.to_dict().items():
            self.config_manager.update_config({key: value})

        # Save to file and sync to database
        self.config_manager.save_config()
        self._sync_config_to_database(default_config)

        return default_config

    def get_config_summary(self) -> dict[str, Any]:
        """Get a summary of current configuration state."""
        config = self.config_manager.get_config()
        db_config = self.get_config_from_database()

        return {
            "config_source": self.config_manager.config_path,
            "total_config_keys": len(config.to_dict()),
            "database_config_keys": len(db_config),
            "hf_token_configured": bool(config.hf_token),
            "log_level": config.log_level,
            "download_directory": config.download_directory,
            "max_concurrent_downloads": config.concurrent_downloads,
            "last_sync": datetime.now(UTC).isoformat(),
        }
