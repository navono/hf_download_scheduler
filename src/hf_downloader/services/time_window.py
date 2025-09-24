"""
Time window utility for download scheduling.

This module provides functionality to validate and check time-based download windows,
including support for midnight crossing and timezone handling.
"""

from dataclasses import dataclass
from datetime import datetime, time, timedelta

from loguru import logger


@dataclass
class TimeWindow:
    """Represents a time window for download scheduling."""

    start_time: str  # HH:MM format
    end_time: str  # HH:MM format
    enabled: bool = False

    def __post_init__(self):
        """Validate time format after initialization."""
        if self.enabled:
            self._validate_time_format(self.start_time)
            self._validate_time_format(self.end_time)

    def _validate_time_format(self, time_str: str):
        """Validate time format is HH:MM."""
        if not time_str:
            raise ValueError("Time string cannot be empty")

        try:
            hours, minutes = time_str.split(":")
            hours = int(hours)
            minutes = int(minutes)

            if hours < 0 or hours > 23:
                raise ValueError(f"Hour must be between 00-23, got {hours}")
            if minutes < 0 or minutes > 59:
                raise ValueError(f"Minute must be between 00-59, got {minutes}")
        except ValueError as e:
            if "invalid literal" in str(e) or "not enough values" in str(e):
                raise ValueError(f"Invalid time format: {time_str}. Use HH:MM format")
            raise

    def _parse_time(self, time_str: str) -> time:
        """Parse HH:MM string to time object."""
        hours, minutes = time_str.split(":")
        return time(int(hours), int(minutes))

    def _time_to_minutes(self, time_str: str) -> int:
        """Convert HH:MM to minutes since midnight."""
        hours, minutes = time_str.split(":")
        return int(hours) * 60 + int(minutes)

    def _get_current_time_minutes(self) -> int:
        """Get current time as minutes since midnight."""
        now = datetime.now()
        return now.hour * 60 + now.minute

    def _crosses_midnight(self) -> bool:
        """Check if the time window crosses midnight."""
        start_minutes = self._time_to_minutes(self.start_time)
        end_minutes = self._time_to_minutes(self.end_time)
        return end_minutes < start_minutes

    def is_current_time_in_window(self) -> bool:
        """
        Check if current time is within the time window.

        Returns:
            bool: True if current time is within the window, False otherwise
        """
        if not self.enabled:
            return True  # No time restriction

        current_minutes = self._get_current_time_minutes()
        start_minutes = self._time_to_minutes(self.start_time)
        end_minutes = self._time_to_minutes(self.end_time)

        if self._crosses_midnight():
            # Window crosses midnight (e.g., 22:00 to 07:00)
            # Current time is in window if it's >= start OR < end (end time is exclusive)
            result = current_minutes >= start_minutes or current_minutes < end_minutes
        else:
            # Normal window (e.g., 09:00 to 17:00)
            # Current time is in window if it's between start and end
            result = start_minutes <= current_minutes <= end_minutes

        logger.debug(
            f"Time window check: current={current_minutes // 60:02d}:{current_minutes % 60:02d}, "
            f"window={self.start_time}-{self.end_time}, crosses_midnight={self._crosses_midnight()}, "
            f"result={result}"
        )

        return result

    def get_next_window_start(self) -> datetime:
        """
        Calculate when the next time window starts.

        Returns:
            datetime: Next window start time
        """
        if not self.enabled:
            return datetime.now()

        now = datetime.now()
        current_time = now.time()
        start_time = self._parse_time(self.start_time)
        end_time = self._parse_time(self.end_time)

        # Combine current date with window times
        today_start = datetime.combine(now.date(), start_time)
        # today_end = datetime.combine(now.date(), end_time)

        if self._crosses_midnight():
            # For midnight-crossing windows, check if we're after yesterday's start
            if current_time >= start_time:
                # We're in today's window, next start is tomorrow
                next_start = today_start + timedelta(days=1)
            else:
                # We're before today's start, check if we're in the window
                if current_time <= end_time:
                    # We're in today's window (from yesterday), next start is today
                    next_start = today_start
                else:
                    # We're between windows, next start is today
                    next_start = today_start
        else:
            # Normal window, check if we're before or after today's start
            if current_time < start_time:
                # Before today's start
                next_start = today_start
            else:
                # After today's start, next start is tomorrow
                next_start = today_start + timedelta(days=1)

        logger.debug(f"Next window start calculated: {next_start}")
        return next_start

    def get_window_end(self) -> datetime | None:
        """
        Calculate when the current time window ends.

        Returns:
            Optional[datetime]: Current window end time, or None if no active window
        """
        if not self.enabled:
            return None

        now = datetime.now()
        current_time = now.time()
        start_time = self._parse_time(self.start_time)
        end_time = self._parse_time(self.end_time)

        # Combine current date with window times
        # today_start = datetime.combine(now.date(), start_time)
        today_end = datetime.combine(now.date(), end_time)

        if self._crosses_midnight():
            if current_time >= start_time:
                # We're in today's window, end is tomorrow
                window_end = today_end + timedelta(days=1)
            elif current_time <= end_time:
                # We're in today's window (from yesterday), end is today
                window_end = today_end
            else:
                # We're between windows
                return None
        else:
            if start_time <= current_time <= end_time:
                # We're in today's window
                window_end = today_end
            else:
                # We're outside the window
                return None

        logger.debug(f"Current window end calculated: {window_end}")
        return window_end

    def get_window_duration_minutes(self) -> int:
        """
        Calculate the duration of the time window in minutes.

        Returns:
            int: Duration in minutes
        """
        if not self.enabled:
            return 0

        start_minutes = self._time_to_minutes(self.start_time)
        end_minutes = self._time_to_minutes(self.end_time)

        if self._crosses_midnight():
            # Window crosses midnight, calculate duration accordingly
            duration = (24 * 60 - start_minutes) + end_minutes
        else:
            # Normal window
            duration = end_minutes - start_minutes

        return max(0, duration)

    def to_dict(self) -> dict:
        """Convert TimeWindow to dictionary."""
        return {
            "start_time": self.start_time,
            "end_time": self.end_time,
            "enabled": self.enabled,
            "crosses_midnight": self._crosses_midnight(),
            "duration_minutes": self.get_window_duration_minutes(),
            "is_currently_active": self.is_current_time_in_window(),
            "next_window_start": self.get_next_window_start().isoformat()
            if self.enabled
            else None,
            "current_window_end": self.get_window_end().isoformat()
            if self.enabled and self.is_current_time_in_window()
            else None,
        }

    def validate(self) -> tuple[bool, list[str]]:
        """
        Validate the time window configuration.

        Returns:
            Tuple[bool, list[str]]: (is_valid, list_of_errors)
        """
        errors = []

        if not self.enabled:
            return True, errors

        try:
            self._validate_time_format(self.start_time)
            self._validate_time_format(self.end_time)
        except ValueError as e:
            errors.append(str(e))
            return False, errors

        # Check if window has positive duration
        duration = self.get_window_duration_minutes()
        if duration == 0:
            errors.append("Time window must have positive duration")
        elif duration < 0:
            errors.append("Time window duration calculation error")

        return len(errors) == 0, errors


class TimeWindowController:
    """Controller for managing time window operations."""

    def __init__(self):
        """Initialize TimeWindowController."""
        self.logger = logger.bind(component="TimeWindowController")

    def create_time_window(
        self, start_time: str, end_time: str, enabled: bool = True
    ) -> TimeWindow:
        """
        Create a new TimeWindow instance with validation.

        Args:
            start_time: Start time in HH:MM format
            end_time: End time in HH:MM format
            enabled: Whether the time window is enabled

        Returns:
            TimeWindow: Created time window instance

        Raises:
            ValueError: If time format is invalid or window is invalid
        """
        time_window = TimeWindow(
            start_time=start_time, end_time=end_time, enabled=enabled
        )

        is_valid, errors = time_window.validate()
        if not is_valid:
            error_msg = "; ".join(errors)
            self.logger.error(f"Invalid time window configuration: {error_msg}")
            raise ValueError(f"Invalid time window: {error_msg}")

        self.logger.info(
            f"Created time window: {start_time}-{end_time} (enabled={enabled})"
        )
        return time_window

    def validate_time_format(self, start_time: str, end_time: str) -> dict:
        """
        Validate time format without creating a TimeWindow instance.

        Args:
            start_time: Start time in HH:MM format
            end_time: End time in HH:MM format

        Returns:
            dict: Validation result with validity, errors, and metadata
        """
        try:
            temp_window = TimeWindow(
                start_time=start_time, end_time=end_time, enabled=True
            )
            is_valid, errors = temp_window.validate()

            return {
                "valid": is_valid,
                "errors": errors,
                "crosses_midnight": temp_window._crosses_midnight(),
                "duration_minutes": temp_window.get_window_duration_minutes(),
                "warnings": []
                if is_valid
                else ["Time window configuration has issues"],
            }
        except Exception as e:
            return {
                "valid": False,
                "errors": [str(e)],
                "crosses_midnight": False,
                "duration_minutes": 0,
                "warnings": ["Unexpected validation error"],
            }
