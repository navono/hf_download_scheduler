"""
Integration service for HF Downloader.

This module provides a unified integration layer that combines all services
with proper error handling, logging, and monitoring capabilities.
"""

import os
import time
from collections.abc import Callable
from datetime import UTC, datetime
from threading import Lock, Thread
from typing import Any

from loguru import logger

from ..utils import Config, CustomizeLogger
from .cli_integration import CLIIntegrationService, ServiceContainer
from .error_handling import (
    ErrorContext,
    ErrorHandler,
    ErrorReporter,
    ErrorSeverity,
    handle_errors,
)
from .model_sync import ModelSyncService

# Use the same logger instance as the main module
gen_config = Config().get_config()
# Override the logger with the one from CustomizeLogger
CustomizeLogger.make_logger(gen_config["log"])


class IntegrationService:
    """Unified integration service for HF Downloader."""

    def __init__(
        self, config_path: str, database_path: str, pid_path: str, log_level: str
    ):
        """Initialize integration service."""
        self.config_path = config_path
        self.database_path = database_path
        self.pid_path = pid_path
        self.log_level = log_level

        # Initialize service container
        self.service_container = ServiceContainer(
            config_path, database_path, pid_path, log_level
        )
        self.cli_integration = CLIIntegrationService(self.service_container)

        # Get config
        self.config = self.service_container.config

        # Initialize model sync service
        self.model_sync_service = ModelSyncService(
            self.service_container.db_manager,
            self.service_container.config_manager.models_file_path,
        )

        # Initialize error handling
        self.error_handler = ErrorHandler()
        self.error_reporter = ErrorReporter()

        # Monitoring
        self.operation_stats: dict[str, dict[str, Any]] = {}
        self.health_check_thread: Thread | None = None
        self.models_watch_thread: Thread | None = None
        self.shutdown_event = False
        self.stats_lock = Lock()

        # 记录 models.json 文件的最后修改时间
        self.models_file_last_modified = self._get_models_file_mtime()

        # Register error callbacks
        self._register_error_callbacks()

        # 在启动时自动同步模型
        logger.info("Auto-syncing models from JSON to database on startup")
        self.sync_models_json_to_db()

        # Initialize monitoring
        self._start_health_monitoring()

        # 启动模型文件监控
        self._start_models_watch()

    def _register_error_callbacks(self):
        """Register error callbacks."""
        self.error_handler.register_callback(
            "ConfigurationError", self._handle_config_error
        )
        self.error_handler.register_callback(
            "DatabaseError", self._handle_database_error
        )
        self.error_handler.register_callback(
            "DownloadError", self._handle_download_error
        )
        self.error_handler.register_callback(
            "ScheduleError", self._handle_schedule_error
        )
        self.error_handler.register_callback("ProcessError", self._handle_process_error)

    def _handle_config_error(
        self, error: Exception, context: ErrorContext | None = None, **kwargs
    ):
        """Handle configuration errors."""
        logger.info(
            "ERROR",
            "Configuration error detected",
            error=str(error),
            context=context.to_dict() if context else None,
        )

    def _handle_database_error(
        self, error: Exception, context: ErrorContext | None = None, **kwargs
    ):
        """Handle database errors."""
        logger.info(
            "ERROR",
            "Database error detected",
            error=str(error),
            context=context.to_dict() if context else None,
        )

    def _handle_download_error(
        self, error: Exception, context: ErrorContext | None = None, **kwargs
    ):
        """Handle download errors."""
        logger.info(
            "ERROR",
            "Download error detected",
            error=str(error),
            context=context.to_dict() if context else None,
        )

    def _handle_schedule_error(
        self, error: Exception, context: ErrorContext | None = None, **kwargs
    ):
        """Handle schedule errors."""
        logger.info(
            "ERROR",
            "Schedule error detected",
            error=str(error),
            context=context.to_dict() if context else None,
        )

    def _handle_process_error(
        self, error: Exception, context: ErrorContext | None = None, **kwargs
    ):
        """Handle process errors."""
        logger.info(
            "CRITICAL",
            "Process error detected",
            error=str(error),
            context=context.to_dict() if context else None,
        )

    @handle_errors("IntegrationService", "health_check", reraise=False)
    def _health_monitoring_loop(self):
        """Health monitoring loop."""
        # 尝试从配置文件中读取
        # 从配置文件中读取健康检查周期，默认为 300 秒（5 分钟）
        health_check_interval = 300  # 默认值

        if hasattr(self.config, "monitoring") and isinstance(
            self.config.monitoring, dict
        ):
            health_check_interval = self.config.monitoring.get(
                "health_check_interval", 300
            )

        logger.debug(f"Health check interval set to {health_check_interval} seconds")

        while not self.shutdown_event:
            try:
                self._perform_health_check()
                time.sleep(health_check_interval)
            except Exception as e:
                logger.error(
                    e,
                    ErrorContext("health_monitoring", "IntegrationService"),
                    ErrorSeverity.ERROR,
                )
                time.sleep(30)  # Wait before retry

    def _perform_health_check(self):
        """Perform health check of all services."""
        health_status = {"timestamp": datetime.now(UTC).isoformat(), "services": {}}

        # Check database
        try:
            db_health = self.service_container.db_manager.get_database_stats()
            health_status["services"]["database"] = {
                "status": "healthy",
                "stats": db_health,
            }
        except Exception as e:
            health_status["services"]["database"] = {
                "status": "unhealthy",
                "error": str(e),
            }

        # Check downloader
        try:
            active_downloads = (
                self.service_container.downloader_service.get_active_downloads()
            )
            health_status["services"]["downloader"] = {
                "status": "healthy",
                "active_downloads": len(active_downloads),
            }
        except Exception as e:
            health_status["services"]["downloader"] = {
                "status": "unhealthy",
                "error": str(e),
            }

        # Check scheduler
        try:
            scheduler_status = self.service_container.scheduler_service.get_status()
            health_status["services"]["scheduler"] = {
                "status": "healthy",
                "state": scheduler_status.get("state", "unknown"),
            }
        except Exception as e:
            health_status["services"]["scheduler"] = {
                "status": "unhealthy",
                "error": str(e),
            }

        # Update health stats
        with self.stats_lock:
            self.operation_stats["health_check"] = {
                "last_check": health_status["timestamp"],
                "status": health_status["services"],
            }

        logger.info("INFO", "Health check completed", health_status=health_status)

    def _get_models_file_mtime(self) -> float:
        """Get the last modification time of the models.json file."""
        try:
            models_file_path = self.service_container.config_manager.models_file_path
            return os.path.getmtime(models_file_path)
        except Exception as e:
            logger.error(f"Error getting models file mtime: {e}")
            return 0

    def _start_health_monitoring(self):
        """Start health monitoring thread."""
        self.health_check_thread = Thread(
            target=self._health_monitoring_loop, daemon=True, name="HealthMonitor"
        )
        self.health_check_thread.start()

    def _start_models_watch(self):
        """Start models file watch thread."""
        self.models_watch_thread = Thread(
            target=self._models_watch_loop, daemon=True, name="ModelsWatcher"
        )
        self.models_watch_thread.start()

    def _models_watch_loop(self):
        """Models file watch loop."""
        # 尝试从配置文件中读取
        if hasattr(self.config, "monitoring") and isinstance(
            self.config.monitoring, dict
        ):
            models_check_interval = self.config.monitoring.get(
                "models_check_interval", 60
            )
        else:
            models_check_interval = 60
        logger.debug(f"Models check interval set to {models_check_interval} seconds")
        while not self.shutdown_event:
            try:
                logger.trace("Model config check modified")
                # 检查文件是否有变化
                current_mtime = self._get_models_file_mtime()
                if current_mtime > self.models_file_last_modified:
                    logger.info("Models file changed, resyncing with database")
                    self.sync_models_json_to_db()
                    self.models_file_last_modified = current_mtime

                # 将数据库中的模型状态同步到 models.json 文件
                self.model_sync_service.sync_db_status_to_json()

                time.sleep(models_check_interval)
            except Exception as e:
                logger.error(f"Error in models watch loop: {e}")
                time.sleep(30)  # Wait before retry

    def shutdown(self):
        """Shutdown integration service."""
        logger.info("INFO", "Shutting down integration service")
        self.shutdown_event = True

        # Stop health monitoring
        if self.health_check_thread and self.health_check_thread.is_alive():
            self.health_check_thread.join(timeout=5)

        # Stop models watch
        if self.models_watch_thread and self.models_watch_thread.is_alive():
            self.models_watch_thread.join(timeout=5)

        # Cleanup services
        try:
            self.service_container.cleanup()
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")

    @handle_errors("IntegrationService", "system_status", reraise=False)
    def get_system_status(self) -> dict[str, Any]:
        """Get comprehensive system status."""
        # Using direct logging instead of OperationTimer
        logger.info("get_system_status", "IntegrationService")
        system_status = self.cli_integration.get_system_status()

        # Add error handling information
        system_status["error_handling"] = {
            "error_counts": self.error_reporter.error_counts,
            "recent_errors": len(self.error_reporter.recent_errors),
            "error_rate": self.error_reporter._calculate_error_rate(),
        }

        # Add operation statistics
        with self.stats_lock:
            system_status["operations"] = self.operation_stats

        return system_status

    @handle_errors("IntegrationService", "safe_download", reraise=False)
    def safe_download_model(
        self, model_name: str, schedule_id: int | None = None
    ) -> dict[str, Any]:
        """Safely download a model with error handling."""
        # Using direct logging instead of OperationTimer
        logger.info("safe_download_model", "IntegrationService", model_name=model_name)
        try:
            result = self.service_container.downloader_service.download_model(
                model_name, schedule_id=schedule_id
            )

            logger.info(f"Download model operation successful: {model_name}")

            return result

        except Exception as e:
            context = ErrorContext(
                "download_model", "IntegrationService", model_name=model_name
            )
            self.error_handler.handle_error(e, context, reraise=False)

            return {"status": "failed", "model": model_name, "error": str(e)}

    @handle_errors("IntegrationService", "safe_manual_download", reraise=False)
    def safe_manual_download(self) -> dict[str, Any]:
        """Safely trigger manual download with error handling."""
        # Using direct logging instead of OperationTimer
        logger.info("safe_manual_download", "IntegrationService")
        try:
            result = self.cli_integration.handle_manual_download()

            logger.info("Manual download operation successful")

            return result

        except Exception as e:
            context = ErrorContext("manual_download", "IntegrationService")
            self.error_handler.handle_error(e, context, reraise=False)

            return {"status": "failed", "error": str(e)}

    @handle_errors("IntegrationService", "safe_daemon_start", reraise=False)
    def safe_daemon_start(self, foreground: bool = False) -> dict[str, Any]:
        """Safely start daemon with error handling."""
        # Using direct logging instead of OperationTimer
        logger.info("safe_daemon_start", "IntegrationService", foreground=foreground)
        try:
            result = self.cli_integration.handle_daemon_start(foreground)

            logger.info(f"Daemon start operation successful, foreground={foreground}")

            return result

        except Exception as e:
            context = ErrorContext(
                "daemon_start", "IntegrationService", foreground=foreground
            )
            self.error_handler.handle_error(e, context, reraise=False)

            return {"status": "failed", "error": str(e)}

    @handle_errors("IntegrationService", "safe_daemon_stop", reraise=False)
    def safe_daemon_stop(self) -> dict[str, Any]:
        """Safely stop daemon with error handling."""
        # Using direct logging instead of OperationTimer
        logger.info("safe_daemon_stop", "IntegrationService")
        try:
            result = self.cli_integration.handle_daemon_stop()

            logger.info("Daemon stop operation successful")

            return result

        except Exception as e:
            context = ErrorContext("daemon_stop", "IntegrationService")
            self.error_handler.handle_error(e, context, reraise=False)

            return {"status": "failed", "error": str(e)}

    @handle_errors("IntegrationService", "get_error_summary", reraise=False)
    def get_error_summary(self) -> dict[str, Any]:
        """Get error summary."""
        return self.error_reporter.get_error_summary()

    @handle_errors("IntegrationService", "log_custom_event", reraise=False)
    def log_custom_event(self, event_type: str, message: str, **kwargs):
        """Log custom event."""
        logger.info("INFO", message, event_type=event_type, **kwargs)

    @handle_errors("IntegrationService", "sync_models", reraise=False)
    def sync_models(self) -> dict[str, Any]:
        """Perform full model synchronization between JSON and database."""
        logger.info("sync_models", "IntegrationService")
        try:
            result = self.model_sync_service.full_sync()

            logger.info(
                f"Full model sync operation successful: {result['json_to_db']['added']} added, {result['db_to_json']['updated']} updated"
            )

            return result

        except Exception as e:
            context = ErrorContext("model_sync", "IntegrationService")
            self.error_handler.handle_error(e, context, reraise=False)

            return {"status": "failed", "error": str(e)}

    @handle_errors("IntegrationService", "sync_models_json_to_db", reraise=False)
    def sync_models_json_to_db(self) -> dict[str, Any]:
        """Sync models from JSON to database."""
        # Using direct logging instead of OperationTimer
        logger.info("sync_models_json_to_db", "IntegrationService")
        try:
            result = self.model_sync_service.sync_models_from_json_to_db()

            logger.info(
                f"Model sync from JSON to DB completed successfully: {result['added']} added, {result.get('updated', 0)} updated, {result['skipped']} skipped"
            )

            return result

        except Exception as e:
            context = ErrorContext("model_sync_json_to_db", "IntegrationService")
            self.error_handler.handle_error(e, context, reraise=False)

            return {"status": "failed", "error": str(e)}

    @handle_errors("IntegrationService", "sync_models_db_to_json", reraise=False)
    def sync_models_db_to_json(self) -> dict[str, Any]:
        """Sync models from database to JSON."""
        # Using direct logging instead of OperationTimer
        logger.info("sync_models_db_to_json", "IntegrationService")
        try:
            result = self.model_sync_service.sync_db_status_to_json()

            logger.info(
                f"Model sync from DB to JSON completed successfully: {result['updated']} updated, {result['unchanged']} unchanged"
            )

            return result

        except Exception as e:
            context = ErrorContext("model_sync_db_to_json", "IntegrationService")
            self.error_handler.handle_error(e, context, reraise=False)

            return {"status": "failed", "error": str(e)}

    @handle_errors("IntegrationService", "get_models_needing_sync", reraise=False)
    def get_models_needing_sync(self) -> list[dict[str, Any]]:
        """Get models that need synchronization."""
        # Using direct logging instead of OperationTimer
        logger.info("get_models_needing_sync", "IntegrationService")
        try:
            result = self.model_sync_service.get_models_needing_sync()

            logger.info(
                f"Get models needing sync operation successful: {len(result)} models need sync"
            )

            return result

        except Exception as e:
            context = ErrorContext("get_models_needing_sync", "IntegrationService")
            self.error_handler.handle_error(e, context, reraise=False)

            return []

    @handle_errors("IntegrationService", "update_model_status_in_json", reraise=False)
    def update_model_status_in_json(self, model_name: str, status: str) -> bool:
        """Update status of a specific model in JSON file."""
        # Using direct logging instead of OperationTimer
        logger.info("update_model_status_in_json", "IntegrationService")
        try:
            result = self.model_sync_service.update_model_status_in_json(
                model_name, status
            )

            logger.info(
                f"Update model status in JSON operation successful: {model_name} -> {status}, success={result}"
            )

            return result

        except Exception as e:
            context = ErrorContext(
                "update_model_status_in_json",
                "IntegrationService",
                model_name=model_name,
                status=status,
            )
            self.error_handler.handle_error(e, context, reraise=False)

            return False

    def register_error_callback(self, error_type: str, callback: Callable):
        """Register custom error callback."""
        self.error_handler.register_callback(error_type, callback)

    def get_service_health(self) -> dict[str, Any]:
        """Get service health status."""
        with self.stats_lock:
            health_stats = self.operation_stats.get("health_check", {})
            return health_stats.get("status", {})

    def get_operation_stats(self) -> dict[str, Any]:
        """Get operation statistics."""
        with self.stats_lock:
            return self.operation_stats.copy()
