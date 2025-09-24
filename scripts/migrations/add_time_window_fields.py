#!/usr/bin/env python3
"""
Database migration script to add time window fields to schedule_configurations table.

This migration adds support for time-based download scheduling restrictions.
"""

import logging
import sqlite3
from datetime import datetime
from pathlib import Path

def setup_logging():
    """Set up logging for the migration."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    return logging.getLogger(__name__)

def backup_database(db_path: str, backup_path: str):
    """Create a backup of the database before migration."""
    logger = logging.getLogger(__name__)
    try:
        import shutil
        shutil.copy2(db_path, backup_path)
        logger.info(f"Database backed up to: {backup_path}")
        return True
    except Exception as e:
        logger.error(f"Failed to backup database: {e}")
        return False

def check_column_exists(conn: sqlite3.Connection, table_name: str, column_name: str) -> bool:
    """Check if a column exists in a table."""
    cursor = conn.cursor()
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = [row[1] for row in cursor.fetchall()]
    return column_name in columns

def add_time_window_fields(conn: sqlite3.Connection):
    """Add time window fields to schedule_configurations table."""
    logger = logging.getLogger(__name__)

    # Check if columns already exist
    if check_column_exists(conn, 'schedule_configurations', 'time_window_enabled'):
        logger.info("Time window fields already exist - skipping migration")
        return True

    try:
        cursor = conn.cursor()

        # Add time window fields
        logger.info("Adding time_window_enabled column...")
        cursor.execute("""
            ALTER TABLE schedule_configurations
            ADD COLUMN time_window_enabled BOOLEAN DEFAULT FALSE
        """)

        logger.info("Adding time_window_start column...")
        cursor.execute("""
            ALTER TABLE schedule_configurations
            ADD COLUMN time_window_start VARCHAR(5)
        """)

        logger.info("Adding time_window_end column...")
        cursor.execute("""
            ALTER TABLE schedule_configurations
            ADD COLUMN time_window_end VARCHAR(5)
        """)

        # Add check constraint for time format (HH:MM)
        logger.info("Adding time format validation constraints...")
        cursor.execute("""
            CREATE TRIGGER validate_time_window_start
            BEFORE INSERT OR UPDATE ON schedule_configurations
            FOR EACH ROW
            BEGIN
                WHEN NEW.time_window_start IS NOT NULL AND
                     NEW.time_window_start NOT GLOB '[0-2][0-9]:[0-5][0-9]'
                BEGIN
                    SELECT RAISE(ABORT, 'Invalid time_window_start format. Use HH:MM format (00:00-23:59)')
                END;
            END;
        """)

        cursor.execute("""
            CREATE TRIGGER validate_time_window_end
            BEFORE INSERT OR UPDATE ON schedule_configurations
            FOR EACH ROW
            BEGIN
                WHEN NEW.time_window_end IS NOT NULL AND
                     NEW.time_window_end NOT GLOB '[0-2][0-9]:[0-5][0-9]'
                BEGIN
                    SELECT RAISE(ABORT, 'Invalid time_window_end format. Use HH:MM format (00:00-23:59)')
                END;
            END;
        """)

        # Add constraint to ensure both time fields are set when enabled
        cursor.execute("""
            CREATE TRIGGER validate_time_window_consistency
            BEFORE INSERT OR UPDATE ON schedule_configurations
            FOR EACH ROW
            BEGIN
                WHEN NEW.time_window_enabled = TRUE AND
                     (NEW.time_window_start IS NULL OR NEW.time_window_end IS NULL)
                BEGIN
                    SELECT RAISE(ABORT, 'Both time_window_start and time_window_end must be specified when time_window_enabled is TRUE')
                END;
            END;
        """)

        conn.commit()
        logger.info("Time window fields added successfully")
        return True

    except sqlite3.Error as e:
        logger.error(f"Database error during migration: {e}")
        conn.rollback()
        return False
    except Exception as e:
        logger.error(f"Unexpected error during migration: {e}")
        conn.rollback()
        return False

def verify_migration(conn: sqlite3.Connection):
    """Verify that the migration was successful."""
    logger = logging.getLogger(__name__)

    try:
        cursor = conn.cursor()

        # Check if columns exist
        columns_exist = all([
            check_column_exists(conn, 'schedule_configurations', 'time_window_enabled'),
            check_column_exists(conn, 'schedule_configurations', 'time_window_start'),
            check_column_exists(conn, 'schedule_configurations', 'time_window_end')
        ])

        if not columns_exist:
            logger.error("Migration verification failed: columns not found")
            return False

        # Check default values for existing records
        cursor.execute("""
            SELECT COUNT(*)
            FROM schedule_configurations
            WHERE time_window_enabled IS NULL
        """)
        null_enabled_count = cursor.fetchone()[0]

        if null_enabled_count > 0:
            logger.warning(f"Found {null_enabled_count} records with NULL time_window_enabled")
            # Fix NULL values
            cursor.execute("""
                UPDATE schedule_configurations
                SET time_window_enabled = FALSE
                WHERE time_window_enabled IS NULL
            """)
            conn.commit()
            logger.info("Fixed NULL time_window_enabled values")

        logger.info("Migration verification completed successfully")
        return True

    except Exception as e:
        logger.error(f"Error during migration verification: {e}")
        return False

def main():
    """Main migration function."""
    logger = setup_logging()

    # Database path
    db_path = "./hf_downloader.db"

    if not Path(db_path).exists():
        logger.error(f"Database not found at {db_path}")
        return 1

    logger.info(f"Starting migration for database: {db_path}")

    # Create backup
    backup_path = f"./hf_downloader.db.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    if not backup_database(db_path, backup_path):
        logger.error("Migration aborted: failed to create backup")
        return 1

    # Connect to database
    try:
        conn = sqlite3.connect(db_path)
        conn.execute("PRAGMA foreign_keys = ON")

        # Run migration
        if not add_time_window_fields(conn):
            logger.error("Migration failed")
            return 1

        # Verify migration
        if not verify_migration(conn):
            logger.error("Migration verification failed")
            return 1

        conn.close()
        logger.info("Migration completed successfully")
        logger.info(f"Database backup saved to: {backup_path}")
        return 0

    except Exception as e:
        logger.error(f"Migration failed with error: {e}")
        return 1

if __name__ == "__main__":
    exit(main())