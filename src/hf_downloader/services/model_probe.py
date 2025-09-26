"""
Model probe service for HF Downloader.

This module provides functionality to probe model download status by quickly
checking if models are already downloaded locally or available remotely.
"""

import os
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

from huggingface_hub import HfApi
from huggingface_hub.utils import RepositoryNotFoundError
from loguru import logger


class ModelProbeResult:
    """Result of model probe operation."""

    def __init__(self, status: str, message: str = "", details: dict[str, Any] = None):
        self.status = status  # "exists_locally", "remote_exists", "not_found", "network_error", "timeout"
        self.message = message
        self.details = details or {}

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "status": self.status,
            "message": self.message,
            "details": self.details
        }


class ModelProbeService:
    """Service for probing model download status."""

    def __init__(self, download_directory: str = None, timeout: int = 5):
        """Initialize model probe service."""
        # Try to find the Hugging Face cache directory
        if download_directory:
            self.download_directory = download_directory
        else:
            # Check multiple possible locations for HF cache
            possible_dirs = [
                os.getenv("HF_HOME"),
                os.path.expanduser("~/.cache/huggingface"),
                "/mnt/f/data/HF_models",  # Common mount point
                "/data/HF_models",        # Alternative common location
            ]

            self.download_directory = None
            for dir_path in possible_dirs:
                if dir_path and os.path.exists(dir_path):
                    # Check if this looks like a HF cache directory
                    if os.path.exists(os.path.join(dir_path, "hub")):
                        self.download_directory = dir_path
                        break

            # Default fallback
            if not self.download_directory:
                self.download_directory = os.getenv("HF_HOME", os.path.expanduser("~/.cache/huggingface"))

        self.timeout = timeout
        self.api = HfApi()
        logger.info(f"ModelProbeService initialized with download directory: {self.download_directory}")

    def probe_model(self, model_name: str, timeout: int = None) -> ModelProbeResult:
        """
        Probe a single model to determine its download status.

        Args:
            model_name: Name of the model to probe
            timeout: Probe timeout in seconds (overrides default)

        Returns:
            ModelProbeResult with status and details
        """
        timeout = timeout or self.timeout
        logger.debug(f"Probing model: {model_name} (timeout: {timeout}s)")

        try:
            # Step 1: Perform download test (most accurate)
            download_test_result = self._test_download_completion(model_name, min(timeout, 10))
            if download_test_result is not None:
                if download_test_result.status == "exists_locally":
                    logger.info(f"Model {model_name} is fully downloaded (verified by download test)")
                    return download_test_result
                elif download_test_result.status in ["timeout", "not_found"]:
                    logger.debug(f"Download test incomplete for {model_name}, falling back to path check")

            # Step 2: Fallback to basic path check
            local_result = self._check_local_model(model_name)
            if local_result.status == "exists_locally":
                # If download test was performed but indicated issues, prioritize that result
                if download_test_result:
                    if download_test_result.status == "not_found":
                        logger.info(f"Model {model_name} path exists but download test indicates incomplete")
                        return ModelProbeResult("not_found", "Model path exists but appears incomplete", {
                            "local_path": local_result.details.get("local_path"),
                            "issue": "incomplete_download",
                            "download_test_result": download_test_result.details
                        })
                    elif download_test_result.status == "timeout":
                        logger.info(f"Model {model_name} path exists but download test timed out - likely incomplete")
                        return ModelProbeResult("not_found", "Model path exists but download test timed out", {
                            "local_path": local_result.details.get("local_path"),
                            "issue": "download_test_timeout",
                            "download_test_result": download_test_result.details
                        })

                logger.info(f"Model {model_name} exists locally (path check only)")
                return local_result

            # Step 3: Quick remote check
            remote_result = self._check_remote_model(model_name, timeout)
            if remote_result.status == "remote_exists":
                logger.info(f"Model {model_name} exists remotely and needs download")
            elif remote_result.status == "not_found":
                logger.warning(f"Model {model_name} not found on Hugging Face")
            elif remote_result.status == "timeout":
                logger.info(f"Model {model_name} probe timed out (might be large model)")

            return remote_result

        except Exception as e:
            logger.error(f"Unexpected error probing model {model_name}: {e}")
            return ModelProbeResult("network_error", f"Probe failed: {str(e)}")

    def _check_local_model(self, model_name: str) -> ModelProbeResult:
        """Check if model exists locally in download directory."""
        try:
            # Hugging Face Hub uses different path structure
            # model/name --> hub/models--model--name/snapshots/{hash}
            safe_model_name = model_name.replace("/", "--")
            hub_model_name = f"models--{safe_model_name}"  # Full HF Hub format

            # Check multiple possible locations
            possible_paths = [
                Path(self.download_directory) / "models" / safe_model_name,      # Legacy path
                Path(self.download_directory) / "hub" / hub_model_name,          # New hub path with models-- prefix
                Path(self.download_directory) / "hub" / safe_model_name,        # Hub path without models-- prefix
            ]

            # Also check if the download_directory itself is the hub directory
            if self.download_directory.endswith("hub"):
                possible_paths.extend([
                    Path(self.download_directory) / hub_model_name,
                    Path(self.download_directory) / safe_model_name,
                ])

            model_path = None
            for path in possible_paths:
                logger.debug(f"Checking path: {path}")
                if path.exists():
                    model_path = path
                    logger.debug(f"Found model at: {path}")
                    break

            if not model_path:
                logger.debug("Local model path does not exist in any expected location")
                logger.debug(f"Checked paths: {[str(p) for p in possible_paths]}")
                return ModelProbeResult("not_found", "Model not found locally")

            # Check for essential model files in snapshots directory (HF Hub structure)
            essential_files = ["config.json", "model.safetensors", "pytorch_model.bin"]
            found_files = []
            total_size = 0
            snapshot_dirs = []

            # Look for snapshots directory (HF Hub structure)
            if model_path.name.startswith("models--"):
                # This is a HF Hub structure, look for snapshots
                snapshots_path = model_path / "snapshots"
                if snapshots_path.exists():
                    snapshot_dirs = [d for d in snapshots_path.iterdir() if d.is_dir()]
                    logger.debug(f"Found {len(snapshot_dirs)} snapshot directories")

            # If no snapshots found in hub path, check the path directly (legacy structure)
            search_paths = snapshot_dirs if snapshot_dirs else [model_path]

            for search_path in search_paths:
                logger.debug(f"Searching for model files in: {search_path}")
                for file_pattern in essential_files:
                    # Look for files matching the pattern
                    matching_files = list(search_path.rglob(file_pattern))
                    for file_path in matching_files:
                        if file_path.is_file():
                            found_files.append(file_path.name)
                            total_size += file_path.stat().st_size
                            logger.debug(f"Found essential file: {file_path.name}")

                # Also check for other common model files
                all_files = list(search_path.rglob("*"))
                file_count = len([f for f in all_files if f.is_file()])

                if found_files:
                    break  # Found essential files, no need to check other paths

            if found_files:
                details = {
                    "local_path": str(model_path),
                    "searched_paths": [str(p) for p in search_paths],
                    "essential_files": found_files,
                    "total_files": file_count,
                    "total_size_bytes": total_size,
                    "total_size_mb": round(total_size / (1024 * 1024), 2),
                    "snapshot_count": len(snapshot_dirs)
                }

                message = f"Model exists locally with {len(found_files)} essential files ({details['total_size_mb']} MB)"
                if snapshot_dirs:
                    message += f" in {len(snapshot_dirs)} snapshot(s)"
                return ModelProbeResult("exists_locally", message, details)
            else:
                # Path exists but no essential files found
                details = {
                    "local_path": str(model_path),
                    "searched_paths": [str(p) for p in search_paths],
                    "file_count": file_count,
                    "snapshot_count": len(snapshot_dirs),
                    "issue": "No essential model files found"
                }
                return ModelProbeResult("not_found", "Model directory exists but no essential files", details)

        except Exception as e:
            logger.error(f"Error checking local model {model_name}: {e}")
            return ModelProbeResult("network_error", f"Local check failed: {str(e)}")

    def _check_remote_model(self, model_name: str, timeout: int) -> ModelProbeResult:
        """Check if model exists remotely on Hugging Face."""
        start_time = time.time()

        try:
            # Try to get model info with timeout
            logger.debug(f"Checking remote model: {model_name}")

            # Use a separate thread to enforce timeout
            import threading
            result_container = []
            exception_container = []

            def _get_model_info():
                try:
                    model_info = self.api.model_info(model_name)
                    result_container.append(model_info)
                except Exception as e:
                    exception_container.append(e)

            thread = threading.Thread(target=_get_model_info)
            thread.start()
            thread.join(timeout=timeout)

            if thread.is_alive():
                # Thread is still running, timeout occurred
                logger.debug(f"Remote check timed out for {model_name}")
                return ModelProbeResult("timeout", f"Remote check timed out after {timeout}s")

            if exception_container:
                exception = exception_container[0]
                if isinstance(exception, RepositoryNotFoundError):
                    return ModelProbeResult("not_found", f"Model not found on Hugging Face: {model_name}")
                else:
                    # Check for rate limiting (429)
                    error_str = str(exception)
                    if "429" in error_str or "Too Many Requests" in error_str:
                        logger.warning(f"Rate limited checking remote model {model_name}: {exception}")
                        return ModelProbeResult("timeout", f"Rate limited: {str(exception)}")
                    else:
                        logger.error(f"Network error checking remote model {model_name}: {exception}")
                        return ModelProbeResult("network_error", f"Network error: {str(exception)}")

            if result_container:
                model_info = result_container[0]
                elapsed_time = time.time() - start_time

                details = {
                    "model_id": model_info.id,
                    "author": model_info.author,
                    "downloads": getattr(model_info, 'downloads', 0),
                    "likes": getattr(model_info, 'likes', 0),
                    "created_at": getattr(model_info, 'created_at', None),
                    "last_modified": getattr(model_info, 'last_modified', None),
                    "probe_time_seconds": round(elapsed_time, 2),
                    "siblings_count": len(getattr(model_info, 'siblings', []))
                }

                message = f"Model exists remotely (probe took {elapsed_time:.2f}s)"
                return ModelProbeResult("remote_exists", message, details)

            return ModelProbeResult("network_error", "Unknown error during remote check")

        except Exception as e:
            logger.error(f"Error checking remote model {model_name}: {e}")
            return ModelProbeResult("network_error", f"Remote check failed: {str(e)}")

    def _test_download_completion(self, model_name: str, timeout: int = 10) -> ModelProbeResult:
        """
        Test if model is fully downloaded by attempting to download a key file.

        Args:
            model_name: Name of the model to test
            timeout: Test timeout in seconds

        Returns:
            ModelProbeResult indicating if model is fully downloaded
        """
        try:
            logger.debug(f"Testing download completion for {model_name}")

            # Try to download config.json as a test
            # If it returns quickly, model is likely fully downloaded
            # If it starts downloading, model is incomplete
            start_time = time.time()

            # Use a temporary directory for the test
            with tempfile.TemporaryDirectory() as temp_dir:
                try:
                    # Try to download config.json with timeout
                    result = subprocess.run(
                        ["hf", "download", model_name, "config.json",
                         "--local-dir", temp_dir],
                        timeout=timeout,
                        capture_output=True,
                        text=True,
                        cwd=temp_dir
                    )

                    elapsed_time = time.time() - start_time

                    if result.returncode == 0:
                        # Check if file was actually downloaded or just found locally
                        config_path = Path(temp_dir) / "config.json"
                        if config_path.exists():
                            # Quick completion suggests already downloaded
                            if elapsed_time < 2.0:  # Less than 2 seconds suggests already downloaded
                                logger.debug(f"Model {model_name} appears fully downloaded (test took {elapsed_time:.2f}s)")
                                return ModelProbeResult("exists_locally", f"Model fully downloaded (test took {elapsed_time:.2f}s)", {
                                    "test_method": "download_test",
                                    "test_time_seconds": round(elapsed_time, 2),
                                    "test_file": "config.json"
                                })
                            else:
                                logger.debug(f"Model {model_name} download test took {elapsed_time:.2f}s, may be incomplete")
                                return ModelProbeResult("not_found", f"Model appears incomplete (test took {elapsed_time:.2f}s)", {
                                    "test_method": "download_test",
                                    "test_time_seconds": round(elapsed_time, 2),
                                    "issue": "slow_download_test"
                                })
                        else:
                            logger.warning(f"Config.json not found after test download for {model_name}")
                            return ModelProbeResult("not_found", "Model test file not found", {
                                "test_method": "download_test",
                                "issue": "test_file_missing"
                            })
                    else:
                        logger.warning(f"Download test failed for {model_name}: {result.stderr}")
                        return ModelProbeResult("not_found", "Model download test failed", {
                            "test_method": "download_test",
                            "error": result.stderr.strip()
                        })

                except subprocess.TimeoutExpired:
                    logger.debug(f"Download test timed out for {model_name}, model may be large/incomplete")
                    return ModelProbeResult("timeout", f"Download test timed out after {timeout}s", {
                        "test_method": "download_test",
                        "timeout_used": timeout
                    })
                except FileNotFoundError:
                    logger.warning("hf command not found, falling back to basic path check")
                    return None  # Indicate fallback needed

        except Exception as e:
            logger.error(f"Error during download test for {model_name}: {e}")
            return None  # Indicate fallback needed

    def probe_models_batch(self, model_names: list[str], timeout: int = None) -> dict[str, ModelProbeResult]:
        """
        Probe multiple models in batch.

        Args:
            model_names: List of model names to probe
            timeout: Timeout per model probe

        Returns:
            Dictionary mapping model names to probe results
        """
        logger.info(f"Probing {len(model_names)} models in batch")
        results = {}

        for model_name in model_names:
            try:
                result = self.probe_model(model_name, timeout)
                results[model_name] = result

                # Small delay to avoid overwhelming the API
                time.sleep(0.1)

            except RepositoryNotFoundError as e:
                logger.warning(f"Model {model_name} not found on Hugging Face: {e}")
                results[model_name] = ModelProbeResult("not_found", f"Model not found on Hugging Face: {model_name}")
            except Exception as e:
                # Check if it's a network-related error
                error_str = str(e).lower()
                if "429" in error_str or "too many requests" in error_str:
                    logger.warning(f"Rate limited probing model {model_name}: {e}")
                    results[model_name] = ModelProbeResult("timeout", f"Rate limited: {str(e)}")
                elif any(keyword in error_str for keyword in ["network", "connection", "timeout", "resolve", "503", "502"]):
                    logger.error(f"Network error probing model {model_name}: {e}")
                    results[model_name] = ModelProbeResult("network_error", f"Network error: {str(e)}")
                else:
                    logger.error(f"Unexpected error probing model {model_name}: {e}")
                    results[model_name] = ModelProbeResult("not_found", f"Probe failed: {str(e)}")

        # Log summary
        status_counts = {}
        for result in results.values():
            status_counts[result.status] = status_counts.get(result.status, 0) + 1

        logger.info(f"Batch probe complete: {status_counts}")
        return results

    def get_status_summary(self, results: dict[str, ModelProbeResult]) -> dict[str, Any]:
        """Get summary statistics from probe results."""
        summary = {
            "total_models": len(results),
            "exists_locally": 0,
            "remote_exists": 0,
            "not_found": 0,
            "network_error": 0,
            "timeout": 0,
            "by_model": {}
        }

        for model_name, result in results.items():
            summary[result.status] += 1
            summary["by_model"][model_name] = result.to_dict()

        return summary
