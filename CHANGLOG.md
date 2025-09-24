# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Priority-based download queue ordering** - Models are now downloaded based on priority (high → medium → low)
- **Enhanced daemon stop mechanism** - Daemon can now be stopped even when PID file is missing
- **Process discovery by name** - When PID file is missing, daemon processes are found by command line pattern
- **Download queue logging** - Automatic logging of download queue with priorities after model synchronization
- **Status sync interval configuration** - Added `status_sync_interval` setting in monitoring configuration

### Changed
- **Simplified model configuration** - Removed unused fields (`description`, `size_estimate`, `tags`) from models.json
- **Updated priority implementation** - Fixed priority reading from model metadata using proper `get_metadata()` method
- **Enhanced database queries** - Updated SQLAlchemy `case()` syntax for priority ordering
- **Improved daemon management** - More robust process stopping with graceful fallback mechanisms
- **Updated default configuration** - Time window now enabled by default (22:00-07:00)

### Fixed
- **Priority display bug** - Fixed issue where all models showed "medium" priority regardless of actual configuration
- **Daemon stop failures** - Fixed daemon stop process when PID file is missing or corrupted
- **SQLAlchemy syntax error** - Fixed `case()` function syntax for newer SQLAlchemy versions
- **Process cleanup** - Ensured daemon processes are properly terminated even in error scenarios

### Technical Details
- Priority ordering uses database-level sorting with SQLAlchemy `case()` expressions
- Process discovery uses `ps aux` command parsing to find daemon processes
- Enhanced error handling in daemon lifecycle management
- Improved logging and debugging capabilities for troubleshooting daemon issues

## [0.1.0] - 2025-09-24

### Added
- Initial release of HF Downloader
- Basic download scheduling functionality
- CLI interface for managing downloads and schedules
- Database storage for models, schedules, and download sessions
- Configuration management system
- Background process support
- Health monitoring and watchdog functionality
- Retry mechanism for failed downloads