"""
Integration tests for configuration service integration with database.
"""

import pytest
import tempfile
import json
import os
from pathlib import Path

from hf_downloader.models.database import DatabaseManager
from hf_downloader.core.config import ConfigManager
from hf_downloader.services.configuration import ConfigurationService


class TestConfigurationIntegration:
    """Test integration between configuration service and database."""

    @pytest.fixture
    def temp_db_path(self):
        """Create temporary database file."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            yield f.name
        os.unlink(f.name)

    @pytest.fixture
    def temp_config_path(self):
        """Create temporary config file."""
        temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False)
        yaml_content = """
download_directory: ./test_models
log_level: DEBUG
max_retries: 3
timeout_seconds: 1800
concurrent_downloads: 2
"""
        temp_file.write(yaml_content)
        temp_file.flush()
        temp_file.close()
        yield temp_file.name
        os.unlink(temp_file.name)

    @pytest.fixture
    def config_service(self, temp_db_path, temp_config_path):
        """Create configuration service instance."""
        db_manager = DatabaseManager(temp_db_path)
        config_manager = ConfigManager(temp_config_path)
        service = ConfigurationService(db_manager, config_manager)
        yield service
        # Ensure database connections are closed
        db_manager.engine.dispose()

    def test_load_and_sync_config(self, config_service):
        """Test loading configuration and syncing with database."""
        config = config_service.load_and_sync_config()

        assert config.download_directory == "./test_models"
        assert config.log_level == "DEBUG"
        assert config.max_retries == 3
        assert config.timeout_seconds == 1800
        assert config.concurrent_downloads == 2

        # Verify database has configuration values
        db_config = config_service.get_config_from_database()
        assert db_config['download_directory'] == "./test_models"
        assert db_config['log_level'] == "DEBUG"
        assert db_config['max_retries'] == "3"

    def test_update_config_and_persist(self, config_service):
        """Test updating configuration and persisting to both file and database."""
        # Load initial config
        initial_config = config_service.load_and_sync_config()

        # Update configuration
        updates = {
            'log_level': 'INFO',
            'max_retries': 5,
            'timeout_seconds': 3600
        }
        updated_config = config_service.update_config_and_persist(updates)

        assert updated_config.log_level == "INFO"
        assert updated_config.max_retries == 5
        assert updated_config.timeout_seconds == 3600

        # Verify database was updated
        db_config = config_service.get_config_from_database()
        assert db_config['log_level'] == "INFO"
        assert db_config['max_retries'] == "5"
        assert db_config['timeout_seconds'] == "3600"

    def test_get_config_value_fallback_order(self, config_service):
        """Test configuration value retrieval with fallback order."""
        # Load initial config
        config_service.load_and_sync_config()

        # Get value that exists in memory
        assert config_service.get_config_value('log_level') == "DEBUG"

        # Get value that should be converted from database
        assert config_service.get_config_value('max_retries') == 3

        # Get value with default
        assert config_service.get_config_value('nonexistent_key', 'default') == "default"

    def test_export_import_config(self, config_service):
        """Test exporting and importing configuration."""
        # Load initial config
        config_service.load_and_sync_config()

        # Export as JSON
        json_export = config_service.export_config('json')
        exported_data = json.loads(json_export)
        assert exported_data['download_directory'] == "./test_models"
        assert exported_data['log_level'] == "DEBUG"

        # Modify and import
        exported_data['log_level'] = "WARNING"
        imported_config = config_service.import_config(json.dumps(exported_data), 'json')
        assert imported_config.log_level == "WARNING"

        # Verify database was updated
        db_config = config_service.get_config_from_database()
        assert db_config['log_level'] == "WARNING"

    def test_validate_config_integrity(self, config_service):
        """Test configuration integrity validation."""
        # Load initial config
        config_service.load_and_sync_config()

        # Should be consistent initially
        integrity = config_service.validate_config_integrity()
        assert integrity['is_consistent'] is True
        assert len(integrity['discrepancies']) == 0

        # Create discrepancy by updating database directly
        config_service.db_manager.set_system_config('log_level', 'ERROR')

        # Should detect discrepancy
        integrity = config_service.validate_config_integrity()
        assert integrity['is_consistent'] is False
        assert len(integrity['discrepancies']) == 1
        assert integrity['discrepancies'][0]['key'] == 'log_level'
        assert integrity['discrepancies'][0]['file_value'] == "DEBUG"
        assert integrity['discrepancies'][0]['database_value'] == "ERROR"

    def test_reset_config_to_defaults(self, config_service):
        """Test resetting configuration to defaults."""
        # Load and modify config
        config_service.load_and_sync_config()
        config_service.update_config_and_persist({
            'log_level': 'ERROR',
            'max_retries': 10
        })

        # Reset to defaults
        reset_config = config_service.reset_config_to_defaults()

        assert reset_config.log_level == "INFO"  # Default value
        assert reset_config.max_retries == 5  # Default value
        assert reset_config.download_directory == "./models"  # Default value

        # Verify database was updated
        db_config = config_service.get_config_from_database()
        assert db_config['log_level'] == "INFO"
        assert db_config['max_retries'] == "5"

    def test_get_config_summary(self, config_service):
        """Test configuration summary generation."""
        # Load config
        config_service.load_and_sync_config()

        # Get summary
        summary = config_service.get_config_summary()

        assert summary['log_level'] == "DEBUG"
        assert summary['download_directory'] == "./test_models"
        assert summary['max_concurrent_downloads'] == 2
        assert summary['total_config_keys'] > 0
        assert summary['database_config_keys'] > 0
        assert 'last_sync' in summary

    def test_config_value_type_conversion(self, config_service):
        """Test proper type conversion of configuration values."""
        # Load config
        config_service.load_and_sync_config()

        # Test integer conversion
        max_retries = config_service.get_config_value('max_retries')
        assert isinstance(max_retries, int)
        assert max_retries == 3

        # Test string value
        log_level = config_service.get_config_value('log_level')
        assert isinstance(log_level, str)
        assert log_level == "DEBUG"

    def test_database_persistence_after_service_restart(self, temp_db_path, temp_config_path):
        """Test that configuration persists in database after service restart."""
        # Create initial service and set config
        db_manager = DatabaseManager(temp_db_path)
        config_manager = ConfigManager(temp_config_path)
        service1 = ConfigurationService(db_manager, config_manager)

        service1.load_and_sync_config()
        service1.update_config_and_persist({
            'log_level': 'CRITICAL',
            'max_retries': 7
        })

        # Create new service instance with same database
        db_manager2 = DatabaseManager(temp_db_path)
        config_manager2 = ConfigManager(temp_config_path)
        service2 = ConfigurationService(db_manager2, config_manager2)

        # Should load persisted config from database
        config = service2.load_and_sync_config()
        assert config.log_level == "CRITICAL"
        assert config.max_retries == 7