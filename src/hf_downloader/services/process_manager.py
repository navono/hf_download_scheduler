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

        # 守护进程监控相关
        self._watchdog_thread: threading.Thread | None = None
        self._watchdog_enabled = False
        self._watchdog_interval = 60  # 默认每60秒检查一次
        self._auto_restart = True  # 默认启用自动重启
        self._max_restart_attempts = 3  # 默认最大重启尝试次数
        self._restart_attempts = 0  # 当前重启尝试次数
        self._last_restart_time = 0  # 上次重启时间戳

        # 系统资源监控相关
        self._resource_monitor_thread: threading.Thread | None = None
        self._resource_monitor_enabled = False
        self._resource_monitor_interval = 60  # 默认每60秒检查一次
        self._memory_threshold = 90  # 内存使用率阈值（百分比）
        self._cpu_threshold = 95  # CPU使用率阈值（百分比）
        self._system_resources = {}
        self._resource_warnings = 0  # 资源警告计数

        # 健康状态报告相关
        self._health_report_thread: threading.Thread | None = None
        self._health_report_enabled = False
        self._health_report_interval = 3600  # 默认每小时生成一次报告
        self._last_health_report_time = 0  # 上次生成报告的时间戳

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

                # 启动守护进程监控
                self._start_watchdog()

            return result

        except Exception as e:
            logger.error(f"Error starting daemon: {e}")
            return {"status": "error", "error": str(e)}

    def stop_daemon(self) -> dict[str, Any]:
        """Stop the downloader daemon."""
        try:
            # 停止守护进程监控
            self._stop_watchdog()

            # First try to get PID from PID file
            pid = self._get_current_pid()

            if not pid:
                # If no PID file, try to find daemon process by name
                logger.warning("No PID file found, trying to find daemon process by name")
                pid = self._find_daemon_process_by_name()

            if not pid:
                return {"status": "not_running", "message": "Daemon is not running"}

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
            # Get current Python executable
            python_executable = sys.executable

            # Use Python module path instead of script path
            # This ensures relative imports work correctly

            # Prepare daemon command
            daemon_command = [
                python_executable,
                "-m",
                "hf_downloader.daemon.main",  # Use module path
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
                # Capture output to understand why it exited
                stdout, stderr = self._daemon_process.communicate()
                error_output = (
                    stderr.decode("utf-8", errors="replace") if stderr else ""
                )
                logger.error(
                    f"Daemon process exited immediately with error: {error_output}"
                )

                return {
                    "status": "failed",
                    "error": "Daemon process exited immediately",
                    "stderr": error_output,
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

    def _start_watchdog(self):
        """启动守护进程监控线程"""
        if hasattr(self.config, "monitoring") and isinstance(
            self.config.monitoring, dict
        ):
            self._watchdog_enabled = self.config.monitoring.get(
                "watchdog_enabled", True
            )
            self._watchdog_interval = self.config.monitoring.get(
                "watchdog_interval", 60
            )
            self._auto_restart = self.config.monitoring.get("auto_restart", True)
            self._max_restart_attempts = self.config.monitoring.get(
                "max_restart_attempts", 3
            )

            # 资源监控相关配置
            self._resource_monitor_enabled = self.config.monitoring.get(
                "resource_monitor_enabled", True
            )
            self._resource_monitor_interval = self.config.monitoring.get(
                "resource_monitor_interval", 60
            )
            self._memory_threshold = self.config.monitoring.get("memory_threshold", 90)
            self._cpu_threshold = self.config.monitoring.get("cpu_threshold", 95)

            # 健康状态报告相关配置
            self._health_report_enabled = self.config.monitoring.get(
                "health_report_enabled", True
            )
            self._health_report_interval = self.config.monitoring.get(
                "health_report_interval", 3600
            )

        if not self._watchdog_enabled:
            logger.info("Watchdog is disabled in configuration")
            return

        # 停止已有的监控线程
        self._stop_watchdog()

        # 创建新的监控线程
        self._restart_attempts = 0
        self._shutdown_event.clear()
        self._watchdog_thread = threading.Thread(
            target=self._watchdog_loop, daemon=True, name="DaemonWatchdog"
        )
        self._watchdog_thread.start()
        logger.info(
            f"Daemon watchdog started with interval {self._watchdog_interval} seconds"
        )

        # 启动资源监控线程
        if self._resource_monitor_enabled:
            self._start_resource_monitor()

        # 启动健康状态报告线程
        if self._health_report_enabled:
            self._start_health_report()

    def _stop_watchdog(self):
        """停止守护进程监控线程"""
        if self._watchdog_thread and self._watchdog_thread.is_alive():
            self._shutdown_event.set()
            self._watchdog_thread.join(timeout=5)
            logger.info("Daemon watchdog stopped")

        # 同时停止资源监控线程
        self._stop_resource_monitor()

    def _watchdog_loop(self):
        """守护进程监控循环"""
        logger.info("Watchdog monitoring loop started")

        while not self._shutdown_event.is_set():
            try:
                # 检查守护进程是否运行
                health_status = self.validate_daemon_health()

                if health_status["status"] == "unhealthy":
                    logger.warning(f"Daemon is unhealthy: {health_status['reason']}")

                    # 如果配置了自动重启且未超过最大重启次数
                    if (
                        self._auto_restart
                        and self._restart_attempts < self._max_restart_attempts
                    ):
                        # 检查上次重启时间，避免频繁重启
                        current_time = time.time()
                        if (
                            current_time - self._last_restart_time > 300
                        ):  # 至少间隔5分钟
                            self._restart_attempts += 1
                            self._last_restart_time = current_time

                            logger.warning(
                                f"Attempting to restart daemon (attempt {self._restart_attempts}/{self._max_restart_attempts})"
                            )

                            # 清理可能存在的僵尸进程
                            self.cleanup_stale_pids()

                            # 重启守护进程
                            restart_result = self._start_daemon_process()
                            if restart_result["status"] == "started":
                                self._write_pid_file(restart_result["pid"])
                                logger.info(
                                    f"Daemon restarted successfully with PID {restart_result['pid']}"
                                )
                            else:
                                logger.error(
                                    f"Failed to restart daemon: {restart_result}"
                                )
                    elif self._restart_attempts >= self._max_restart_attempts:
                        logger.error(
                            f"Maximum restart attempts ({self._max_restart_attempts}) reached. "
                            "Manual intervention required."
                        )
                elif health_status["status"] == "warning":
                    logger.warning(f"Daemon health warning: {health_status['reason']}")
                else:
                    # 如果守护进程健康，重置重启计数
                    if self._restart_attempts > 0:
                        logger.info(
                            "Daemon is healthy again, resetting restart attempts counter"
                        )
                        self._restart_attempts = 0

            except Exception as e:
                logger.error(f"Error in watchdog loop: {e}")

            # 等待下一次检查
            self._shutdown_event.wait(self._watchdog_interval)

        logger.info("Watchdog monitoring loop stopped")

    def _start_resource_monitor(self):
        """启动系统资源监控线程"""
        # 停止已有的资源监控线程
        self._stop_resource_monitor()

        # 创建新的资源监控线程
        self._resource_warnings = 0
        self._resource_monitor_thread = threading.Thread(
            target=self._resource_monitor_loop, daemon=True, name="ResourceMonitor"
        )
        self._resource_monitor_thread.start()
        logger.info(
            f"Resource monitor started with interval {self._resource_monitor_interval} seconds"
        )

    def _stop_resource_monitor(self):
        """停止系统资源监控线程"""
        if self._resource_monitor_thread and self._resource_monitor_thread.is_alive():
            self._shutdown_event.set()
            self._resource_monitor_thread.join(timeout=5)
            logger.info("Resource monitor stopped")

        # 同时停止健康状态报告线程
        self._stop_health_report()

    def _resource_monitor_loop(self):
        """系统资源监控循环"""
        logger.info("Resource monitoring loop started")

        while not self._shutdown_event.is_set():
            try:
                # 获取系统资源使用情况
                system_resources = self._get_system_resources()
                self._system_resources = system_resources

                # 检查内存使用率
                memory_percent = system_resources.get("memory_percent", 0)
                if memory_percent > self._memory_threshold:
                    self._resource_warnings += 1
                    logger.warning(
                        f"System memory usage ({memory_percent:.1f}%) exceeds threshold ({self._memory_threshold}%)"
                    )

                    # 如果守护进程正在运行，尝试释放内存
                    pid = self._get_current_pid()
                    if pid:
                        self._optimize_daemon_memory(pid)

                # 检查CPU使用率
                cpu_percent = system_resources.get("cpu_percent", 0)
                if cpu_percent > self._cpu_threshold:
                    self._resource_warnings += 1
                    logger.warning(
                        f"System CPU usage ({cpu_percent:.1f}%) exceeds threshold ({self._cpu_threshold}%)"
                    )

                    # 如果守护进程正在运行，尝试降低 CPU 使用率
                    pid = self._get_current_pid()
                    if pid:
                        self._optimize_daemon_cpu(pid)

                # 如果资源正常，重置警告计数
                if (
                    memory_percent < self._memory_threshold
                    and cpu_percent < self._cpu_threshold
                ):
                    if self._resource_warnings > 0:
                        logger.info("System resources back to normal levels")
                        self._resource_warnings = 0

            except Exception as e:
                logger.error(f"Error in resource monitor loop: {e}")

            # 等待下一次检查
            self._shutdown_event.wait(self._resource_monitor_interval)

        logger.info("Resource monitoring loop stopped")

    def _get_system_resources(self) -> dict[str, Any]:
        """获取系统资源使用情况"""
        try:
            # 获取系统内存使用情况
            virtual_memory = psutil.virtual_memory()
            swap_memory = psutil.swap_memory()

            # 获取CPU使用情况
            cpu_percent = psutil.cpu_percent(interval=1)
            cpu_count = psutil.cpu_count()

            # 获取磁盘使用情况
            disk_usage = psutil.disk_usage("/")

            return {
                "timestamp": datetime.now().isoformat(),
                "memory": {
                    "total": virtual_memory.total,
                    "available": virtual_memory.available,
                    "used": virtual_memory.used,
                    "free": virtual_memory.free,
                    "percent": virtual_memory.percent,
                    "total_formatted": self._format_bytes(virtual_memory.total),
                    "available_formatted": self._format_bytes(virtual_memory.available),
                    "used_formatted": self._format_bytes(virtual_memory.used),
                    "free_formatted": self._format_bytes(virtual_memory.free),
                },
                "swap": {
                    "total": swap_memory.total,
                    "used": swap_memory.used,
                    "free": swap_memory.free,
                    "percent": swap_memory.percent,
                    "total_formatted": self._format_bytes(swap_memory.total),
                    "used_formatted": self._format_bytes(swap_memory.used),
                    "free_formatted": self._format_bytes(swap_memory.free),
                },
                "cpu": {
                    "percent": cpu_percent,
                    "count": cpu_count,
                },
                "disk": {
                    "total": disk_usage.total,
                    "used": disk_usage.used,
                    "free": disk_usage.free,
                    "percent": disk_usage.percent,
                    "total_formatted": self._format_bytes(disk_usage.total),
                    "used_formatted": self._format_bytes(disk_usage.used),
                    "free_formatted": self._format_bytes(disk_usage.free),
                },
                "memory_percent": virtual_memory.percent,
                "cpu_percent": cpu_percent,
                "disk_percent": disk_usage.percent,
            }

        except Exception as e:
            logger.error(f"Error getting system resources: {e}")
            return {}

    def _optimize_daemon_memory(self, pid: int):
        """尝试优化守护进程的内存使用"""
        try:
            process = psutil.Process(pid)
            process_memory = process.memory_info()

            logger.warning(
                f"Daemon process (PID {pid}) memory usage: {self._format_bytes(process_memory.rss)}"
            )

            # 记录内存使用情况
            self.db_manager.add_system_log(
                "memory_warning",
                f"High memory usage detected: {self._format_bytes(process_memory.rss)}",
                {"pid": pid, "rss": process_memory.rss, "vms": process_memory.vms},
            )

            # 如果内存使用过高，可以尝试调用GC或其他方法释放内存
            # 这里只是记录日志，实际应用中可以添加更多的内存优化策略

        except Exception as e:
            logger.error(f"Error optimizing daemon memory: {e}")

    def _optimize_daemon_cpu(self, pid: int):
        """尝试优化守护进程的CPU使用"""
        try:
            process = psutil.Process(pid)
            cpu_percent = process.cpu_percent(interval=1)

            logger.warning(f"Daemon process (PID {pid}) CPU usage: {cpu_percent:.1f}%")

            # 记录CPU使用情况
            self.db_manager.add_system_log(
                "cpu_warning",
                f"High CPU usage detected: {cpu_percent:.1f}%",
                {"pid": pid, "cpu_percent": cpu_percent},
            )

            # 如果CPU使用过高，可以尝试降低进程优先级或其他方法
            # 这里只是记录日志，实际应用中可以添加更多的CPU优化策略

        except Exception as e:
            logger.error(f"Error optimizing daemon CPU: {e}")

    def _start_health_report(self):
        """启动健康状态报告线程"""
        # 停止已有的健康状态报告线程
        self._stop_health_report()

        # 创建新的健康状态报告线程
        self._health_report_thread = threading.Thread(
            target=self._health_report_loop, daemon=True, name="HealthReport"
        )
        self._health_report_thread.start()
        logger.info(
            f"Health report thread started with interval {self._health_report_interval} seconds"
        )

    def _stop_health_report(self):
        """停止健康状态报告线程"""
        if self._health_report_thread and self._health_report_thread.is_alive():
            self._shutdown_event.set()
            self._health_report_thread.join(timeout=5)
            logger.info("Health report thread stopped")

    def _health_report_loop(self):
        """健康状态报告循环"""
        logger.info("Health report loop started")

        while not self._shutdown_event.is_set():
            try:
                # 检查是否到了生成报告的时间
                current_time = time.time()
                if (
                    current_time - self._last_health_report_time
                    > self._health_report_interval
                ):
                    self._last_health_report_time = current_time
                    self._generate_health_report()

            except Exception as e:
                logger.error(f"Error in health report loop: {e}")

            # 等待下一次检查
            self._shutdown_event.wait(
                min(300, self._health_report_interval)
            )  # 最多等待5分钟

        logger.info("Health report loop stopped")

    def _generate_health_report(self):
        """生成健康状态报告"""
        try:
            # 获取守护进程状态
            daemon_status = self.get_daemon_status(detailed=True)

            # 获取系统资源使用情况
            system_resources = self._get_system_resources()

            # 获取最近的系统日志
            recent_logs = self.db_manager.get_recent_system_logs(limit=20)
            recent_logs_summary = {
                "total": len(recent_logs),
                "warnings": len(
                    [log for log in recent_logs if "warning" in log.log_type.lower()]
                ),
                "errors": len(
                    [log for log in recent_logs if "error" in log.log_type.lower()]
                ),
            }

            # 生成报告
            report = {
                "timestamp": datetime.now().isoformat(),
                "daemon_status": daemon_status,
                "system_resources": system_resources,
                "recent_logs_summary": recent_logs_summary,
                "restart_attempts": self._restart_attempts,
                "resource_warnings": self._resource_warnings,
            }

            # 记录健康状态报告
            self.db_manager.add_system_log(
                "health_report", "Periodic health report generated", report
            )

            logger.info("Health report generated successfully")

            # 如果有警告或错误，记录更详细的日志
            if recent_logs_summary["warnings"] > 0 or recent_logs_summary["errors"] > 0:
                logger.warning(
                    f"Health report contains warnings/errors: "
                    f"{recent_logs_summary['warnings']} warnings, "
                    f"{recent_logs_summary['errors']} errors"
                )

        except Exception as e:
            logger.error(f"Error generating health report: {e}")

    def _find_daemon_process_by_name(self) -> int | None:
        """Find daemon process by name when PID file is missing."""
        try:
            import subprocess

            # Look for python processes with daemon main module
            cmd = ["ps", "aux"]
            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode != 0:
                logger.error("Failed to execute ps command")
                return None

            # Parse ps output to find daemon process
            for line in result.stdout.split('\n'):
                if 'hf_downloader.daemon.main' in line and 'grep' not in line:
                    # Extract PID from the line (second field)
                    parts = line.split()
                    if len(parts) >= 2:
                        try:
                            pid = int(parts[1])
                            # Verify it's actually our daemon process
                            if self._verify_daemon_process(pid):
                                logger.info(f"Found daemon process with PID: {pid}")
                                return pid
                        except (ValueError, IndexError):
                            continue

            logger.info("No daemon process found by name")
            return None

        except Exception as e:
            logger.error(f"Error finding daemon process by name: {e}")
            return None

    def _verify_daemon_process(self, pid: int) -> bool:
        """Verify that the process is actually our daemon."""
        try:
            import subprocess

            # Check process command line to confirm it's our daemon
            cmd = ["ps", "-p", str(pid), "-o", "command="]
            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode != 0:
                return False

            cmdline = result.stdout.strip()
            return 'hf_downloader.daemon.main' in cmdline

        except Exception as e:
            logger.error(f"Error verifying daemon process {pid}: {e}")
            return False
