"""
Database models and operations for HF Downloader.

This module contains the SQLAlchemy models and database operations
for managing models, schedules, downloads, and configuration.
"""

import json
import logging
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
    create_engine,
)
from sqlalchemy.orm import Session, declarative_base, relationship, sessionmaker

Base = declarative_base()


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
        self.logger = logging.getLogger(__name__)
        self._create_tables()
        logger.info("DatabaseManager initialized successfully")

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
                "pending": ["downloading"],
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
        """Get all models with specified status."""
        with self.get_session() as session:
            return session.query(Model).filter(Model.status == status).all()

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
    ) -> ScheduleConfiguration:
        """Create a new schedule configuration."""
        with self.get_session() as session:
            schedule = ScheduleConfiguration(
                name=name,
                type=type,
                time=time,
                day_of_week=day_of_week,
                max_concurrent_downloads=max_concurrent_downloads,
            )
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
