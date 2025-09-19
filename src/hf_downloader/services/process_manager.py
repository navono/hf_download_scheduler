"""
Process manager service for HF Downloader.

This module handles daemon process management, including starting, stopping,
and monitoring the downloader daemon.
"""

import os
import platform
import signal
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import psutil
from loguru import logger

from ..core.config import Config
from ..models.database import DatabaseManager


class ProcessManager:
    """Manages the downloader daemon process."""

    def __init__(
        self,
        config: Config,
        db_path: str,
        pid_path: str,
        config_path: str = "./config/default.yaml",
    ):
        """Initialize process manager."""
        self.config = config
        self.config_path = config_path
        self.db_manager = DatabaseManager(db_path)
        self.pid_path = Path(pid_path)
        self._daemon_process: subprocess.Popen | None = None
        self._shutdown_event = threading.Event()

    def start_daemon(self) -> dict[str, Any]:
        """Start the downloader daemon."""
        try:
            # Check if daemon is already running
            if self._is_daemon_running():
                return {
                    "status": "already_running",
                    "message": "Daemon is already running",
                    "pid": self._get_current_pid(),
                }

            # Start daemon process
            result = self._start_daemon_process()

            if result["status"] == "started":
                # Write PID file
                self._write_pid_file(result["pid"])
                logger.info(f"Daemon started with PID {result['pid']}")

            return result

        except Exception as e:
            logger.error(f"Error starting daemon: {e}")
            return {"status": "error", "error": str(e)}

    def stop_daemon(self) -> dict[str, Any]:
        """Stop the downloader daemon."""
        try:
            if not self._is_daemon_running():
                return {"status": "not_running", "message": "Daemon is not running"}

            pid = self._get_current_pid()
            if not pid:
                return {"status": "no_pid_file", "message": "No PID file found"}

            # Try graceful shutdown first
            if self._stop_daemon_gracefully(pid):
                return {
                    "status": "stopped",
                    "message": "Daemon stopped gracefully",
                    "pid": pid,
                }
            else:
                # Force kill if graceful shutdown fails
                if self._kill_daemon_forcefully(pid):
                    return {
                        "status": "stopped",
                        "message": "Daemon killed forcefully",
                        "pid": pid,
                    }
                else:
                    return {
                        "status": "error",
                        "message": "Failed to stop daemon",
                        "pid": pid,
                    }

        except Exception as e:
            logger.error(f"Error stopping daemon: {e}")
            return {"status": "error", "error": str(e)}

    def restart_daemon(self) -> dict[str, Any]:
        """Restart the downloader daemon."""
        try:
            # Stop existing daemon
            stop_result = self.stop_daemon()

            # Wait a bit for process to clean up
            time.sleep(2)

            # Start new daemon
            start_result = self.start_daemon()

            return {
                "status": "restarted",
                "stop_result": stop_result,
                "start_result": start_result,
            }

        except Exception as e:
            logger.error(f"Error restarting daemon: {e}")
            return {"status": "error", "error": str(e)}

    def get_daemon_status(self, detailed: bool = False) -> dict[str, Any]:
        """Get daemon status."""
        try:
            if not self._is_daemon_running():
                return {"status": "stopped", "message": "Daemon is not running"}

            pid = self._get_current_pid()
            if not pid:
                return {"status": "no_pid_file", "message": "PID file not found"}

            status_info = {
                "status": "running",
                "pid": pid,
                "uptime": self._get_daemon_uptime(pid),
                "memory_usage": self._get_memory_usage(pid) if detailed else None,
                "cpu_usage": self._get_cpu_usage(pid) if detailed else None,
                "start_time": self._get_process_start_time(pid) if detailed else None,
            }

            return status_info

        except Exception as e:
            logger.error(f"Error getting daemon status: {e}")
            return {"status": "error", "error": str(e)}

    def _start_daemon_process(self) -> dict[str, Any]:
        """Start the daemon process."""
        try:
            # Get current Python executable and script path
            python_executable = sys.executable

            # Path to the daemon script
            daemon_script = Path(__file__).parent.parent / "daemon" / "main.py"

            # Prepare daemon command
            daemon_command = [
                python_executable,
                str(daemon_script),
                "--config",
                str(self.config_path),
                "--database",
                str(self.config.database_path),
                "--pid",
                str(self.pid_path),
                "--log-level",
                self.config.log_level,
            ]

            # Start daemon process
            if platform.system() == "Windows":
                # Windows doesn't support daemon mode in the same way
                # Start as a background process
                self._daemon_process = subprocess.Popen(
                    daemon_command,
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    stdin=subprocess.PIPE,
                )
            else:
                # Unix-like systems - use proper daemon mode
                self._daemon_process = subprocess.Popen(
                    daemon_command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    stdin=subprocess.PIPE,
                    preexec_fn=os.setsid,
                )

            pid = self._daemon_process.pid

            # Wait a bit to see if process starts successfully
            time.sleep(2)

            # Check if process is still running
            if self._daemon_process.poll() is None:
                return {
                    "status": "started",
                    "pid": pid,
                    "message": "Daemon started successfully",
                }
            else:
                # Process exited immediately
                return {
                    "status": "failed",
                    "error": "Daemon process exited immediately",
                }

        except Exception as e:
            logger.error(f"Error starting daemon process: {e}")
            return {"status": "error", "error": str(e)}

    def _stop_daemon_gracefully(self, pid: int) -> bool:
        """Stop daemon gracefully."""
        try:
            # Send SIGTERM to the daemon process
            if platform.system() == "Windows":
                # Windows doesn't have SIGTERM, use taskkill
                result = subprocess.run(
                    ["taskkill", "/PID", str(pid), "/F"], capture_output=True, text=True
                )
                return result.returncode == 0
            else:
                # Unix-like systems
                os.kill(pid, signal.SIGTERM)

                # Wait for graceful shutdown
                for _ in range(30):  # 30 seconds timeout
                    if not self._is_process_running(pid):
                        break
                    time.sleep(1)

                # Remove PID file if process stopped
                if not self._is_process_running(pid):
                    self._remove_pid_file()
                    return True

            return False

        except ProcessLookupError:
            # Process doesn't exist
            self._remove_pid_file()
            return True
        except Exception as e:
            logger.error(f"Error stopping daemon gracefully: {e}")
            return False

    def _kill_daemon_forcefully(self, pid: int) -> bool:
        """Kill daemon forcefully."""
        try:
            if platform.system() == "Windows":
                # Windows force kill
                result = subprocess.run(
                    ["taskkill", "/PID", str(pid), "/F", "/T"],
                    capture_output=True,
                    text=True,
                )
                return result.returncode == 0
            else:
                # Unix-like systems - SIGKILL
                os.kill(pid, signal.SIGKILL)

                # Wait and check if process is dead
                time.sleep(2)
                if not self._is_process_running(pid):
                    self._remove_pid_file()
                    return True

            return False

        except ProcessLookupError:
            # Process doesn't exist
            self._remove_pid_file()
            return True
        except Exception as e:
            logger.error(f"Error killing daemon forcefully: {e}")
            return False

    def _is_daemon_running(self) -> bool:
        """Check if daemon is running."""
        try:
            pid = self._get_current_pid()
            if not pid:
                return False

            return self._is_process_running(pid)

        except Exception as e:
            logger.error(f"Error checking if daemon is running: {e}")
            return False

    def _is_process_running(self, pid: int) -> bool:
        """Check if a process is running."""
        try:
            if platform.system() == "Windows":
                # Windows process check
                result = subprocess.run(
                    ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV"],
                    capture_output=True,
                    text=True,
                )
                return f'"{pid}"' in result.stdout
            else:
                # Unix-like systems
                os.kill(pid, 0)  # Send signal 0 to check if process exists
                return True

        except (ProcessLookupError, PermissionError):
            return False
        except Exception as e:
            logger.error(f"Error checking if process {pid} is running: {e}")
            return False

    def _get_current_pid(self) -> int | None:
        """Get current daemon PID from PID file."""
        try:
            if not self.pid_path.exists():
                return None

            with open(self.pid_path) as f:
                pid_content = f.read().strip()

            if pid_content:
                return int(pid_content)

            return None

        except (OSError, ValueError) as e:
            logger.error(f"Error reading PID file: {e}")
            return None

    def _write_pid_file(self, pid: int):
        """Write PID file."""
        try:
            # Create parent directory if it doesn't exist
            self.pid_path.parent.mkdir(parents=True, exist_ok=True)

            with open(self.pid_path, "w") as f:
                f.write(str(pid))

        except Exception as e:
            logger.error(f"Error writing PID file: {e}")

    def _remove_pid_file(self):
        """Remove PID file."""
        try:
            if self.pid_path.exists():
                self.pid_path.unlink()
        except Exception as e:
            logger.error(f"Error removing PID file: {e}")

    def _get_daemon_uptime(self, pid: int) -> str:
        """Get daemon uptime."""
        try:
            process = psutil.Process(pid)
            create_time = datetime.fromtimestamp(process.create_time())
            uptime = datetime.now() - create_time

            # Format uptime
            days = uptime.days
            hours, remainder = divmod(uptime.seconds, 3600)
            minutes, seconds = divmod(remainder, 60)

            if days > 0:
                return f"{days}d {hours}h {minutes}m"
            elif hours > 0:
                return f"{hours}h {minutes}m {seconds}s"
            elif minutes > 0:
                return f"{minutes}m {seconds}s"
            else:
                return f"{seconds}s"

        except Exception as e:
            logger.error(f"Error getting daemon uptime: {e}")
            return "unknown"

    def _get_memory_usage(self, pid: int) -> dict[str, Any]:
        """Get daemon memory usage."""
        try:
            process = psutil.Process(pid)
            memory_info = process.memory_info()

            return {
                "rss": memory_info.rss,  # Resident Set Size
                "vms": memory_info.vms,  # Virtual Memory Size
                "percent": process.memory_percent(),
                "rss_formatted": self._format_bytes(memory_info.rss),
                "vms_formatted": self._format_bytes(memory_info.vms),
            }

        except Exception as e:
            logger.error(f"Error getting memory usage: {e}")
            return {}

    def _get_cpu_usage(self, pid: int) -> float:
        """Get daemon CPU usage."""
        try:
            process = psutil.Process(pid)
            return process.cpu_percent(interval=1)

        except Exception as e:
            logger.error(f"Error getting CPU usage: {e}")
            return 0.0

    def _get_process_start_time(self, pid: int) -> str | None:
        """Get process start time."""
        try:
            process = psutil.Process(pid)
            start_time = datetime.fromtimestamp(process.create_time())
            return start_time.isoformat()

        except Exception as e:
            logger.error(f"Error getting process start time: {e}")
            return None

    def _format_bytes(self, bytes_value: int) -> str:
        """Format bytes to human readable format."""
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if bytes_value < 1024.0:
                return f"{bytes_value:.2f} {unit}"
            bytes_value /= 1024.0
        return f"{bytes_value:.2f} PB"

    def cleanup_stale_pids(self):
        """Clean up stale PID files."""
        try:
            if self.pid_path.exists():
                pid = self._get_current_pid()
                if pid and not self._is_process_running(pid):
                    self._remove_pid_file()
                    logger.info("Cleaned up stale PID file")

        except Exception as e:
            logger.error(f"Error cleaning up stale PID files: {e}")

    def validate_daemon_health(self) -> dict[str, Any]:
        """Validate daemon health."""
        try:
            if not self._is_daemon_running():
                return {"status": "unhealthy", "reason": "daemon_not_running"}

            pid = self._get_current_pid()
            if not pid:
                return {"status": "unhealthy", "reason": "no_pid_file"}

            # Check if process is responsive
            process = psutil.Process(pid)
            if process.status() == psutil.STATUS_ZOMBIE:
                return {"status": "unhealthy", "reason": "zombie_process"}

            # Check memory usage
            memory_percent = process.memory_percent()
            if memory_percent > 90:
                return {
                    "status": "warning",
                    "reason": "high_memory_usage",
                    "memory_percent": memory_percent,
                }

            # Check CPU usage
            cpu_percent = process.cpu_percent(interval=1)
            if cpu_percent > 95:
                return {
                    "status": "warning",
                    "reason": "high_cpu_usage",
                    "cpu_percent": cpu_percent,
                }

            return {
                "status": "healthy",
                "pid": pid,
                "memory_percent": memory_percent,
                "cpu_percent": cpu_percent,
            }

        except Exception as e:
            logger.error(f"Error validating daemon health: {e}")
            return {"status": "error", "error": str(e)}
