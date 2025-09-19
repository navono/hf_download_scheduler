"""
Contract tests for CLI status command.

This module tests the CLI status command contract as specified in
the CLI contract specification. Tests must fail before implementation.
"""

import pytest
import subprocess
import tempfile
import os
import json


class TestCLIStatusContract:
    """Test CLI status command contract."""

    def test_status_command_help(self):
        """Test status command help option."""
        result = subprocess.run(
            ["python", "-m", "hf_downloader.cli.main", "status", "--help"],
            capture_output=True,
            text=True,
        )
        # Should fail initially (implementation doesn't exist)
        assert result.returncode != 0

    def test_status_command_pid_option(self):
        """Test status command --pid option."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.pid', delete=False) as f:
            pid_file = f.name

        try:
            result = subprocess.run(
                ["python", "-m", "hf_downloader.cli.main", "status", "--pid", pid_file],
                capture_output=True,
                text=True,
                timeout=5,
            )
            # Should fail initially
            assert result.returncode != 0
        finally:
            if os.path.exists(pid_file):
                os.unlink(pid_file)

    def test_status_command_not_running_response(self):
        """Test status command when not running."""
        result = subprocess.run(
            ["python", "-m", "hf_downloader.cli.main", "status"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        # Should fail initially, but when implemented should return:
        # {"status": "stopped"}
        assert result.returncode != 0

    def test_status_command_running_response(self):
        """Test status command when running."""
        # This would require a running process, but for now just test the command exists
        result = subprocess.run(
            ["python", "-m", "hf_downloader.cli.main", "status"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        # Should fail initially, but when implemented should return:
        # {"status": "running", "pid": 12345, "uptime": "2h 30m"}
        assert result.returncode != 0

    def test_status_command_json_output(self):
        """Test status command returns JSON output."""
        result = subprocess.run(
            ["python", "-m", "hf_downloader.cli.main", "status", "--format", "json"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        # Should fail initially
        assert result.returncode != 0

    def test_status_command_detailed_output(self):
        """Test status command detailed output."""
        result = subprocess.run(
            ["python", "-m", "hf_downloader.cli.main", "status", "--detailed"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        # Should fail initially
        assert result.returncode != 0

    def test_status_response_structure(self):
        """Test status response has correct structure."""
        result = subprocess.run(
            ["python", "-m", "hf_downloader.cli.main", "status"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        # Should fail initially, but when implemented should be valid JSON
        assert result.returncode != 0

    def test_status_config_option(self):
        """Test status command --config option."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("download_directory: ./models\nlog_level: INFO\n")
            config_file = f.name

        try:
            result = subprocess.run(
                ["python", "-m", "hf_downloader.cli.main", "status", "--config", config_file],
                capture_output=True,
                text=True,
                timeout=5,
            )
            # Should fail initially
            assert result.returncode != 0
        finally:
            os.unlink(config_file)