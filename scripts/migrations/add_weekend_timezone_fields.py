#!/usr/bin/env python3
"""
Database migration script to add weekend and timezone fields to schedule_configurations table.

This migration adds support for weekend downloads and UTC+8 timezone functionality.
"""

import sqlite3
from datetime import datetime
from pathlib import Path
from loguru import logger

def backup_database(db_path: str, backup_path: str):
    """Create a backup of the database before migration."""
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

def add_weekend_timezone_fields(conn: sqlite3.Connection):
    """Add weekend and timezone fields to schedule_configurations table."""

    # Check if columns already exist
    if check_column_exists(conn, 'schedule_configurations', 'time_window_timezone'):
        logger.info("Weekend and timezone fields already exist - skipping migration")
        return True

    try:
        cursor = conn.cursor()

        # Add timezone field
        logger.info("Adding time_window_timezone column...")
        cursor.execute("""
            ALTER TABLE schedule_configurations
            ADD COLUMN time_window_timezone VARCHAR(50) DEFAULT 'local'
        """)

        # Add weekend enabled field
        logger.info("Adding weekend_enabled column...")
        cursor.execute("""
            ALTER TABLE schedule_configurations
            ADD COLUMN weekend_enabled BOOLEAN DEFAULT FALSE
        """)

        # Add weekend days field (JSON array)
        logger.info("Adding weekend_days column...")
        cursor.execute("""
            ALTER TABLE schedule_configurations
            ADD COLUMN weekend_days TEXT
        """)

        # Note: Validation is handled at the application level in config.py
        # SQLite doesn't support complex triggers well, so we'll rely on app-level validation

        conn.commit()
        logger.info("Weekend and timezone fields added successfully")
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

    try:
        cursor = conn.cursor()

        # Check if columns exist
        columns_exist = all([
            check_column_exists(conn, 'schedule_configurations', 'time_window_timezone'),
            check_column_exists(conn, 'schedule_configurations', 'weekend_enabled'),
            check_column_exists(conn, 'schedule_configurations', 'weekend_days')
        ])

        if not columns_exist:
            logger.error("Migration verification failed: columns not found")
            return False

        # Check default values for existing records
        cursor.execute("""
            SELECT COUNT(*)
            FROM schedule_configurations
            WHERE time_window_timezone IS NULL
        """)
        null_timezone_count = cursor.fetchone()[0]

        if null_timezone_count > 0:
            logger.info(f"Found {null_timezone_count} records with NULL time_window_timezone, setting defaults...")
            cursor.execute("""
                UPDATE schedule_configurations
                SET time_window_timezone = 'local'
                WHERE time_window_timezone IS NULL
            """)

        cursor.execute("""
            SELECT COUNT(*)
            FROM schedule_configurations
            WHERE weekend_enabled IS NULL
        """)
        null_weekend_count = cursor.fetchone()[0]

        if null_weekend_count > 0:
            logger.info(f"Found {null_weekend_count} records with NULL weekend_enabled, setting defaults...")
            cursor.execute("""
                UPDATE schedule_configurations
                SET weekend_enabled = FALSE
                WHERE weekend_enabled IS NULL
            """)

        conn.commit()
        logger.info("Migration verification completed successfully")
        return True

    except Exception as e:
        logger.error(f"Error during migration verification: {e}")
        return False

def main():
    """Main migration function."""

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
        if not add_weekend_timezone_fields(conn):
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