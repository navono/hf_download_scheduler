"""
Error handling and logging integration for HF Downloader.

This module provides centralized error handling, logging configuration,
and structured logging capabilities for the entire application.
"""

import functools
import traceback
from collections.abc import Callable
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from loguru import logger


# Custom exception types
class HFDownloaderError(Exception):
    """Base exception for HF Downloader."""

    pass


class ConfigurationError(HFDownloaderError):
    """Configuration related errors."""

    pass


class DatabaseError(HFDownloaderError):
    """Database related errors."""

    pass


class DownloadError(HFDownloaderError):
    """Download related errors."""

    pass


class ScheduleError(HFDownloaderError):
    """Schedule related errors."""

    pass


class ProcessError(HFDownloaderError):
    """Process related errors."""

    pass


class AuthenticationError(HFDownloaderError):
    """Authentication related errors."""

    pass


class NetworkError(HFDownloaderError):
    """Network related errors."""

    pass


class ValidationError(HFDownloaderError):
    """Validation related errors."""

    pass


class ErrorSeverity(Enum):
    """Error severity levels."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class ErrorContext:
    """Context for error information."""

    def __init__(self, operation: str, component: str, **kwargs):
        """Initialize error context."""
        self.operation = operation
        self.component = component
        self.timestamp = datetime.now(UTC)
        self.metadata = kwargs
        self.stack_trace = traceback.format_stack()[:-2]  # Exclude current frame

    def to_dict(self) -> dict[str, Any]:
        """Convert context to dictionary."""
        return {
            "operation": self.operation,
            "component": self.component,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
            "stack_trace": self.stack_trace,
        }


class ErrorHandler:
    """Centralized error handler."""

    def __init__(self):
        """Initialize error handler."""
        self.error_callbacks: dict[str, list[Callable]] = {}

    def register_callback(self, error_type: str, callback: Callable):
        """Register error callback."""
        if error_type not in self.error_callbacks:
            self.error_callbacks[error_type] = []
        self.error_callbacks[error_type].append(callback)

    def handle_error(
        self,
        error: Exception,
        context: ErrorContext | None = None,
        reraise: bool = False,
        **kwargs,
    ):
        """Handle error with logging and callbacks."""
        # Determine error type
        error_type = type(error).__name__

        # Log error
        severity = self._determine_severity(error)
        logger.error(error, context, severity, **kwargs)

        # Execute callbacks
        if error_type in self.error_callbacks:
            for callback in self.error_callbacks[error_type]:
                try:
                    callback(error, context, **kwargs)
                except Exception as callback_error:
                    logger.error(
                        callback_error,
                        ErrorContext("error_callback", "ErrorHandler"),
                        ErrorSeverity.ERROR,
                        original_error=error_type,
                    )

        # Reraise if requested
        if reraise:
            raise error

    def _determine_severity(self, error: Exception) -> ErrorSeverity:
        """Determine error severity."""
        if isinstance(error, (AuthenticationError, ProcessError)):
            return ErrorSeverity.CRITICAL
        elif isinstance(error, (DatabaseError, NetworkError)):
            return ErrorSeverity.ERROR
        elif isinstance(error, (ConfigurationError, ValidationError)):
            return ErrorSeverity.WARNING
        else:
            return ErrorSeverity.ERROR


def handle_errors(
    component: str, operation: str, reraise: bool = False, _log_level: str = "ERROR"
):
    """Decorator for error handling."""

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            handler = ErrorHandler()

            try:
                return func(*args, **kwargs)
            except Exception as e:
                context = ErrorContext(operation, component)
                handler.handle_error(
                    e, context, reraise=reraise, function=func.__name__
                )
                if reraise:
                    raise
                return None

        return wrapper

    return decorator


class OperationTimer:
    """Context manager for timing operations."""

    def __init__(
        self, error_logger: "ErrorLogger", operation: str, component: str, **kwargs
    ):
        """Initialize operation timer."""
        self.error_logger = error_logger
        self.operation = operation
        self.component = component
        self.kwargs = kwargs
        self.start_time = None
        self.end_time = None

    def __enter__(self):
        """Start timing."""
        self.start_time = datetime.now(UTC)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """End timing and log."""
        self.end_time = datetime.now(UTC)
        duration = (self.end_time - self.start_time).total_seconds()

        if exc_type is None:
            status = "completed"
            self.error_logger.log_operation(
                self.operation, status, self.component, duration=duration, **self.kwargs
            )
        else:
            status = "failed"
            self.error_logger.log_error(
                exc_val,
                ErrorContext(self.operation, self.component),
                ErrorSeverity.ERROR,
                duration=duration,
                **self.kwargs,
            )

    def elapsed(self) -> float:
        """Get elapsed time."""
        if self.start_time is None:
            return 0.0
        end_time = self.end_time or datetime.now(UTC)
        return (end_time - self.start_time).total_seconds()


class ErrorLogger:
    """Error logger with structured logging capabilities."""

    def __init__(self, component: str, operation: str, **kwargs):
        """Initialize error logger."""
        self.component = component
        self.operation = operation
        self.kwargs = kwargs

    def log_structured(self, level: str, message: str, **extra_kwargs):
        """Log a structured message."""
        self._log(message, level, **extra_kwargs)

    def log_error(
        self,
        error: Exception,
        context: ErrorContext | None = None,
        severity: ErrorSeverity = ErrorSeverity.ERROR,
        **extra_kwargs,
    ):
        """Log an error."""
        self._log(
            str(error), severity.value, error=error, context=context, **extra_kwargs
        )

    def log_operation(
        self, operation: str, status: str, component: str, **extra_kwargs
    ):
        """Log an operation with status."""
        message = f"{operation} {status}"
        self._log(
            message,
            "INFO",
            operation=operation,
            status=status,
            component=component,
            **extra_kwargs,
        )

    def _log(self, message: str, level: str = "INFO", **extra_kwargs):
        """Internal log method."""
        # 直接使用 loguru 的 logger，保持与 main 模块相同的格式
        if level.upper() == "DEBUG":
            logger.debug(message)
        elif level.upper() == "INFO":
            logger.info(message)
        elif level.upper() == "WARNING":
            logger.warning(message)
        elif level.upper() == "ERROR":
            logger.error(message)
        elif level.upper() == "CRITICAL":
            logger.critical(message)
        else:
            logger.info(message)


def create_error_logger(component: str, operation: str, **kwargs):
    """Create a logger for a specific component and operation."""
    return ErrorLogger(component, operation, **kwargs)


class ErrorReporter:
    """Error reporting and aggregation."""

    def __init__(self):
        """Initialize error reporter."""
        self.error_counts: dict[str, int] = {}
        self.recent_errors: list[dict[str, Any]] = []
        self.max_recent_errors = 100

    def report_error(self, error: Exception, context: ErrorContext | None = None):
        """Report error."""
        error_type = type(error).__name__

        # Update counts
        self.error_counts[error_type] = self.error_counts.get(error_type, 0) + 1

        # Add to recent errors
        error_data = {
            "error_type": error_type,
            "message": str(error),
            "timestamp": datetime.now(UTC).isoformat(),
            "context": context.to_dict() if context else None,
        }

        self.recent_errors.append(error_data)
        if len(self.recent_errors) > self.max_recent_errors:
            self.recent_errors.pop(0)

        # Log error
        logger.error(error, context)

    def get_error_summary(self) -> dict[str, Any]:
        """Get error summary."""
        return {
            "total_errors": sum(self.error_counts.values()),
            "error_counts": self.error_counts,
            "recent_errors": self.recent_errors[-10:],  # Last 10 errors
            "error_rate": self._calculate_error_rate(),
        }

    def _calculate_error_rate(self) -> float:
        """Calculate error rate (errors per hour)."""
        if not self.recent_errors:
            return 0.0

        now = datetime.now(UTC)
        one_hour_ago = now.timestamp() - 3600

        recent_hour_errors = [
            e
            for e in self.recent_errors
            if datetime.fromisoformat(e["timestamp"]).timestamp() > one_hour_ago
        ]

        return len(recent_hour_errors) / 1.0  # errors per hour
