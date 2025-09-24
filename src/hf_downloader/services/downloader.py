"""
Downloader service for HF Downloader.

This module handles downloading Hugging Face models with progress tracking,
retry mechanisms, and error handling.
"""

import os
import signal
import sys
import threading
import time
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

from huggingface_hub import HfApi, hf_hub_download
from huggingface_hub.utils import HFValidationError, RepositoryNotFoundError
from loguru import logger

from ..core.config import Config
from ..models.database import DatabaseManager
from ..services.model_sync import ModelSyncService


class DownloadError(Exception):
    """Custom exception for download errors."""

    pass


class DownloaderService:
    """Service for downloading Hugging Face models."""

    def __init__(self, config: Config, db_path: str, models_file_path: str = None):
        """Initialize downloader service."""
        logger.info("Initializing DownloaderService")
        self.config = config
        self.db_manager = DatabaseManager(db_path)

        # Initialize ModelSyncService if models_file_path is provided
        self.model_sync_service = None
        if models_file_path:
            self.model_sync_service = ModelSyncService(
                self.db_manager, models_file_path
            )

        self._active_downloads: dict[str, threading.Thread] = {}
        self._progress_callbacks: dict[str, Callable] = {}
        self._cancel_flags: dict[str, bool] = {}
        self._shutdown_event = threading.Event()
        self._original_sigint = None

        # 外部服务引用
        self.integration_service = None

        # Set up signal handler for graceful shutdown
        self._setup_signal_handler()

    def set_integration_service(self, integration_service):
        """设置集成服务引用，用于状态同步。"""
        self.integration_service = integration_service

    def _sync_model_status_immediate(self, model_name: str, status: str):
        """立即同步模型状态到JSON文件。"""
        try:
            if self.integration_service:
                self.integration_service.sync_db_status_to_json_immediate(model_name)
            elif self.model_sync_service:
                self.model_sync_service.update_model_status_in_json(model_name, status)
        except Exception as e:
            logger.error(f"Error syncing model status for {model_name}: {e}")

        # Create download directory if it doesn't exist
        if self.config.download_directory:
            Path(self.config.download_directory).mkdir(parents=True, exist_ok=True)
            logger.info(
                f"DownloaderService initialized with download directory: {self.config.download_directory}"
            )
        else:
            logger.warning(
                f"No download directory specified, using default HF_HOME: {os.environ.get('HF_HOME')}"
            )

    def _setup_signal_handler(self):
        """Set up signal handler for graceful shutdown."""

        def signal_handler(_signum, _frame):
            logger.info("Received shutdown signal, cancelling all downloads...")
            self.cancel_all_downloads()
            if self._original_sigint:
                # Restore original handler and re-raise
                signal.signal(signal.SIGINT, self._original_sigint)
                sys.exit(1)
            else:
                sys.exit(0)

        self._original_sigint = signal.getsignal(signal.SIGINT)
        signal.signal(signal.SIGINT, signal_handler)

        # 注册清理函数，确保进程退出时清理状态
        import atexit
        atexit.register(self._cleanup_on_exit)

    def _cleanup_on_exit(self):
        """进程退出时清理僵尸下载状态。"""
        try:
            logger.info("Cleaning up download states on exit...")

            # 清理活跃的下载线程
            for model_name, thread in list(self._active_downloads.items()):
                if thread and thread.is_alive():
                    logger.warning(f"Force stopping download thread for {model_name}")
                    self._cancel_flags[model_name] = True
                    thread.join(timeout=2)

                # 将模型状态重置为pending
                try:
                    model = self.db_manager.get_model_by_name(model_name)
                    if model and model.status == "downloading":
                        logger.info(f"Resetting {model_name} status to pending on exit")
                        self.db_manager.update_model_status(model.id, "pending")
                        self._sync_model_status_immediate(model_name, "pending")
                except Exception as e:
                    logger.error(f"Error resetting model status for {model_name}: {e}")

            # 清理下载会话
            try:
                active_sessions = self.db_manager.get_active_download_sessions()
                for session in active_sessions:
                    logger.info(f"Cleaning up active session {session.id}")
                    self.db_manager.update_download_session(
                        session.id, "failed", "Process exited unexpectedly"
                    )
            except Exception as e:
                logger.error(f"Error cleaning up download sessions: {e}")

            logger.info("Exit cleanup completed")

        except Exception as e:
            logger.error(f"Error during exit cleanup: {e}")

    def download_model(
        self,
        model_name: str,
        progress_callback: Callable[[dict[str, Any]], None] | None = None,
        schedule_id: int | None = None,
    ) -> dict[str, Any]:
        """Download a Hugging Face model."""
        logger.info(f"Starting download for model: {model_name}")
        try:
            # Check if model is already being downloaded
            if model_name in self._active_downloads:
                logger.info(f"Model {model_name} is already being downloaded")
                return {
                    "status": "downloading",
                    "model": model_name,
                    "message": "Download already in progress",
                }

            # Get or create model record
            model = self.db_manager.get_model_by_name(model_name)
            if not model:
                logger.info(f"Creating new model record for: {model_name}")
                model = self.db_manager.create_model(
                    name=model_name, metadata={"source": "huggingface"}
                )
            elif model.status == "completed":
                logger.info(f"Model {model_name} already completed")
                return {
                    "status": "completed",
                    "model": model_name,
                    "path": model.download_path,
                    "message": "Model already downloaded",
                }

            # Update model status to downloading
            logger.info(f"Updating model {model_name} status to downloading")
            self.db_manager.update_model_status(model.id, "downloading")

            # 立即同步状态到JSON
            self._sync_model_status_immediate(model_name, "downloading")

            # Create download session
            session = self.db_manager.create_download_session(model.id, schedule_id)

            # Store callback and cancel flag
            self._progress_callbacks[model_name] = progress_callback
            self._cancel_flags[model_name] = False

            # Start download in separate thread
            logger.info(f"Starting download thread for model: {model_name}")
            download_thread = threading.Thread(
                target=self._download_model_thread,
                args=(model_name, model.id, session.id, progress_callback),
            )
            self._active_downloads[model_name] = download_thread
            download_thread.start()

            return {
                "status": "started",
                "model": model_name,
                "session_id": session.id,
                "message": "Download started",
            }

        except Exception as e:
            logger.error(f"Error starting download for {model_name}: {e}")
            return {"status": "failed", "model": model_name, "error": str(e)}

    def _download_model_thread(
        self,
        model_name: str,
        model_id: int,
        session_id: int,
        progress_callback: Callable | None,
    ):
        """Download model in separate thread."""
        try:
            # Check if shutdown was requested before starting
            if self._shutdown_event.is_set() or self._cancel_flags.get(
                model_name, False
            ):
                raise DownloadError(
                    f"Download cancelled for {model_name} - shutdown requested"
                )

            # Get model info
            hf_api = HfApi(token=self.config.hf_token)
            _ = hf_api.model_info(model_name)  # Verify model exists

            # Calculate total size
            total_size = self._calculate_model_size(model_name)

            # Update session with total size
            self.db_manager.update_download_session(
                session_id, "in_progress", total_bytes=total_size
            )

            # Download model files
            downloaded_path = self._download_model_files(
                model_name, model_id, session_id
            )

            # Update model and session status
            self.db_manager.update_model_status(model_id, "completed", downloaded_path)
            self.db_manager.update_download_session(session_id, "completed")

            # 立即同步状态到JSON
            self._sync_model_status_immediate(model_name, "completed")

            if progress_callback:
                progress_callback(
                    {
                        "model": model_name,
                        "status": "completed",
                        "progress": 100,
                        "downloaded_bytes": total_size,
                        "total_bytes": total_size,
                        "path": downloaded_path,
                    }
                )

            logger.info(f"Successfully downloaded {model_name}")

        except DownloadError as e:
            logger.warning(f"Download cancelled for {model_name}: {e}")
            # Update model and session status to cancelled/failed
            try:
                self.db_manager.update_model_status(model_id, "failed")
                self.db_manager.update_download_session(
                    session_id, "cancelled", error_message=str(e)
                )

                # 立即同步状态到JSON
                self._sync_model_status_immediate(model_name, "failed")
            except Exception as db_error:
                logger.error(f"Error updating database after cancellation: {db_error}")

            if progress_callback:
                progress_callback(
                    {"model": model_name, "status": "cancelled", "error": str(e)}
                )

        except Exception as e:
            logger.error(f"Error downloading {model_name}: {e}")

            # Update model and session status
            try:
                self.db_manager.update_model_status(model_id, "failed")
                self.db_manager.update_download_session(
                    session_id, "failed", error_message=str(e)
                )

                # 立即同步状态到JSON
                self._sync_model_status_immediate(model_name, "failed")
            except Exception as db_error:
                logger.error(f"Error updating database after failure: {db_error}")

            if progress_callback:
                progress_callback(
                    {"model": model_name, "status": "failed", "error": str(e)}
                )

        finally:
            # Clean up
            self._active_downloads.pop(model_name, None)
            self._progress_callbacks.pop(model_name, None)
            self._cancel_flags.pop(model_name, None)

    def _download_model_files(
        self, model_name: str, model_id: int, session_id: int
    ) -> str:
        """Download model files with progress tracking."""
        downloaded_path = None
        bytes_downloaded = 0

        for attempt in range(self.config.max_retries + 1):
            # Check for cancellation at the start of each attempt
            if self._shutdown_event.is_set() or self._cancel_flags.get(
                model_name, False
            ):
                raise DownloadError(f"Download cancelled for {model_name}")

            try:
                # Get model files
                hf_api = HfApi(token=self.config.hf_token)
                files = hf_api.list_repo_files(model_name)

                # Create model directory
                model_dir = None
                if self.config.download_directory:
                    model_dir = Path(
                        self.config.download_directory
                    ) / model_name.replace("/", "_")
                    model_dir.mkdir(parents=True, exist_ok=True)

                # Download each file
                for _i, file_path in enumerate(files):
                    # Check for cancellation before each file
                    if self._shutdown_event.is_set() or self._cancel_flags.get(
                        model_name, False
                    ):
                        raise DownloadError(f"Download cancelled for {model_name}")

                    try:
                        if model_dir is None:
                            file_download_path = hf_hub_download(
                                repo_id=model_name,
                                filename=file_path,
                                local_dir_use_symlinks=False,
                                token=self.config.hf_token,
                            )
                        else:
                            file_download_path = hf_hub_download(
                                repo_id=model_name,
                                filename=file_path,
                                local_dir=model_dir,
                                local_dir_use_symlinks=False,
                                token=self.config.hf_token,
                            )

                        # Update progress
                        if file_download_path and os.path.exists(file_download_path):
                            bytes_downloaded += os.path.getsize(file_download_path)
                            self.db_manager.update_download_session(
                                session_id,
                                "in_progress",
                                bytes_downloaded=bytes_downloaded,
                            )

                            # Notify callback
                            if self._progress_callbacks.get(model_name):
                                total_size = self._calculate_model_size(model_name)
                                progress = (
                                    (bytes_downloaded / total_size) * 100
                                    if total_size > 0
                                    else 0
                                )
                                self._progress_callbacks[model_name](
                                    {
                                        "model": model_name,
                                        "status": "in_progress",
                                        "progress": progress,
                                        "downloaded_bytes": bytes_downloaded,
                                        "total_bytes": total_size,
                                        "file": file_path,
                                    }
                                )

                    except Exception as file_error:
                        logger.warning(
                            f"Error downloading file {file_path}: {file_error}"
                        )
                        # Check if we should cancel due to shutdown
                        if self._shutdown_event.is_set() or self._cancel_flags.get(
                            model_name, False
                        ):
                            raise DownloadError(
                                f"Download cancelled for {model_name} during file download"
                            )
                        raise  # Re-raise to trigger retry

                downloaded_path = str(model_dir)
                break

            except DownloadError:
                # Re-raise download cancellation errors immediately
                raise

            except Exception as e:
                if attempt == self.config.max_retries:
                    raise DownloadError(
                        f"Failed to download {model_name} after {self.config.max_retries + 1} attempts: {e}"
                    )

                logger.warning(
                    f"Download attempt {attempt + 1} failed for {model_name}: {e}"
                )

                # Wait with interruption check
                for _wait_i in range(2**attempt):
                    if self._shutdown_event.is_set() or self._cancel_flags.get(
                        model_name, False
                    ):
                        raise DownloadError(
                            f"Download cancelled for {model_name} during retry wait"
                        )
                    time.sleep(1)

        return downloaded_path

    def _calculate_model_size(self, model_name: str) -> int:
        """Calculate total size of model files."""
        try:
            hf_api = HfApi(token=self.config.hf_token)
            files = hf_api.list_repo_files(model_name)

            total_size = 0
            for file_path in files:
                file_info = hf_api.model_info(model_name, files_metadata=True)
                # Try to get file size from siblings
                for sibling in getattr(file_info, "siblings", []):
                    if hasattr(sibling, "rfilename") and sibling.rfilename == file_path:
                        if hasattr(sibling, "size"):
                            total_size += sibling.size
                        break

            return (
                total_size if total_size > 0 else 1024 * 1024 * 100
            )  # Default to 100MB

        except Exception as e:
            logger.warning(f"Could not calculate size for {model_name}: {e}")
            return 1024 * 1024 * 100  # Default to 100MB

    def get_download_status(self, model_name: str) -> dict[str, Any]:
        """Get download status for a model."""
        try:
            model = self.db_manager.get_model_by_name(model_name)
            if not model:
                return {
                    "status": "not_found",
                    "model": model_name,
                    "message": "Model not found in database",
                }

            # Check if currently downloading
            if model_name in self._active_downloads:
                return {
                    "status": "downloading",
                    "model": model_name,
                    "message": "Download in progress",
                }

            # Get latest download session
            sessions = self.db_manager.get_download_history(model.id, 1)
            if sessions:
                latest_session = sessions[0]
                return {
                    "status": model.status,
                    "model": model_name,
                    "path": model.download_path,
                    "last_session": latest_session.to_dict(),
                    "message": f"Model status: {model.status}",
                }

            return {
                "status": model.status,
                "model": model_name,
                "message": f"Model status: {model.status}",
            }

        except Exception as e:
            logger.error(f"Error getting download status for {model_name}: {e}")
            return {"status": "error", "model": model_name, "error": str(e)}

    def cancel_download(self, model_name: str) -> dict[str, Any]:
        """Cancel an ongoing download."""
        try:
            if model_name not in self._active_downloads:
                return {
                    "status": "not_downloading",
                    "model": model_name,
                    "message": "No active download found",
                }

            # Set cancel flag
            self._cancel_flags[model_name] = True

            # Get model and update status
            model = self.db_manager.get_model_by_name(model_name)
            if model:
                self.db_manager.update_model_status(model.id, "paused")

                # 同步更新 models.json 文件
                if self.model_sync_service:
                    try:
                        # 更新 models.json 中的模型状态
                        self.model_sync_service.update_model_status_in_json(
                            model_name, "paused"
                        )
                        logger.info(
                            f"Updated model status in JSON for {model_name}: paused"
                        )
                    except Exception as json_error:
                        logger.error(
                            f"Error updating models.json for {model_name}: {json_error}"
                        )

            return {
                "status": "cancelled",
                "model": model_name,
                "message": "Download cancellation requested",
            }

        except Exception as e:
            logger.error(f"Error cancelling download for {model_name}: {e}")
            return {"status": "error", "model": model_name, "error": str(e)}

    def cancel_all_downloads(self):
        """Cancel all active downloads."""
        logger.info(f"Cancelling {len(self._active_downloads)} active downloads...")

        # Set cancel flag for all downloads
        for model_name in self._active_downloads:
            self._cancel_flags[model_name] = True
            logger.info(f"Cancelling download for {model_name}")

            # Update model status
            try:
                model = self.db_manager.get_model_by_name(model_name)
                if model:
                    self.db_manager.update_model_status(model.id, "paused")
            except Exception as e:
                logger.error(f"Error updating model status for {model_name}: {e}")

        # Set shutdown event
        self._shutdown_event.set()

        # Wait for all downloads to finish (with timeout)
        for model_name, thread in list(self._active_downloads.items()):
            if thread.is_alive():
                thread.join(timeout=5.0)  # Wait up to 5 seconds per thread
                if thread.is_alive():
                    logger.warning(
                        f"Thread for {model_name} did not terminate gracefully"
                    )

        logger.info("All downloads cancelled")

    def wait_for_completion(self, timeout: float | None = None) -> bool:
        """Wait for all downloads to complete."""
        start_time = time.time()

        while self._active_downloads:
            if timeout and (time.time() - start_time) > timeout:
                logger.warning("Timeout waiting for downloads to complete")
                return False

            # Check if shutdown was requested
            if self._shutdown_event.is_set():
                logger.info("Shutdown requested, stopping wait")
                return False

            time.sleep(0.1)

        return True

    def __del__(self):
        """Clean up when service is destroyed."""
        try:
            self.cancel_all_downloads()
            # Restore original signal handler
            if self._original_sigint:
                signal.signal(signal.SIGINT, self._original_sigint)
        except Exception:
            pass  # Ignore errors during cleanup

    def get_active_downloads(self) -> dict[str, dict[str, Any]]:
        """Get all active downloads."""
        active_downloads = {}
        for model_name in self._active_downloads:
            status = self.get_download_status(model_name)
            active_downloads[model_name] = status
        return active_downloads

    def cleanup_completed_downloads(self):
        """Clean up completed download records."""
        try:
            # Clean up old download sessions (keep last 10 per model)
            models = self.db_manager.get_models_by_status("completed")
            for model in models:
                sessions = self.db_manager.get_download_history(model.id, 20)
                if len(sessions) > 10:
                    # Keep only the last 10 sessions
                    for _session in sessions[10:]:
                        # Note: This would require a delete method in DatabaseManager
                        pass

        except Exception as e:
            logger.error(f"Error cleaning up downloads: {e}")

    def validate_model_access(self, model_name: str) -> dict[str, Any]:
        """Validate if model can be accessed with current credentials."""
        try:
            hf_api = HfApi(token=self.config.hf_token)
            model_info = hf_api.model_info(model_name)

            return {
                "status": "accessible",
                "model": model_name,
                "model_info": {
                    "id": model_info.id,
                    "private": getattr(model_info, "private", False),
                    "downloads": getattr(model_info, "downloads", 0),
                    "likes": getattr(model_info, "likes", 0),
                },
            }

        except RepositoryNotFoundError:
            return {
                "status": "not_found",
                "model": model_name,
                "error": "Model not found on Hugging Face",
            }
        except HFValidationError as e:
            return {
                "status": "access_denied",
                "model": model_name,
                "error": f"Access denied: {str(e)}",
            }
        except Exception as e:
            return {"status": "error", "model": model_name, "error": str(e)}

    def get_session_details(self, session_id: int) -> dict[str, Any]:
        """Get detailed information about a download session."""
        try:
            session = self.db_manager.get_download_session(session_id)
            if not session:
                return {
                    "status": "not_found",
                    "session_id": session_id,
                    "message": "Session not found",
                }

            # Get model information
            model = self.db_manager.get_model(session.model_id)
            if not model:
                return {
                    "status": "error",
                    "session_id": session_id,
                    "message": "Associated model not found",
                }

            # Calculate progress percentage
            progress = 0
            if session.total_bytes and session.total_bytes > 0:
                progress = (session.bytes_downloaded / session.total_bytes) * 100

            # Calculate duration if completed
            duration_seconds = None
            if session.completed_at and session.started_at:
                duration_seconds = (
                    session.completed_at - session.started_at
                ).total_seconds()

            # Calculate download speed if available
            speed_bps = 0
            if (
                session.bytes_downloaded > 0
                and duration_seconds
                and duration_seconds > 0
            ):
                speed_bps = session.bytes_downloaded / duration_seconds

            return {
                "status": "success",
                "session": session.to_dict(),
                "model": model.to_dict(),
                "progress_percentage": round(progress, 2),
                "duration_seconds": duration_seconds,
                "download_speed_bps": round(speed_bps, 2),
                "download_speed_mbps": round(speed_bps / (1024 * 1024), 2)
                if speed_bps > 0
                else 0,
                "is_active": session.status in ["started", "in_progress", "paused"],
                "is_complete": session.status == "completed",
                "can_retry": session.status == "failed",
            }

        except Exception as e:
            logger.error(f"Error getting session details for {session_id}: {e}")
            return {"status": "error", "session_id": session_id, "error": str(e)}

    def get_active_sessions(self) -> list[dict[str, Any]]:
        """Get all active download sessions with details."""
        try:
            sessions = self.db_manager.get_active_download_sessions()
            active_sessions = []

            for session in sessions:
                # Get model information
                model = self.db_manager.get_model(session.model_id)
                model_name = (
                    model.name if model else f"Unknown (ID: {session.model_id})"
                )

                # Calculate progress
                progress = 0
                if session.total_bytes and session.total_bytes > 0:
                    progress = (session.bytes_downloaded / session.total_bytes) * 100

                # Calculate duration
                duration_seconds = 0
                if session.started_at:
                    end_time = session.completed_at or datetime.now()
                    duration_seconds = (end_time - session.started_at).total_seconds()

                # Calculate current speed
                speed_bps = 0
                if session.bytes_downloaded > 0 and duration_seconds > 0:
                    speed_bps = session.bytes_downloaded / duration_seconds

                active_sessions.append(
                    {
                        "session_id": session.id,
                        "model_name": model_name,
                        "status": session.status,
                        "progress_percentage": round(progress, 2),
                        "bytes_downloaded": session.bytes_downloaded,
                        "total_bytes": session.total_bytes,
                        "download_speed_bps": round(speed_bps, 2),
                        "download_speed_mbps": round(speed_bps / (1024 * 1024), 2)
                        if speed_bps > 0
                        else 0,
                        "duration_seconds": duration_seconds,
                        "retry_count": session.retry_count,
                        "started_at": session.started_at.isoformat()
                        if session.started_at
                        else None,
                        "schedule_id": session.schedule_id,
                    }
                )

            return active_sessions

        except Exception as e:
            logger.error(f"Error getting active sessions: {e}")
            return []

    def get_download_statistics(
        self,
        model_id: int | None = None,
        schedule_id: int | None = None,
        time_range_days: int | None = None,
    ) -> dict[str, Any]:
        """Get comprehensive download statistics."""
        try:
            stats = self.db_manager.get_session_statistics(
                model_id=model_id,
                schedule_id=schedule_id,
                time_range_days=time_range_days,
            )

            # Add current active downloads information
            active_sessions = self.get_active_sessions()
            stats["current_active_downloads"] = len(active_sessions)
            stats["current_downloading_models"] = [
                s["model_name"] for s in active_sessions
            ]

            # Add total models information
            total_models = len(self.db_manager.get_all_models())
            stats["total_models_tracked"] = total_models

            return stats

        except Exception as e:
            logger.error(f"Error getting download statistics: {e}")
            return {"status": "error", "error": str(e)}

    def retry_failed_download(
        self, session_id: int, schedule_id: int | None = None
    ) -> dict[str, Any]:
        """Retry a failed download session."""
        try:
            # Get the original session
            original_session = self.db_manager.get_download_session(session_id)
            if not original_session:
                return {
                    "status": "not_found",
                    "session_id": session_id,
                    "message": "Session not found",
                }

            if original_session.status != "failed":
                return {
                    "status": "invalid_state",
                    "session_id": session_id,
                    "message": f"Cannot retry session with status: {original_session.status}",
                }

            # Get model information
            model = self.db_manager.get_model_by_id(original_session.model_id)
            if not model:
                return {
                    "status": "error",
                    "session_id": session_id,
                    "message": "Associated model not found",
                }

            # Create retry session
            new_session = self.db_manager.retry_failed_session(session_id, schedule_id)
            if not new_session:
                return {
                    "status": "error",
                    "session_id": session_id,
                    "message": "Failed to create retry session",
                }

            # Update model status
            self.db_manager.update_model_status(model.id, "downloading")

            return {
                "status": "retry_created",
                "original_session_id": session_id,
                "new_session_id": new_session.id,
                "model": model.name,
                "retry_count": new_session.retry_count,
                "message": f"Created retry session for {model.name}",
            }

        except Exception as e:
            logger.error(
                f"Error retrying failed download for session {session_id}: {e}"
            )
            return {"status": "error", "session_id": session_id, "error": str(e)}

    def cancel_session(self, session_id: int) -> dict[str, Any]:
        """Cancel a specific download session."""
        try:
            session = self.db_manager.get_download_session(session_id)
            if not session:
                return {
                    "status": "not_found",
                    "session_id": session_id,
                    "message": "Session not found",
                }

            if session.status not in ["started", "in_progress", "paused"]:
                return {
                    "status": "invalid_state",
                    "session_id": session_id,
                    "message": f"Cannot cancel session with status: {session.status}",
                }

            # Get model information
            model = self.db_manager.get_model(session.model_id)
            if model:
                model_name = model.name
                # Set cancel flag if currently downloading
                if model_name in self._active_downloads:
                    self._cancel_flags[model_name] = True

                # Update model status
                self.db_manager.update_model_status(model.id, "paused")

            # Update session status
            self.db_manager.update_download_session(
                session_id, "cancelled", error_message="Cancelled by user"
            )

            return {
                "status": "cancelled",
                "session_id": session_id,
                "model": model_name if model else f"Unknown (ID: {session.model_id})",
                "message": "Session cancelled successfully",
            }

        except Exception as e:
            logger.error(f"Error cancelling session {session_id}: {e}")
            return {"status": "error", "session_id": session_id, "error": str(e)}
