"""
Contract tests for CLI stop command.

This module tests the CLI stop command contract as specified in
the CLI contract specification. Tests must fail before implementation.
"""

import pytest
import subprocess
import tempfile
import os


class TestCLIStopContract:
    """Test CLI stop command contract."""

    def test_stop_command_help(self):
        """Test stop command help option."""
        result = subprocess.run(
            ["python", "-m", "hf_downloader.cli.main", "stop", "--help"],
            capture_output=True,
            text=True,
        )
        # Should fail initially (implementation doesn't exist)
        assert result.returncode != 0

    def test_stop_command_pid_option(self):
        """Test stop command --pid option."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.pid', delete=False) as f:
            pid_file = f.name

        try:
            result = subprocess.run(
                ["python", "-m", "hf_downloader.cli.main", "stop", "--pid", pid_file],
                capture_output=True,
                text=True,
                timeout=5,
            )
            # Should fail initially
            assert result.returncode != 0
        finally:
            if os.path.exists(pid_file):
                os.unlink(pid_file)

    def test_stop_command_not_running_error(self):
        """Test stop command returns error when not running."""
        result = subprocess.run(
            ["python", "-m", "hf_downloader.cli.main", "stop"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        # Should fail initially, but when implemented should return "not running" error
        assert result.returncode != 0

    def test_stop_command_success_response(self):
        """Test stop command success response format."""
        result = subprocess.run(
            ["python", "-m", "hf_downloader.cli.main", "stop"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        # Should fail initially, but when implemented should return:
        # {"status": "stopped"}
        assert result.returncode != 0

    def test_stop_command_json_output(self):
        """Test stop command returns JSON output."""
        result = subprocess.run(
            ["python", "-m", "hf_downloader.cli.main", "stop", "--format", "json"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        # Should fail initially
        assert result.returncode != 0

    def test_stop_command_config_option(self):
        """Test stop command --config option."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("download_directory: ./models\nlog_level: INFO\n")
            config_file = f.name

        try:
            result = subprocess.run(
                ["python", "-m", "hf_downloader.cli.main", "stop", "--config", config_file],
                capture_output=True,
                text=True,
                timeout=5,
            )
            # Should fail initially
            assert result.returncode != 0
        finally:
            os.unlink(config_file)