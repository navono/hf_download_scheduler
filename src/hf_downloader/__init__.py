"""
HF Downloader - A scheduled Hugging Face model downloader.

This package provides automated downloading of Hugging Face models
based on configurable schedules with background processing capability.
"""

__version__ = "1.0.0"
__author__ = "HF Downloader Team"
__email__ = "contact@hf-downloader.com"

from .core.config import Config

__all__ = [
    "Config",
]
