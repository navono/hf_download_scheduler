"""
Main daemon entry point for HF Downloader.

This module provides the main daemon process that runs in the background
and handles scheduled downloads.
"""

import argparse
import os
import signal
import sys
from pathlib import Path

from ..core.config import ConfigManager
from ..models.database import DatabaseManager
from ..services.downloader import DownloaderService
from ..services.scheduler import SchedulerService
from ..utils import Config, CustomizeLogger

# Use the same logger instance as the main module
gen_config = Config().get_config()
logger = CustomizeLogger.make_logger(gen_config["log"])


class Daemon:
    """Main daemon class."""

    def __init__(
        self, config_path: str, db_path: str, pid_path: str, log_level: str = "INFO"
    ):
        """Initialize daemon."""
        self.config_manager = ConfigManager(config_path)
        self.config = self.config_manager.load_config()
        self.db_manager = DatabaseManager(db_path)
        self.downloader_service = DownloaderService(self.config, db_path)
        self.scheduler_service = SchedulerService(self.config, db_path)
        self.pid_path = Path(pid_path)
        self.running = False

        # Set up signal handlers
        self._setup_signal_handlers()

    def _setup_signal_handlers(self):
        """Set up signal handlers for graceful shutdown."""

        def signal_handler(signum, _frame):
            """Handle shutdown signals."""
            logger.info(f"Received signal {signum}, shutting down...")
            self.stop()

        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)

        if hasattr(signal, "SIGHUP"):
            signal.signal(signal.SIGHUP, signal_handler)

    def start(self):
        """Start the daemon."""
        try:
            logger.info("Starting HF Downloader daemon...")

            # Write PID file
            self.pid_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.pid_path, "w") as f:
                f.write(str(os.getpid()))

            # Inject downloader service into scheduler
            self.scheduler_service.downloader_service = self.downloader_service

            # Start scheduler
            result = self.scheduler_service.start()
            if result["status"] != "started":
                logger.error(f"Failed to start scheduler: {result}")
                return False

            self.running = True
            logger.info("Daemon started successfully")
            logger.info(f"Active schedule: {result['schedule']}")
            logger.info(f"Next run: {result.get('next_run', 'Not scheduled')}")

            # Display pending models that will be downloaded on next run
            self._display_pending_models()

            # Main daemon loop
            while self.running:
                try:
                    # Perform periodic health checks
                    self._health_check()

                    # Sleep for a while
                    import time

                    time.sleep(60)  # Check every minute

                except KeyboardInterrupt:
                    logger.info("Received keyboard interrupt")
                    break
                except Exception as e:
                    logger.error(f"Error in daemon loop: {e}")
                    import time

                    time.sleep(60)  # Wait before retrying

            return True

        except Exception as e:
            logger.error(f"Error starting daemon: {e}")
            return False

    def stop(self):
        """Stop the daemon."""
        try:
            logger.info("Stopping HF Downloader daemon...")

            self.running = False

            # Stop scheduler
            result = self.scheduler_service.stop()
            if result["status"] == "stopped":
                logger.info("Scheduler stopped successfully")

            # Clean up PID file
            if self.pid_path.exists():
                self.pid_path.unlink()

            logger.info("Daemon stopped successfully")

        except Exception as e:
            logger.error(f"Error stopping daemon: {e}")

    def _health_check(self):
        """Perform daemon health checks."""
        try:
            # Check database connection
            self.db_manager.get_system_config("health_check", "ok")

            # Check scheduler status
            status = self.scheduler_service.get_status()
            if status["state"] != "running":
                logger.warning("Scheduler is not running, attempting to restart...")
                self.scheduler_service.start()

            # Clean up old downloads
            self.downloader_service.cleanup_completed_downloads()

        except Exception as e:
            logger.error(f"Health check failed: {e}")

    def _display_pending_models(self):
        """Display the list of pending models that will be downloaded on next run."""
        try:
            # Get pending models from scheduler service
            pending_models = self.scheduler_service.get_pending_models()

            if not pending_models:
                logger.info("No pending models to download on next run")
                return

            # Log the number of pending models
            logger.info(
                f"Found {len(pending_models)} pending models for next scheduled download:"
            )

            # Log each model with its details
            for i, model in enumerate(pending_models, 1):
                model_name = model.get("name", "Unknown")
                model_priority = model.get("priority", "medium")
                model_size = model.get("size_estimate", "Unknown size")

                # Format the log message
                if model_size and model_size != "":
                    logger.info(
                        f"  {i}. {model_name} (Priority: {model_priority}, Size: {model_size})"
                    )
                else:
                    logger.info(f"  {i}. {model_name} (Priority: {model_priority})")

        except Exception as e:
            logger.error(f"Error displaying pending models: {e}")


def main():
    """Main daemon entry point."""
    parser = argparse.ArgumentParser(description="HF Downloader Daemon")
    parser.add_argument(
        "--config",
        type=str,
        default="./config/default.yaml",
        help="Configuration file path",
    )
    parser.add_argument(
        "--database", type=str, default="./hf_downloader.db", help="Database file path"
    )
    parser.add_argument(
        "--pid", type=str, default="./hf_downloader.pid", help="PID file path"
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Log level",
    )

    args = parser.parse_args()

    # Initialize daemon
    daemon = Daemon(
        config_path=args.config,
        db_path=args.database,
        pid_path=args.pid,
        log_level=args.log_level,
    )

    # Start daemon
    success = daemon.start()
    if not success:
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()
