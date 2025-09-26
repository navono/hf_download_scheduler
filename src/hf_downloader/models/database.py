"""
Database models and operations for HF Downloader.

This module contains the SQLAlchemy models and database operations
for managing models, schedules, downloads, and configuration.
"""

import json
from datetime import UTC, datetime, timedelta
from typing import Any

from loguru import logger
from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    case,
    create_engine,
)
from sqlalchemy.orm import Session, declarative_base, relationship, sessionmaker

Base = declarative_base()


def get_priority_order(priority_str: str) -> int:
    """Convert priority string to numeric order for sorting."""
    priority_map = {
        "high": 1,
        "medium": 2,
        "low": 3,
    }
    return priority_map.get(priority_str.lower(), 2)  # Default to medium


class Model(Base):
    """Represents a Hugging Face model to be downloaded."""

    __tablename__ = "models"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False, unique=True)
    status = Column(String(20), nullable=False)
    size_bytes = Column(BigInteger, nullable=True)
    download_path = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
    model_metadata = Column(Text, nullable=True)  # JSON stored as text

    # Relationships
    download_sessions = relationship("DownloadSession", back_populates="model")

    def __repr__(self):
        return f"<Model(id={self.id}, name='{self.name}', status='{self.status}')>"

    def to_dict(self) -> dict[str, Any]:
        """Convert model to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "status": self.status,
            "size_bytes": self.size_bytes,
            "download_path": self.download_path,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "metadata": json.loads(self.model_metadata)
            if self.model_metadata
            else None,
        }

    def get_metadata(self) -> dict[str, Any]:
        """Get parsed metadata."""
        return json.loads(self.model_metadata) if self.model_metadata else {}

    def set_metadata(self, metadata: dict[str, Any]):
        """Set metadata from dictionary."""
        self.model_metadata = json.dumps(metadata)


class ScheduleConfiguration(Base):
    """Defines when downloads should occur."""

    __tablename__ = "schedule_configurations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    type = Column(String(20), nullable=False)
    time = Column(String(5), nullable=False)  # HH:MM format
    day_of_week = Column(Integer, nullable=True)
    enabled = Column(Boolean, default=True)
    max_concurrent_downloads = Column(Integer, default=1)

    # Time window fields for download scheduling restrictions
    time_window_enabled = Column(Boolean, default=False)
    time_window_start = Column(String(5), nullable=True)  # HH:MM format
    time_window_end = Column(String(5), nullable=True)  # HH:MM format
    time_window_timezone = Column(String(50), nullable=True, default="local")  # Timezone for time window
    weekend_enabled = Column(Boolean, default=False)  # Enable weekend downloads
    weekend_days = Column(Text, nullable=True)  # JSON array of weekend days

    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    # Relationships
    download_sessions = relationship("DownloadSession", back_populates="schedule")

    def __repr__(self):
        return f"<ScheduleConfiguration(id={self.id}, name='{self.name}', type='{self.type}')>"

    def to_dict(self) -> dict[str, Any]:
        """Convert schedule to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type,
            "time": self.time,
            "day_of_week": self.day_of_week,
            "enabled": self.enabled,
            "max_concurrent_downloads": self.max_concurrent_downloads,
            "time_window_enabled": self.time_window_enabled,
            "time_window_start": self.time_window_start,
            "time_window_end": self.time_window_end,
            "time_window_timezone": self.time_window_timezone,
            "weekend_enabled": self.weekend_enabled,
            "weekend_days": json.loads(self.weekend_days) if self.weekend_days else [],
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class DownloadSession(Base):
    """Tracks individual download attempts."""

    __tablename__ = "download_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    model_id = Column(Integer, ForeignKey("models.id"), nullable=False)
    schedule_id = Column(
        Integer, ForeignKey("schedule_configurations.id"), nullable=True
    )
    status = Column(String(20), nullable=False)
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    bytes_downloaded = Column(BigInteger, default=0)
    total_bytes = Column(BigInteger, nullable=True)
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0)
    model_metadata = Column(Text, nullable=True)  # JSON stored as text

    # Relationships
    model = relationship("Model", back_populates="download_sessions")
    schedule = relationship("ScheduleConfiguration", back_populates="download_sessions")

    def __repr__(self):
        return f"<DownloadSession(id={self.id}, status='{self.status}', model_id={self.model_id})>"

    def to_dict(self) -> dict[str, Any]:
        """Convert download session to dictionary."""
        return {
            "id": self.id,
            "model_id": self.model_id,
            "schedule_id": self.schedule_id,
            "status": self.status,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat()
            if self.completed_at
            else None,
            "bytes_downloaded": self.bytes_downloaded,
            "total_bytes": self.total_bytes,
            "error_message": self.error_message,
            "retry_count": self.retry_count,
            "metadata": json.loads(self.model_metadata)
            if self.model_metadata
            else None,
        }

    def get_metadata(self) -> dict[str, Any]:
        """Get parsed metadata."""
        return json.loads(self.model_metadata) if self.model_metadata else {}

    def set_metadata(self, metadata: dict[str, Any]):
        """Set metadata from dictionary."""
        self.model_metadata = json.dumps(metadata)


class SystemConfiguration(Base):
    """Global application settings."""

    __tablename__ = "system_configurations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String(100), nullable=False, unique=True)
    value = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    def __repr__(self):
        return f"<SystemConfiguration(key='{self.key}', value='{self.value}')>"

    def to_dict(self) -> dict[str, Any]:
        """Convert system configuration to dictionary."""
        return {
            "id": self.id,
            "key": self.key,
            "value": self.value,
            "description": self.description,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class SystemLog(Base):
    """System logs for monitoring and debugging."""

    __tablename__ = "system_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    log_type = Column(String(50), nullable=False)  # e.g., "error", "warning", "info"
    message = Column(Text, nullable=False)
    details = Column(Text, nullable=True)  # JSON stored as text
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))

    def __repr__(self):
        return f"<SystemLog(id={self.id}, type='{self.log_type}', created_at='{self.created_at}')>"

    def to_dict(self) -> dict[str, Any]:
        """Convert system log to dictionary."""
        return {
            "id": self.id,
            "log_type": self.log_type,
            "message": self.message,
            "details": json.loads(self.details) if self.details else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def get_details(self) -> dict[str, Any]:
        """Get parsed details."""
        return json.loads(self.details) if self.details else {}

    def set_details(self, details: dict[str, Any]):
        """Set details from dictionary."""
        self.details = json.dumps(details)


class DatabaseManager:
    """Database operations manager."""

    def __init__(self, db_path: str):
        """Initialize database manager with SQLite database path."""
        logger.info(f"Initializing DatabaseManager with database path: {db_path}")
        self.db_path = db_path
        self.engine = create_engine(f"sqlite:///{db_path}")
        self.SessionLocal = sessionmaker(
            autocommit=False, autoflush=False, bind=self.engine
        )
        self.logger = logger.bind(component="DatabaseManager")
        self._create_tables()
        logger.info("DatabaseManager initialized successfully")

    def _validate_time_format(self, time_str: str):
        """Validate time format is HH:MM."""
        if not time_str:
            return

        try:
            hours, minutes = time_str.split(":")
            hours = int(hours)
            minutes = int(minutes)

            if hours < 0 or hours > 23:
                raise ValueError(f"Hour must be between 00-23, got {hours}")
            if minutes < 0 or minutes > 59:
                raise ValueError(f"Minute must be between 00-59, got {minutes}")
        except ValueError as e:
            if "invalid literal" in str(e):
                raise ValueError(f"Invalid time format: {time_str}. Use HH:MM format")
            raise

    def _create_tables(self):
        """Create database tables."""
        Base.metadata.create_all(bind=self.engine)

    def get_session(self) -> Session:
        """Get database session."""
        return self.SessionLocal()

    # Model operations
    def create_model(
        self,
        name: str,
        size_bytes: int | None = None,
        metadata: dict[str, Any] | None = None,
        status: str = "pending",
    ) -> Model:
        """Create a new model record."""
        logger.info(f"Creating new model: {name} with status: {status}")
        with self.get_session() as session:
            model = Model(
                name=name,
                status=status,
                size_bytes=size_bytes,
                model_metadata=json.dumps(metadata) if metadata else None,
            )
            session.add(model)
            session.commit()
            session.refresh(model)
            logger.info(f"Successfully created model with ID: {model.id}")
            return model

    def get_model(self, model_id: int) -> Model | None:
        """Get model by ID."""
        with self.get_session() as session:
            return session.query(Model).filter(Model.id == model_id).first()

    def get_model_by_name(self, name: str) -> Model | None:
        """Get model by name."""
        with self.get_session() as session:
            return session.query(Model).filter(Model.name == name).first()

    def update_model_status(
        self, model_id: int, status: str, download_path: str | None = None
    ) -> bool:
        """Update model status and optionally download path."""
        logger.info(f"Updating model {model_id} status to: {status}")
        with self.get_session() as session:
            model = session.query(Model).filter(Model.id == model_id).first()
            if not model:
                logger.warning(f"Model with ID {model_id} not found")
                return False

            # Validate status transition
            valid_transitions = {
                "pending": ["downloading", "completed"],  # Allow direct -> completed for probing
                "downloading": ["completed", "failed"],
                "failed": ["pending"],  # retry
                "completed": [],  # terminal state
                "paused": ["downloading", "pending"],
            }

            current_status = model.status
            if status not in valid_transitions.get(current_status, []):
                logger.error(
                    f"Invalid status transition from {current_status} to {status}"
                )
                raise ValueError(
                    f"Invalid status transition from {current_status} to {status}"
                )

            model.status = status
            if download_path:
                model.download_path = download_path
            model.updated_at = datetime.now(UTC)

            session.commit()
            logger.info(f"Successfully updated model {model_id} status to {status}")
            return True

    def update_model(
        self, model_id: int, status: str | None = None, metadata: dict | None = None
    ) -> bool:
        """Update model status and metadata."""
        logger.info(
            f"Updating model {model_id} with status: {status}, metadata: {metadata}"
        )
        with self.get_session() as session:
            model = session.query(Model).filter(Model.id == model_id).first()
            if not model:
                logger.warning(f"Model with ID {model_id} not found")
                return False

            # Update status if provided
            if status is not None:
                # For model_sync.py, we allow direct status updates without transition validation
                # This is needed for synchronization between JSON and database
                model.status = status
                logger.info(f"Updated model {model_id} status to {status}")

            # Update metadata if provided
            if metadata is not None and isinstance(metadata, dict):
                # Get current metadata
                current_metadata = model.get_metadata()

                # Update metadata fields
                for key, value in metadata.items():
                    current_metadata[key] = value

                # Save updated metadata
                model.set_metadata(current_metadata)

                logger.info(f"Updated model {model_id} metadata")

            model.updated_at = datetime.now(UTC)
            session.commit()
            logger.info(f"Successfully updated model {model_id}")
            return True

    def get_models_by_status(self, status: str) -> list[Model]:
        """Get all models with specified status, ordered by priority."""
        with self.get_session() as session:
            # Create CASE expression for priority ordering
            priority_order = case(
                (Model.model_metadata.like('%"priority": "high"%'), 1),
                (Model.model_metadata.like('%"priority": "medium"%'), 2),
                (Model.model_metadata.like('%"priority": "low"%'), 3),
                else_=2  # Default to medium priority
            )

            return session.query(Model)\
                .filter(Model.status == status)\
                .order_by(priority_order, Model.created_at)\
                .all()

    def get_all_models(self) -> list[Model]:
        """Get all models from database."""
        with self.get_session() as session:
            return session.query(Model).all()

    # Schedule operations
    def create_schedule(
        self,
        name: str,
        type: str,
        time: str,
        day_of_week: int | None = None,
        max_concurrent_downloads: int = 1,
        time_window_enabled: bool = False,
        time_window_start: str | None = None,
        time_window_end: str | None = None,
    ) -> ScheduleConfiguration:
        """Create a new schedule configuration."""
        with self.get_session() as session:
            schedule = ScheduleConfiguration(
                name=name,
                type=type,
                time=time,
                day_of_week=day_of_week,
                max_concurrent_downloads=max_concurrent_downloads,
                time_window_enabled=time_window_enabled,
                time_window_start=time_window_start,
                time_window_end=time_window_end,
            )
            # Validate time window configuration
            if time_window_enabled:
                if not time_window_start or not time_window_end:
                    raise ValueError(
                        "Both time_window_start and time_window_end must be specified when time_window_enabled is True"
                    )
                self._validate_time_format(time_window_start)
                self._validate_time_format(time_window_end)

            session.add(schedule)
            session.commit()
            session.refresh(schedule)
            return schedule

    def get_active_schedule(self) -> ScheduleConfiguration | None:
        """Get the currently enabled schedule."""
        with self.get_session() as session:
            return (
                session.query(ScheduleConfiguration)
                .filter(ScheduleConfiguration.enabled)
                .first()
            )

    def enable_schedule(self, schedule_id: int) -> bool:
        """Enable a schedule and disable all others."""
        with self.get_session() as session:
            # Disable all schedules
            session.query(ScheduleConfiguration).update(
                {ScheduleConfiguration.enabled: False}
            )

            # Enable specified schedule
            schedule = (
                session.query(ScheduleConfiguration)
                .filter(ScheduleConfiguration.id == schedule_id)
                .first()
            )
            if schedule:
                schedule.enabled = True
                session.commit()
                return True
            return False

    def disable_schedule(self, schedule_id: int) -> bool:
        """Disable a specific schedule."""
        with self.get_session() as session:
            schedule = (
                session.query(ScheduleConfiguration)
                .filter(ScheduleConfiguration.id == schedule_id)
                .first()
            )
            if schedule:
                schedule.enabled = False
                session.commit()
                return True
            return False

    def get_all_schedules(self) -> list[ScheduleConfiguration]:
        """Get all schedule configurations."""
        with self.get_session() as session:
            return (
                session.query(ScheduleConfiguration)
                .order_by(ScheduleConfiguration.created_at.desc())
                .all()
            )

    def get_schedule(self, schedule_id: int) -> ScheduleConfiguration | None:
        """Get schedule by ID."""
        with self.get_session() as session:
            return (
                session.query(ScheduleConfiguration)
                .filter(ScheduleConfiguration.id == schedule_id)
                .first()
            )

    def update_schedule(
        self,
        schedule_id: int,
        name: str | None = None,
        type: str | None = None,
        time: str | None = None,
        day_of_week: int | None = None,
        max_concurrent_downloads: int | None = None,
        enabled: bool | None = None,
        time_window_enabled: bool | None = None,
        time_window_start: str | None = None,
        time_window_end: str | None = None,
    ) -> ScheduleConfiguration | None:
        """Update schedule configuration."""
        with self.get_session() as session:
            schedule = (
                session.query(ScheduleConfiguration)
                .filter(ScheduleConfiguration.id == schedule_id)
                .first()
            )
            if not schedule:
                return None

            if name is not None:
                schedule.name = name
            if type is not None:
                schedule.type = type
            if time is not None:
                schedule.time = time
            if day_of_week is not None:
                schedule.day_of_week = day_of_week
            if max_concurrent_downloads is not None:
                schedule.max_concurrent_downloads = max_concurrent_downloads
            if enabled is not None:
                schedule.enabled = enabled
            if time_window_enabled is not None:
                schedule.time_window_enabled = time_window_enabled
            if time_window_start is not None:
                schedule.time_window_start = time_window_start
            if time_window_end is not None:
                schedule.time_window_end = time_window_end

            # Validate time window configuration
            if schedule.time_window_enabled:
                if not schedule.time_window_start or not schedule.time_window_end:
                    raise ValueError(
                        "Both time_window_start and time_window_end must be specified when time_window_enabled is True"
                    )
                self._validate_time_format(schedule.time_window_start)
                self._validate_time_format(schedule.time_window_end)

            schedule.updated_at = datetime.now(UTC)
            session.commit()
            session.refresh(schedule)
            return schedule

    def delete_schedule(self, schedule_id: int) -> bool:
        """Delete a schedule configuration."""
        with self.get_session() as session:
            schedule = (
                session.query(ScheduleConfiguration)
                .filter(ScheduleConfiguration.id == schedule_id)
                .first()
            )
            if not schedule:
                return False

            # Check if this is the active schedule
            if schedule.enabled:
                # Find another schedule to enable if available
                other_schedules = (
                    session.query(ScheduleConfiguration)
                    .filter(ScheduleConfiguration.id != schedule_id)
                    .all()
                )
                if other_schedules:
                    # Enable the most recently created schedule
                    other_schedules[0].enabled = True

            session.delete(schedule)
            session.commit()
            return True

    def get_enabled_schedules(self) -> list[ScheduleConfiguration]:
        """Get all enabled schedules."""
        with self.get_session() as session:
            return (
                session.query(ScheduleConfiguration)
                .filter(ScheduleConfiguration.enabled)
                .all()
            )

    # Download session operations
    def create_download_session(
        self, model_id: int, schedule_id: int | None = None
    ) -> DownloadSession:
        """Create a new download session."""
        logger.info(
            f"Creating download session for model {model_id}, schedule {schedule_id}"
        )
        with self.get_session() as session:
            session_obj = DownloadSession(
                model_id=model_id, schedule_id=schedule_id, status="started"
            )
            session.add(session_obj)
            session.commit()
            session.refresh(session_obj)
            logger.info(f"Successfully created download session {session_obj.id}")
            return session_obj

    def update_download_session(
        self,
        session_id: int,
        status: str,
        bytes_downloaded: int | None = None,
        total_bytes: int | None = None,
        error_message: str | None = None,
    ) -> bool:
        """Update download session progress."""
        logger.info(f"Updating download session {session_id} to status: {status}")
        with self.get_session() as session:
            download_session = (
                session.query(DownloadSession)
                .filter(DownloadSession.id == session_id)
                .first()
            )
            if not download_session:
                logger.warning(f"Download session {session_id} not found")
                return False

            download_session.status = status
            if bytes_downloaded is not None:
                download_session.bytes_downloaded = bytes_downloaded
            if total_bytes is not None:
                download_session.total_bytes = total_bytes
            if error_message:
                download_session.error_message = error_message
                logger.error(f"Session {session_id} error: {error_message}")

            if status in ["completed", "failed", "cancelled"]:
                download_session.completed_at = datetime.now(UTC)

            session.commit()
            return True

    def get_download_history(
        self, model_id: int, limit: int = 10
    ) -> list[DownloadSession]:
        """Get download history for a model."""
        with self.get_session() as session:
            return (
                session.query(DownloadSession)
                .filter(DownloadSession.model_id == model_id)
                .order_by(DownloadSession.started_at.desc())
                .limit(limit)
                .all()
            )

    def get_download_session(self, session_id: int) -> DownloadSession | None:
        """Get a specific download session by ID."""
        with self.get_session() as session:
            return (
                session.query(DownloadSession)
                .filter(DownloadSession.id == session_id)
                .first()
            )

    def get_active_download_sessions(self) -> list[DownloadSession]:
        """Get all currently active download sessions."""
        with self.get_session() as session:
            return (
                session.query(DownloadSession)
                .filter(
                    DownloadSession.status.in_(["started", "in_progress", "paused"])
                )
                .all()
            )

    def get_sessions_by_status(self, status: str) -> list[DownloadSession]:
        """Get download sessions by status."""
        with self.get_session() as session:
            return (
                session.query(DownloadSession)
                .filter(DownloadSession.status == status)
                .order_by(DownloadSession.started_at.desc())
                .all()
            )

    def get_sessions_by_schedule(self, schedule_id: int) -> list[DownloadSession]:
        """Get all download sessions for a specific schedule."""
        with self.get_session() as session:
            return (
                session.query(DownloadSession)
                .filter(DownloadSession.schedule_id == schedule_id)
                .order_by(DownloadSession.started_at.desc())
                .all()
            )

    def get_session_statistics(
        self,
        model_id: int | None = None,
        schedule_id: int | None = None,
        time_range_days: int | None = None,
    ) -> dict[str, Any]:
        """Get download session statistics."""
        with self.get_session() as session:
            query = session.query(DownloadSession)

            # Apply filters
            if model_id:
                query = query.filter(DownloadSession.model_id == model_id)
            if schedule_id:
                query = query.filter(DownloadSession.schedule_id == schedule_id)
            if time_range_days:
                cutoff_date = datetime.now(UTC) - timedelta(days=time_range_days)
                query = query.filter(DownloadSession.started_at >= cutoff_date)

            sessions = query.all()

            # Calculate statistics
            total_sessions = len(sessions)
            completed_sessions = len([s for s in sessions if s.status == "completed"])
            failed_sessions = len([s for s in sessions if s.status == "failed"])
            cancelled_sessions = len([s for s in sessions if s.status == "cancelled"])
            active_sessions = len(
                [
                    s
                    for s in sessions
                    if s.status in ["started", "in_progress", "paused"]
                ]
            )

            # Calculate total bytes
            total_downloaded = sum(
                s.bytes_downloaded for s in sessions if s.bytes_downloaded
            )
            total_size = sum(s.total_bytes for s in sessions if s.total_bytes)

            # Calculate average download speed for completed sessions
            completed_with_time = [
                s
                for s in sessions
                if s.status == "completed"
                and s.started_at
                and s.completed_at
                and s.bytes_downloaded > 0
            ]

            avg_speed = 0
            if completed_with_time:
                speeds = []
                for s in completed_with_time:
                    duration = (s.completed_at - s.started_at).total_seconds()
                    if duration > 0:
                        speed = s.bytes_downloaded / duration  # bytes per second
                        speeds.append(speed)
                if speeds:
                    avg_speed = sum(speeds) / len(speeds)

            # Calculate success rate
            success_rate = (
                (completed_sessions / total_sessions * 100) if total_sessions > 0 else 0
            )

            return {
                "total_sessions": total_sessions,
                "completed_sessions": completed_sessions,
                "failed_sessions": failed_sessions,
                "cancelled_sessions": cancelled_sessions,
                "active_sessions": active_sessions,
                "success_rate": round(success_rate, 2),
                "total_bytes_downloaded": total_downloaded,
                "total_bytes_requested": total_size,
                "completion_rate": round((total_downloaded / total_size * 100), 2)
                if total_size > 0
                else 0,
                "average_download_speed_bps": round(avg_speed, 2),
                "average_download_speed_mbps": round(avg_speed / (1024 * 1024), 2)
                if avg_speed > 0
                else 0,
            }

    def cleanup_old_sessions(self, days_to_keep: int = 30) -> dict[str, Any]:
        """Clean up old download sessions."""
        try:
            cutoff_date = datetime.now(UTC) - timedelta(days=days_to_keep)

            with self.get_session() as session:
                # Count sessions to be deleted
                old_sessions = (
                    session.query(DownloadSession)
                    .filter(DownloadSession.started_at < cutoff_date)
                    .filter(
                        DownloadSession.status.in_(["completed", "failed", "cancelled"])
                    )
                    .all()
                )

                deleted_count = len(old_sessions)

                # Delete old sessions
                for old_session in old_sessions:
                    session.delete(old_session)

                session.commit()

                self.logger.info(f"Cleaned up {deleted_count} old download sessions")

                return {
                    "status": "success",
                    "deleted_count": deleted_count,
                    "cutoff_date": cutoff_date.isoformat(),
                    "days_kept": days_to_keep,
                }

        except Exception as e:
            self.logger.error(f"Error cleaning up old sessions: {e}")
            return {"status": "error", "error": str(e), "deleted_count": 0}

    def retry_failed_session(
        self, session_id: int, new_schedule_id: int | None = None
    ) -> DownloadSession | None:
        """Create a new session to retry a failed download."""
        try:
            with self.get_session() as session:
                # Get the original failed session
                failed_session = (
                    session.query(DownloadSession)
                    .filter(DownloadSession.id == session_id)
                    .first()
                )

                if not failed_session or failed_session.status != "failed":
                    return None

                # Create new session with incremented retry count
                new_session = DownloadSession(
                    model_id=failed_session.model_id,
                    schedule_id=new_schedule_id or failed_session.schedule_id,
                    status="started",
                    retry_count=failed_session.retry_count + 1,
                    total_bytes=failed_session.total_bytes,
                )

                # Copy metadata if it exists
                if failed_session.model_metadata:
                    new_session.model_metadata = failed_session.model_metadata

                session.add(new_session)
                session.commit()
                session.refresh(new_session)

                self.logger.info(
                    f"Created retry session {new_session.id} for failed session {session_id}"
                )

                return new_session

        except Exception as e:
            self.logger.error(f"Error creating retry session: {e}")
            return None

    # Time window operations
    def get_schedules_with_time_window(
        self, enabled_only: bool = True
    ) -> list[ScheduleConfiguration]:
        """Get schedules that have time window enabled."""
        with self.get_session() as session:
            query = session.query(ScheduleConfiguration)
            if enabled_only:
                query = query.filter(ScheduleConfiguration.enabled)
            return query.filter(ScheduleConfiguration.time_window_enabled).all()

    def get_schedules_in_time_window(self) -> list[ScheduleConfiguration]:
        """Get schedules that are currently in their time window."""
        from ..services.time_window import TimeWindow

        schedules_in_window = []

        with self.get_session() as session:
            schedules = (
                session.query(ScheduleConfiguration)
                .filter(
                    ScheduleConfiguration.enabled,
                    ScheduleConfiguration.time_window_enabled,
                )
                .all()
            )

            for schedule in schedules:
                if schedule.time_window_start and schedule.time_window_end:
                    time_window = TimeWindow(
                        schedule.time_window_start,
                        schedule.time_window_end,
                        enabled=True,
                    )
                    if time_window.is_current_time_in_window():
                        schedules_in_window.append(schedule)

        return schedules_in_window

    def get_time_window_status(self, schedule_id: int) -> dict[str, Any]:
        """Get time window status for a specific schedule."""
        from ..services.time_window import TimeWindow

        with self.get_session() as session:
            schedule = (
                session.query(ScheduleConfiguration)
                .filter(ScheduleConfiguration.id == schedule_id)
                .first()
            )

            if not schedule:
                return {"error": "Schedule not found"}

            if not schedule.time_window_enabled:
                return {
                    "enabled": False,
                    "message": "Time window is disabled for this schedule",
                }

            if not schedule.time_window_start or not schedule.time_window_end:
                return {
                    "enabled": False,
                    "message": "Time window configuration is incomplete",
                }

            time_window = TimeWindow(
                schedule.time_window_start, schedule.time_window_end, enabled=True
            )

            return {
                "enabled": True,
                "start_time": schedule.time_window_start,
                "end_time": schedule.time_window_end,
                "is_currently_active": time_window.is_current_time_in_window(),
                "next_window_start": time_window.get_next_window_start().isoformat(),
                "current_window_end": time_window.get_window_end().isoformat()
                if time_window.get_window_end()
                else None,
                "crosses_midnight": time_window._crosses_midnight(),
                "duration_minutes": time_window.get_window_duration_minutes(),
            }

    # System configuration operations
    def get_system_config(self, key: str, default: str | None = None) -> str | None:
        """Get system configuration value."""
        with self.get_session() as session:
            config = (
                session.query(SystemConfiguration)
                .filter(SystemConfiguration.key == key)
                .first()
            )
            return config.value if config else default

    def set_system_config(
        self, key: str, value: str, description: str | None = None
    ) -> bool:
        """Set system configuration value."""
        with self.get_session() as session:
            config = (
                session.query(SystemConfiguration)
                .filter(SystemConfiguration.key == key)
                .first()
            )
            if config:
                config.value = value
                config.updated_at = datetime.now(UTC)
            else:
                config = SystemConfiguration(
                    key=key, value=value, description=description
                )
                session.add(config)
            session.commit()
            return True

    def initialize_default_config(self):
        """Initialize default system configuration."""
        defaults = [
            ("download_directory", "./models", "Directory for downloaded models"),
            ("log_level", "INFO", "Logging level"),
            ("max_retries", "5", "Maximum number of download retries"),
            ("timeout_seconds", "3600", "Download timeout in seconds"),
        ]

        for key, value, description in defaults:
            self.set_system_config(key, value, description)

    def get_database_stats(self) -> dict[str, Any]:
        """Get database statistics."""
        try:
            with self.get_session() as session:
                # Count models by status
                model_stats = {}
                for status in ["pending", "downloading", "completed", "failed"]:
                    count = session.query(Model).filter(Model.status == status).count()
                    model_stats[status] = count

                # Count schedules
                schedule_count = session.query(ScheduleConfiguration).count()

                # Count download sessions
                session_count = session.query(DownloadSession).count()

                # Get system configuration
                sys_config = session.query(SystemConfiguration).first()

                return {
                    "models": model_stats,
                    "total_models": sum(model_stats.values()),
                    "schedules": schedule_count,
                    "download_sessions": session_count,
                    "system_config": sys_config.to_dict() if sys_config else None,
                }
        except Exception as e:
            self.logger.error(f"Error getting database stats: {e}")
            return {"error": str(e)}

    def add_system_log(
        self, log_type: str, message: str, details: dict[str, Any] | None = None
    ) -> SystemLog:
        """Add a system log entry."""
        try:
            with self.get_session() as session:
                log_entry = SystemLog(
                    log_type=log_type,
                    message=message,
                    details=json.dumps(details) if details else None,
                )
                session.add(log_entry)
                session.commit()
                session.refresh(log_entry)

                logger.info(f"Added system log: {log_type} - {message}")
                return log_entry

        except Exception as e:
            logger.error(f"Error adding system log: {e}")
            # Return a dummy log entry since we couldn't save to the database
            return SystemLog(
                id=-1,
                log_type=log_type,
                message=message,
                details=json.dumps({"error": str(e), **details})
                if details
                else json.dumps({"error": str(e)}),
            )

    def get_recent_system_logs(
        self, limit: int = 100, log_type: str | None = None
    ) -> list[SystemLog]:
        """Get recent system logs."""
        try:
            with self.get_session() as session:
                query = session.query(SystemLog)

                if log_type:
                    query = query.filter(SystemLog.log_type == log_type)

                logs = query.order_by(SystemLog.created_at.desc()).limit(limit).all()
                return logs

        except Exception as e:
            logger.error(f"Error getting system logs: {e}")
            return []
