"""
Service integration layer for HF Downloader.

This module provides integration between CLI and all backend services,
ensuring proper dependency injection and consistent service management.
"""

from typing import Any

from loguru import logger

from ..core.config import Config, ConfigManager
from ..models.database import DatabaseManager
from ..services.configuration import ConfigurationService
from ..services.downloader import DownloaderService
from ..services.process_manager import ProcessManager
from ..services.scheduler import SchedulerService


class ServiceContainer:
    """Container for managing service dependencies and lifecycle."""

    def __init__(
        self, config_path: str, database_path: str, pid_path: str, log_level: str
    ):
        """Initialize service container."""
        logger.info(f"Initializing ServiceContainer with config: {config_path}")
        self.config_path = config_path
        self.database_path = database_path
        self.pid_path = pid_path
        self.log_level = log_level

        # Initialize services
        self._config_manager: ConfigManager | None = None
        self._config: Config | None = None
        self._db_manager: DatabaseManager | None = None
        self._downloader_service: DownloaderService | None = None
        self._scheduler_service: SchedulerService | None = None
        self._process_manager: ProcessManager | None = None
        self._configuration_service: ConfigurationService | None = None

        self._initialize_services()

    def _initialize_services(self):
        """Initialize all services with proper dependency injection."""
        try:
            # Initialize configuration
            self._config_manager = ConfigManager(self.config_path)
            self._config = self._config_manager.load_config()

            # Initialize database
            self._db_manager = DatabaseManager(self.database_path)

            # Initialize core services
            self._downloader_service = DownloaderService(
                self._config, self.database_path, self._config.models_file
            )
            self._scheduler_service = SchedulerService(self._config, self.database_path)
            self._process_manager = ProcessManager(
                self._config, self.database_path, self.pid_path, self.config_path
            )
            self._configuration_service = ConfigurationService(
                self._db_manager, self._config_manager
            )

            # Wire up dependencies
            self._scheduler_service.downloader_service = self._downloader_service

            # Set integration service reference in downloader service
            self._downloader_service.set_integration_service(self)

            logger.info("All services initialized successfully")

        except Exception as e:
            logger.error(f"Error initializing services: {e}")
            raise

    @property
    def config_manager(self) -> ConfigManager:
        """Get configuration manager."""
        if self._config_manager is None:
            raise RuntimeError("Config manager not initialized")
        return self._config_manager

    @property
    def config(self) -> Config:
        """Get configuration."""
        if self._config is None:
            raise RuntimeError("Config not initialized")
        return self._config

    @property
    def db_manager(self) -> DatabaseManager:
        """Get database manager."""
        if self._db_manager is None:
            raise RuntimeError("Database manager not initialized")
        return self._db_manager

    @property
    def downloader_service(self) -> DownloaderService:
        """Get downloader service."""
        if self._downloader_service is None:
            raise RuntimeError("Downloader service not initialized")
        return self._downloader_service

    @property
    def scheduler_service(self) -> SchedulerService:
        """Get scheduler service."""
        if self._scheduler_service is None:
            raise RuntimeError("Scheduler service not initialized")
        return self._scheduler_service

    @property
    def process_manager(self) -> ProcessManager:
        """Get process manager."""
        if self._process_manager is None:
            raise RuntimeError("Process manager not initialized")
        return self._process_manager

    @property
    def configuration_service(self) -> ConfigurationService:
        """Get configuration service."""
        if self._configuration_service is None:
            raise RuntimeError("Configuration service not initialized")
        return self._configuration_service

    def get_service_status(self) -> dict[str, Any]:
        """Get status of all services."""
        try:
            return {
                "config": {
                    "loaded": self._config is not None,
                    "path": self.config_path,
                },
                "database": {
                    "path": self.database_path,
                    "connected": self._db_manager is not None,
                },
                "downloader": {
                    "active_downloads": len(
                        self._downloader_service.get_active_downloads()
                    )
                    if self._downloader_service
                    else 0
                },
                "scheduler": {
                    "state": self._scheduler_service.get_status()["state"]
                    if self._scheduler_service
                    else "not_initialized"
                },
                "process_manager": {"pid_path": self.pid_path},
            }
        except Exception as e:
            logger.error(f"Error getting service status: {e}")
            return {"error": str(e)}

    def cleanup(self):
        """Clean up all services."""
        try:
            if self._downloader_service:
                self._downloader_service.cancel_all_downloads()

            if self._scheduler_service:
                self._scheduler_service.stop()

            logger.info("Services cleaned up successfully")

        except Exception as e:
            logger.error(f"Error during service cleanup: {e}")


class CLIIntegrationService:
    """Service for integrating CLI commands with backend services."""

    def __init__(self, service_container: ServiceContainer):
        """Initialize CLI integration service."""
        self.container = service_container

    def handle_daemon_start(self, foreground: bool = False) -> dict[str, Any]:
        """Handle daemon start command."""
        try:
            if foreground:
                # Start in foreground mode
                from ..daemon.main import Daemon

                daemon = Daemon(
                    config_path=self.container.config_path,
                    db_path=self.container.database_path,
                    pid_path=self.container.pid_path,
                    log_level=self.container.log_level,
                )
                success = daemon.start()
                return {
                    "status": "started" if success else "failed",
                    "foreground": True,
                }
            else:
                # Start in background mode
                result = self.container.process_manager.start_daemon()
                return result

        except Exception as e:
            logger.error(f"Error handling daemon start: {e}")
            return {"status": "error", "error": str(e)}

    def handle_daemon_stop(self) -> dict[str, Any]:
        """Handle daemon stop command."""
        try:
            result = self.container.process_manager.stop_daemon()
            return result

        except Exception as e:
            logger.error(f"Error handling daemon stop: {e}")
            return {"status": "error", "error": str(e)}

    def handle_daemon_status(self, detailed: bool = False) -> dict[str, Any]:
        """Handle daemon status command."""
        try:
            result = self.container.process_manager.get_daemon_status(detailed=detailed)
            return result

        except Exception as e:
            logger.error(f"Error handling daemon status: {e}")
            return {"status": "error", "error": str(e)}

    def handle_daemon_restart(self) -> dict[str, Any]:
        """Handle daemon restart command."""
        try:
            result = self.container.process_manager.restart_daemon()
            return result

        except Exception as e:
            logger.error(f"Error handling daemon restart: {e}")
            return {"status": "error", "error": str(e)}

    def handle_manual_download(self) -> dict[str, Any]:
        """Handle manual download command."""
        try:
            result = self.container.scheduler_service.trigger_manual_run()
            return result

        except Exception as e:
            logger.error(f"Error handling manual download: {e}")
            return {"status": "error", "error": str(e)}

    def handle_model_list(self, status_filter: str = "all") -> dict[str, Any]:
        """Handle model list command."""
        try:
            if status_filter == "all":
                # Get all models
                models = self.container.db_manager.get_all_models()
            else:
                models = self.container.db_manager.get_models_by_status(status_filter)

            return {
                "status": "success",
                "models": [model.to_dict() for model in models],
                "count": len(models),
            }

        except Exception as e:
            logger.error(f"Error handling model list: {e}")
            return {"status": "error", "error": str(e)}

    def handle_model_add(self, model_name: str) -> dict[str, Any]:
        """Handle model add command."""
        logger.info(f"Adding model: {model_name}")
        try:
            # Check if model already exists
            existing_model = self.container.db_manager.get_model_by_name(model_name)
            if existing_model:
                logger.info(f"Model {model_name} already exists")
                return {
                    "status": "exists",
                    "model": existing_model.to_dict(),
                    "message": f"Model {model_name} already exists",
                }

            # Create new model
            model = self.container.db_manager.create_model(
                name=model_name, metadata={"source": "cli"}
            )

            return {
                "status": "created",
                "model": model.to_dict(),
                "message": f"Model {model_name} added successfully",
            }

        except Exception as e:
            logger.error(f"Error handling model add: {e}")
            return {"status": "error", "error": str(e)}

    def handle_schedule_list(self) -> dict[str, Any]:
        """Handle schedule list command."""
        try:
            schedules = self.container.scheduler_service.get_all_schedules()
            return schedules

        except Exception as e:
            logger.error(f"Error handling schedule list: {e}")
            return {"status": "error", "error": str(e)}

    def handle_schedule_update(self, schedule_id: int, **kwargs) -> dict[str, Any]:
        """Handle schedule update command."""
        try:
            result = self.container.scheduler_service.update_schedule(
                schedule_id, **kwargs
            )
            return result

        except Exception as e:
            logger.error(f"Error handling schedule update: {e}")
            return {"status": "error", "error": str(e)}

    def handle_schedule_disable(self, schedule_id: int) -> dict[str, Any]:
        """Handle schedule disable command."""
        try:
            result = self.container.scheduler_service.disable_schedule(schedule_id)
            return result

        except Exception as e:
            logger.error(f"Error handling schedule disable: {e}")
            return {"status": "error", "error": str(e)}

    def handle_schedule_delete(self, schedule_id: int) -> dict[str, Any]:
        """Handle schedule delete command."""
        try:
            result = self.container.scheduler_service.delete_schedule(schedule_id)
            return result

        except Exception as e:
            logger.error(f"Error handling schedule delete: {e}")
            return {"status": "error", "error": str(e)}

    def handle_schedule_backup(self) -> dict[str, Any]:
        """Handle schedule backup command."""
        try:
            result = self.container.scheduler_service.backup_schedules()
            return result

        except Exception as e:
            logger.error(f"Error handling schedule backup: {e}")
            return {"status": "error", "error": str(e)}

    def handle_schedule_restore(self) -> dict[str, Any]:
        """Handle schedule restore command."""
        try:
            result = self.container.scheduler_service.restore_schedules_from_backup()
            return result

        except Exception as e:
            logger.error(f"Error handling schedule restore: {e}")
            return {"status": "error", "error": str(e)}

    def handle_schedule_create(
        self,
        name: str,
        schedule_type: str,
        time_str: str,
        day_of_week: int | None = None,
        max_concurrent_downloads: int = 1,
    ) -> dict[str, Any]:
        """Handle schedule create command."""
        try:
            result = self.container.scheduler_service.create_schedule(
                name=name,
                schedule_type=schedule_type,
                time_str=time_str,
                day_of_week=day_of_week,
                max_concurrent_downloads=max_concurrent_downloads,
            )
            return result

        except Exception as e:
            logger.error(f"Error handling schedule create: {e}")
            return {"status": "error", "error": str(e)}

    def handle_schedule_enable(self, schedule_id: int) -> dict[str, Any]:
        """Handle schedule enable command."""
        try:
            result = self.container.scheduler_service.enable_schedule(schedule_id)
            return result

        except Exception as e:
            logger.error(f"Error handling schedule enable: {e}")
            return {"status": "error", "error": str(e)}

    def get_system_status(self) -> dict[str, Any]:
        """Get comprehensive system status."""
        try:
            service_status = self.container.get_service_status()

            # Add additional system information
            system_status = {
                "services": service_status,
                "configuration": {
                    "path": self.container.config_path,
                    "valid": self.container.config_manager.validate_config(),
                },
                "scheduler": self.container.scheduler_service.get_status()
                if self.container.scheduler_service
                else None,
            }

            return system_status

        except Exception as e:
            logger.error(f"Error getting system status: {e}")
            return {"status": "error", "error": str(e)}

    def handle_session_list(
        self, model_name: str | None = None, status: str | None = None
    ) -> dict[str, Any]:
        """Handle session list command."""
        try:
            if model_name:
                # Get sessions for specific model
                model = self.container.db_manager.get_model_by_name(model_name)
                if not model:
                    return {
                        "status": "not_found",
                        "model": model_name,
                        "message": f"Model '{model_name}' not found",
                    }
                sessions = self.container.db_manager.get_download_history(
                    model.id, limit=50
                )
            elif status:
                # Get sessions by status
                sessions = self.container.db_manager.get_sessions_by_status(status)
            else:
                # Get all recent sessions
                sessions = self.container.db_manager.get_active_download_sessions()

            return {
                "status": "success",
                "sessions": [session.to_dict() for session in sessions],
                "count": len(sessions),
                "filter_model": model_name,
                "filter_status": status,
            }

        except Exception as e:
            logger.error(f"Error handling session list: {e}")
            return {"status": "error", "error": str(e)}

    def handle_session_details(self, session_id: int) -> dict[str, Any]:
        """Handle session details command."""
        try:
            result = self.container.downloader_service.get_session_details(session_id)
            return result

        except Exception as e:
            logger.error(f"Error handling session details: {e}")
            return {"status": "error", "session_id": session_id, "error": str(e)}

    def handle_session_cancel(self, session_id: int) -> dict[str, Any]:
        """Handle session cancel command."""
        try:
            result = self.container.downloader_service.cancel_session(session_id)
            return result

        except Exception as e:
            logger.error(f"Error handling session cancel: {e}")
            return {"status": "error", "session_id": session_id, "error": str(e)}

    def handle_session_retry(
        self, session_id: int, schedule_id: int | None = None
    ) -> dict[str, Any]:
        """Handle session retry command."""
        try:
            result = self.container.downloader_service.retry_failed_download(
                session_id, schedule_id
            )
            return result

        except Exception as e:
            logger.error(f"Error handling session retry: {e}")
            return {"status": "error", "session_id": session_id, "error": str(e)}

    def handle_download_statistics(
        self,
        model_name: str | None = None,
        schedule_id: int | None = None,
        time_range_days: int | None = None,
    ) -> dict[str, Any]:
        """Handle download statistics command."""
        try:
            # Convert model name to model ID if provided
            model_id = None
            if model_name:
                model = self.container.db_manager.get_model_by_name(model_name)
                if not model:
                    return {
                        "status": "not_found",
                        "model": model_name,
                        "message": f"Model '{model_name}' not found",
                    }
                model_id = model.id

            result = self.container.downloader_service.get_download_statistics(
                model_id=model_id,
                schedule_id=schedule_id,
                time_range_days=time_range_days,
            )
            return result

        except Exception as e:
            logger.error(f"Error handling download statistics: {e}")
            return {"status": "error", "error": str(e)}

    def handle_session_cleanup(self, days_to_keep: int = 30) -> dict[str, Any]:
        """Handle session cleanup command."""
        try:
            result = self.container.db_manager.cleanup_old_sessions(days_to_keep)
            return result

        except Exception as e:
            logger.error(f"Error handling session cleanup: {e}")
            return {"status": "error", "error": str(e)}
