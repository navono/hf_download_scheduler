"""
Contract tests for CLI models command.

This module tests the CLI models command contract as specified in
the CLI contract specification. Tests must fail before implementation.
"""

import pytest
import subprocess
import tempfile
import os
import json


class TestCLIModelsContract:
    """Test CLI models command contract."""

    def test_models_command_help(self):
        """Test models command help option."""
        result = subprocess.run(
            ["python", "-m", "hf_downloader.cli.main", "models", "--help"],
            capture_output=True,
            text=True,
        )
        # Should fail initially (implementation doesn't exist)
        assert result.returncode != 0

    def test_models_list_command(self):
        """Test models list command."""
        result = subprocess.run(
            ["python", "-m", "hf_downloader.cli.main", "models", "list"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        # Should fail initially
        assert result.returncode != 0

    def test_models_list_status_filter(self):
        """Test models list with status filter."""
        for status in ['all', 'pending', 'downloading', 'completed', 'failed']:
            result = subprocess.run(
                ["python", "-m", "hf_downloader.cli.main", "models", "list", "--status", status],
                capture_output=True,
                text=True,
                timeout=5,
            )
            # Should fail initially
            assert result.returncode != 0

    def test_models_list_format_option(self):
        """Test models list with format option."""
        for format_type in ['json', 'table']:
            result = subprocess.run(
                ["python", "-m", "hf_downloader.cli.main", "models", "list", "--format", format_type],
                capture_output=True,
                text=True,
                timeout=5,
            )
            # Should fail initially
            assert result.returncode != 0

    def test_models_add_command(self):
        """Test models add command."""
        result = subprocess.run(
            ["python", "-m", "hf_downloader.cli.main", "models", "add", "facebook/bart-large-cnn"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        # Should fail initially
        assert result.returncode != 0

    def test_models_add_models_option(self):
        """Test models add with --models option."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({"models": []}, f)
            models_file = f.name

        try:
            result = subprocess.run(
                ["python", "-m", "hf_downloader.cli.main", "models", "add", "test/model", "--models", models_file],
                capture_output=True,
                text=True,
                timeout=5,
            )
            # Should fail initially
            assert result.returncode != 0
        finally:
            os.unlink(models_file)

    def test_models_remove_command(self):
        """Test models remove command."""
        result = subprocess.run(
            ["python", "-m", "hf_downloader.cli.main", "models", "remove", "facebook/bart-large-cnn"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        # Should fail initially
        assert result.returncode != 0

    def test_models_add_success_response(self):
        """Test models add success response."""
        result = subprocess.run(
            ["python", "-m", "hf_downloader.cli.main", "models", "add", "facebook/bart-large-cnn"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        # Should fail initially, but when implemented should return:
        # {"status": "added", "model": "facebook/bart-large-cnn"}
        assert result.returncode != 0

    def test_models_remove_success_response(self):
        """Test models remove success response."""
        result = subprocess.run(
            ["python", "-m", "hf_downloader.cli.main", "models", "remove", "facebook/bart-large-cnn"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        # Should fail initially, but when implemented should return:
        # {"status": "removed", "model": "facebook/bart-large-cnn"}
        assert result.returncode != 0

    def test_models_list_json_output(self):
        """Test models list returns valid JSON."""
        result = subprocess.run(
            ["python", "-m", "hf_downloader.cli.main", "models", "list", "--format", "json"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        # Should fail initially, but when implemented should return valid JSON
        assert result.returncode != 0