"""
Scheduler service for HF Downloader.

This module handles scheduled downloading of Hugging Face models with
support for daily, weekly, and custom schedules.
"""

import threading
import time
from datetime import datetime
from enum import Enum
from typing import Any

import schedule
from loguru import logger

from ..core.config import Config
from ..models.database import DatabaseManager, ScheduleConfiguration
from .time_window import TimeWindow


class SchedulerState(Enum):
    """Scheduler state enumeration."""

    STOPPED = "stopped"
    RUNNING = "running"
    PAUSED = "paused"


class SchedulerService:
    """Service for scheduling model downloads."""

    def __init__(self, config: Config, db_path: str):
        """Initialize scheduler service."""
        logger.info("Initializing SchedulerService")
        self.config = config
        self.db_manager = DatabaseManager(db_path)
        self._state = SchedulerState.STOPPED
        self._scheduler_thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._jobs: dict[str, schedule.Job] = {}
        self.downloader_service = None  # Will be set by dependency injection
        self.integration_service = None  # Optional integration service for enhanced functionality

        # Initialize default schedule if none exists
        self._initialize_default_schedule()
        logger.info("SchedulerService initialized successfully")

    def _initialize_default_schedule(self):
        """Initialize default schedule from config.yaml and update database."""
        try:
            # 获取配置文件中的默认调度设置
            default_schedule = getattr(self.config, "default_schedule", None)
            if default_schedule and isinstance(default_schedule, dict):
                schedule_type = default_schedule.get("type", "daily")
                schedule_time = default_schedule.get("time", "22:00")
                # Note: enabled status is handled by database default value
                max_concurrent = default_schedule.get(
                    "max_concurrent_downloads", self.config.concurrent_downloads
                )

                # Extract time window configuration from nested structure
                time_window_config = default_schedule.get("time_window", {})
                time_window_enabled = time_window_config.get("enabled", False)
                time_window_start = (
                    time_window_config.get("start_time", "22:00")
                    if time_window_enabled
                    else None
                )
                time_window_end = (
                    time_window_config.get("end_time", "07:00")
                    if time_window_enabled
                    else None
                )

                logger.info(
                    f"Using default schedule from config: {schedule_type} at {schedule_time}"
                )

                # 检查是否有现有的调度
                active_schedule = self.db_manager.get_active_schedule()

                if active_schedule:
                    # 更新现有的调度
                    logger.info(
                        f"Updating existing schedule (ID: {active_schedule.id}) with config settings"
                    )
                    self.db_manager.update_schedule(
                        active_schedule.id,
                        type=schedule_type,
                        time=schedule_time,
                        max_concurrent_downloads=max_concurrent,
                        time_window_enabled=time_window_enabled,
                        time_window_start=time_window_start,
                        time_window_end=time_window_end,
                    )
                else:
                    # 创建新的调度
                    logger.info(
                        f"Creating new schedule from config: {schedule_type} at {schedule_time}"
                    )
                    self.db_manager.create_schedule(
                        name="default_daily",
                        type=schedule_type,
                        time=schedule_time,
                        max_concurrent_downloads=max_concurrent,
                        time_window_enabled=time_window_enabled,
                        time_window_start=time_window_start,
                        time_window_end=time_window_end,
                    )
            else:
                # 如果配置文件中没有默认调度设置，则创建一个默认的
                active_schedule = self.db_manager.get_active_schedule()
                if not active_schedule:
                    logger.info(
                        "No default schedule in config, creating default daily schedule at 23:00"
                    )
                    self.db_manager.create_schedule(
                        name="default_daily",
                        type="daily",
                        time="23:00",
                        max_concurrent_downloads=self.config.concurrent_downloads,
                    )
        except Exception as e:
            logger.error(f"Error initializing default schedule: {e}")

    def start(self) -> dict[str, Any]:
        """Start the scheduler."""
        logger.info("Starting scheduler")
        try:
            if self._state == SchedulerState.RUNNING:
                logger.info("Scheduler is already running")
                return {
                    "status": "already_running",
                    "message": "Scheduler is already running",
                }

            # Load active schedule
            logger.info("Loading active schedule")
            active_schedule = self.db_manager.get_active_schedule()
            if not active_schedule:
                logger.warning("No active schedule found")
                return {"status": "no_schedule", "message": "No active schedule found"}

            # Debug: Log active schedule details
            logger.debug(f"Active schedule: {active_schedule.to_dict()}")
            logger.info(
                f"Schedule type: {active_schedule.type}, time: {active_schedule.time}"
            )
            if active_schedule.day_of_week is not None:
                logger.info(f"Day of week: {active_schedule.day_of_week}")

            # Clear existing jobs
            logger.debug("Clearing existing jobs")
            schedule.clear()
            self._jobs.clear()

            # Schedule jobs based on active schedule
            logger.info("Scheduling jobs based on active schedule")
            self._schedule_jobs(active_schedule)

            # Debug: Log scheduled jobs
            logger.debug(f"Scheduled jobs count: {len(self._jobs)}")
            for job_name, job in self._jobs.items():
                logger.debug(f"Job: {job_name}, next_run: {job.next_run}")

            # Start scheduler thread
            logger.info("Starting scheduler thread")
            self._stop_event.clear()
            self._scheduler_thread = threading.Thread(target=self._scheduler_loop)
            self._scheduler_thread.daemon = True
            self._scheduler_thread.start()
            logger.debug(f"Scheduler thread started: {self._scheduler_thread.ident}")

            self._state = SchedulerState.RUNNING
            logger.info("Scheduler started successfully")

            next_run = self.get_next_run_time()
            logger.info(f"Next run time: {next_run}")

            return {
                "status": "started",
                "schedule": active_schedule.to_dict(),
                "next_run": next_run,
            }

        except Exception as e:
            logger.error(f"Error starting scheduler: {e}")
            return {"status": "error", "error": str(e)}

    def stop(self) -> dict[str, Any]:
        """Stop the scheduler."""
        try:
            if self._state == SchedulerState.STOPPED:
                return {
                    "status": "already_stopped",
                    "message": "Scheduler is already stopped",
                }

            # Signal stop to scheduler thread
            self._stop_event.set()

            # Wait for scheduler thread to finish
            if self._scheduler_thread:
                self._scheduler_thread.join(timeout=5)

            # Clear scheduled jobs
            schedule.clear()
            self._jobs.clear()

            self._state = SchedulerState.STOPPED

            return {"status": "stopped", "message": "Scheduler stopped successfully"}

        except Exception as e:
            logger.error(f"Error stopping scheduler: {e}")
            return {"status": "error", "error": str(e)}

    def _scheduler_loop(self):
        """Main scheduler loop."""
        logger.info("Scheduler loop started")
        loop_count = 0
        while not self._stop_event.is_set():
            try:
                loop_count += 1
                if loop_count % 60 == 0:  # Log every minute
                    logger.debug(f"Scheduler loop running (iteration {loop_count})")
                    current_time = datetime.now()
                    logger.debug(f"Current time: {current_time}")
                    for job_name, job in self._jobs.items():
                        logger.debug(f"Job {job_name} next run: {job.next_run}")

                schedule.run_pending()
                time.sleep(1)  # Check every second
            except Exception as e:
                logger.error(f"Error in scheduler loop: {e}")
                time.sleep(5)  # Wait before retrying
        logger.info("Scheduler loop stopped")

    def _schedule_jobs(self, schedule_config: ScheduleConfiguration):
        """Schedule jobs based on configuration."""
        try:
            logger.debug(f"Scheduling jobs for config: {schedule_config.to_dict()}")

            time_parts = schedule_config.time.split(":")
            hour = int(time_parts[0])
            minute = int(time_parts[1])

            logger.debug(f"Parsed time: hour={hour}, minute={minute}")
            current_time = datetime.now()
            logger.debug(f"Current system time: {current_time}")

            if schedule_config.type == "daily":
                logger.debug(f"Creating daily schedule at {hour:02d}:{minute:02d}")
                job = (
                    schedule.every()
                    .day.at(f"{hour:02d}:{minute:02d}")
                    .do(self._execute_scheduled_download, schedule_config.id)
                )
                self._jobs[f"daily_{hour}_{minute}"] = job
                logger.debug(f"Daily job created: {job.next_run}")

            elif schedule_config.type == "weekly":
                if schedule_config.day_of_week is not None:
                    day_names = [
                        "monday",
                        "tuesday",
                        "wednesday",
                        "thursday",
                        "friday",
                        "saturday",
                        "sunday",
                    ]
                    day_name = day_names[schedule_config.day_of_week]
                    logger.debug(
                        f"Creating weekly schedule on {day_name} at {hour:02d}:{minute:02d}"
                    )

                    job = (
                        getattr(schedule.every(), day_name)
                        .at(f"{hour:02d}:{minute:02d}")
                        .do(self._execute_scheduled_download, schedule_config.id)
                    )
                    self._jobs[
                        f"weekly_{schedule_config.day_of_week}_{hour}_{minute}"
                    ] = job
                    logger.debug(f"Weekly job created: {job.next_run}")
                else:
                    logger.warning("Weekly schedule but no day_of_week specified")

            logger.info(
                f"Scheduled job for {schedule_config.type} at {schedule_config.time}"
            )

            # Log all scheduled jobs
            for job_name, job in self._jobs.items():
                logger.info(f"Scheduled job '{job_name}' next run: {job.next_run}")

        except Exception as e:
            logger.error(f"Error scheduling jobs: {e}")

    def _execute_scheduled_download(self, schedule_id: int):
        """Execute scheduled download."""
        try:
            start_time = datetime.now()
            logger.info(
                f"Executing scheduled download for schedule {schedule_id} at {start_time}"
            )

            if not self.downloader_service:
                logger.error("Downloader service not available")
                return

            # Get schedule configuration
            schedule_config = self.db_manager.get_active_schedule()
            if not schedule_config:
                logger.error("No active schedule configuration found")
                return

            # Check if schedule is enabled
            if not schedule_config.enabled:
                logger.info(f"Schedule {schedule_id} is disabled, skipping download")
                return

            # Check time window restrictions
            if schedule_config.time_window_enabled:
                time_window = TimeWindow(
                    schedule_config.time_window_start or "22:00",
                    schedule_config.time_window_end or "07:00",
                    enabled=True,
                )

                if not time_window.is_current_time_in_window():
                    logger.info(
                        f"Current time {start_time.strftime('%H:%M')} is outside time window "
                        f"({schedule_config.time_window_start}-{schedule_config.time_window_end}), "
                        "skipping download"
                    )
                    return

                logger.info(
                    f"Time window check passed: current time {start_time.strftime('%H:%M')} "
                    f"is within window ({schedule_config.time_window_start}-{schedule_config.time_window_end})"
                )
            else:
                logger.info("No time window restriction, proceeding with download")

            # Get enabled models with pending status
            pending_models = self.get_pending_models()
            logger.debug(f"Found {len(pending_models)} enabled pending models")

            if not pending_models:
                logger.info("No pending models to download")
                return

            # Log the list of models that will be downloaded
            logger.info(
                f"Scheduled download will process the following {len(pending_models)} models:"
            )
            for i, model in enumerate(pending_models, 1):
                logger.info(f"  {i}. {model.name}")

            # Limit concurrent downloads
            max_downloads = min(
                schedule_config.max_concurrent_downloads, len(pending_models)
            )
            logger.info(f"Starting up to {max_downloads} downloads")

            # Start downloads
            for i, model in enumerate(pending_models[:max_downloads]):
                try:
                    logger.info(
                        f"Starting download {i + 1}/{max_downloads}: {model.name}"
                    )
                    result = self.downloader_service.download_model(
                        model.name, schedule_id=schedule_id
                    )
                    logger.info(f"Started download for {model.name}: {result}")
                except Exception as e:
                    logger.error(f"Error starting download for {model.name}: {e}")

            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            logger.info(
                f"Scheduled download execution completed in {duration:.2f} seconds"
            )

        except Exception as e:
            logger.error(f"Error executing scheduled download: {e}")

    def get_next_run_time(self) -> str | None:
        """Get next scheduled run time."""
        try:
            if not self._jobs:
                logger.debug("No scheduled jobs found")
                return None

            next_run = None
            for job_name, job in self._jobs.items():
                job_run = job.next_run
                logger.debug(f"Job '{job_name}' next run: {job_run}")
                if job_run and (not next_run or job_run < next_run):
                    next_run = job_run
                    logger.debug(f"Updated next_run to: {next_run}")

            result = next_run.isoformat() if next_run else None
            logger.debug(f"Final next run time: {result}")
            return result
        except Exception as e:
            logger.error(f"Error getting next run time: {e}")
            return None

    def create_schedule(
        self,
        name: str,
        schedule_type: str,
        time_str: str,
        day_of_week: int | None = None,
        max_concurrent_downloads: int = 1,
    ) -> dict[str, Any]:
        """Create a new schedule."""
        try:
            # Validate time format
            self._validate_time_format(time_str)

            # Validate schedule type
            if schedule_type not in ["daily", "weekly"]:
                raise ValueError(f"Invalid schedule type: {schedule_type}")

            # Validate day of week for weekly schedules
            if schedule_type == "weekly" and day_of_week is None:
                raise ValueError("day_of_week is required for weekly schedules")

            if schedule_type == "weekly" and not (0 <= day_of_week <= 6):
                raise ValueError("day_of_week must be between 0 and 6")

            # Create schedule
            schedule_config = self.db_manager.create_schedule(
                name=name,
                type=schedule_type,
                time=time_str,
                day_of_week=day_of_week,
                max_concurrent_downloads=max_concurrent_downloads,
            )

            return {"status": "created", "schedule": schedule_config.to_dict()}

        except Exception as e:
            logger.error(f"Error creating schedule: {e}")
            return {"status": "error", "error": str(e)}

    def _validate_time_format(self, time_str: str):
        """Validate time format (HH:MM)."""
        try:
            time_parts = time_str.split(":")
            if len(time_parts) != 2:
                raise ValueError("Time must be in HH:MM format")

            hour = int(time_parts[0])
            minute = int(time_parts[1])

            if not (0 <= hour <= 23):
                raise ValueError("Hour must be between 0 and 23")
            if not (0 <= minute <= 59):
                raise ValueError("Minute must be between 0 and 59")

        except ValueError as e:
            raise ValueError(f"Invalid time format '{time_str}': {e}")

    def get_scheduled_jobs(self) -> list[dict[str, Any]]:
        """Get all scheduled jobs."""
        try:
            jobs = []
            for job_name, job in self._jobs.items():
                jobs.append(
                    {
                        "name": job_name,
                        "next_run": job.next_run.isoformat() if job.next_run else None,
                        "unit": job.unit,
                        "at_time": job.at_time,
                    }
                )
            return jobs
        except Exception as e:
            logger.error(f"Error getting scheduled jobs: {e}")
            return []

    def get_status(self) -> dict[str, Any]:
        """Get scheduler status information."""
        try:
            next_run = self.get_next_run_time()
            active_schedule = self.db_manager.get_active_schedule()

            return {
                "state": self._state.value,
                "next_run": next_run,
                "active_schedule": active_schedule.to_dict()
                if active_schedule
                else None,
                "jobs": self.get_scheduled_jobs(),
            }
        except Exception as e:
            logger.error(f"Error getting scheduler status: {e}")
            return {"state": "error", "error": str(e)}

    def get_pending_models(self) -> list[dict[str, Any]]:
        """Get list of pending models that will be downloaded on next run."""
        try:
            # Use integration service if available (it checks enabled field)
            if self.integration_service:
                logger.debug("Using integration service to get enabled pending models")
                return self.integration_service.get_enabled_pending_models()

            # Fallback to old method (doesn't check enabled field)
            logger.debug("Integration service not available, using fallback method")
            pending_models = self.db_manager.get_models_by_status("pending")
            logger.debug(f"Found {len(pending_models)} pending models")

            # Convert to list of dictionaries for easier handling
            result = []
            for model in pending_models:
                model_dict = {
                    "id": model.id,
                    "name": model.name,
                    "status": model.status,
                }

                # Add metadata if available
                metadata = model.get_metadata()
                if metadata:
                    model_dict["priority"] = metadata.get("priority", "medium")

                result.append(model_dict)

            return result
        except Exception as e:
            logger.error(f"Error getting pending models: {e}")
            return []

    def get_all_schedules(self) -> dict[str, Any]:
        """Get all schedule configurations."""
        try:
            schedules = self.db_manager.get_all_schedules()
            return {
                "status": "success",
                "schedules": schedules,
                "count": len(schedules),
            }
        except Exception as e:
            logger.error(f"Error getting all schedules: {e}")
            return {"status": "error", "error": str(e)}
