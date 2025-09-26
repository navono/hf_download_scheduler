"""
Main CLI entry point for HF Downloader.

This module provides the command-line interface for the HF Downloader application.
"""

import json
from typing import Any

import click

from ..services.integration_service import IntegrationService
from ..services.model_sync import ModelSyncService
from ..utils import Config, CustomizeLogger

gen_config = Config().get_config()
logger = CustomizeLogger.make_logger(gen_config["log"])


@click.group()
@click.option(
    "--config",
    "-c",
    type=click.Path(exists=True),
    default="./config/config.yaml",
    help="Configuration file path",
)
@click.option(
    "--database",
    "-d",
    type=click.Path(),
    default="./hf_downloader.db",
    help="Database file path",
)
@click.option(
    "--pid",
    "-p",
    type=click.Path(),
    default="./hf_downloader.pid",
    help="PID file path",
)
@click.option(
    "--log-level",
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]),
    default="INFO",
    help="Log level",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["json", "table"]),
    default="table",
    help="Output format",
)
@click.pass_context
def cli(ctx, config, database, pid, log_level, output_format):
    """HF Downloader - Scheduled Hugging Face model downloader."""
    ctx.ensure_object(dict)

    # Note: Logging is configured globally using loguru through CustomizeLogger

    # Initialize context
    ctx.obj["config_path"] = config
    ctx.obj["database_path"] = database
    ctx.obj["pid_path"] = pid
    ctx.obj["log_level"] = log_level
    ctx.obj["output_format"] = output_format

    # Initialize integration service
    ctx.obj["integration_service"] = IntegrationService(
        config, database, pid, log_level
    )


@cli.command()
@click.option("--foreground", "-f", is_flag=True, help="Run in foreground mode")
@click.pass_context
def start(ctx, foreground):
    """Start the downloader daemon."""
    integration_service = ctx.obj["integration_service"]

    logger.info(f"Starting downloader daemon in {foreground} mode...")

    if foreground:
        # Run daemon in foreground
        from ..daemon.main import Daemon

        daemon = Daemon(
            config_path=ctx.obj["config_path"],
            db_path=ctx.obj["database_path"],
            pid_path=ctx.obj["pid_path"],
            log_level=ctx.obj["log_level"],
        )

        # Display models that will be downloaded before starting daemon
        if ctx.obj["output_format"] == "table":
            models = integration_service.cli_integration.handle_model_list(
                status_filter="pending"
            )
            if models["status"] == "success" and models["models"]:
                logger.info(
                    "Pending models that will be downloaded on next scheduled run:"
                )
                _format_models_output(models["models"])

        success = daemon.start()
        if not success:
            logger.error("Failed to start daemon")
            ctx.exit(1)
    else:
        # Start daemon in background
        result = integration_service.safe_daemon_start(foreground=False)

        if result["status"] == "started":
            logger.info(f"Daemon started successfully with PID {result['pid']}")
        elif result["status"] == "already_running":
            logger.info(f"Daemon is already running (PID {result['pid']})")
        else:
            error_msg = result.get("error", "Unknown error")
            stderr = result.get("stderr", "")
            if stderr:
                logger.error(f"Failed to start daemon: {error_msg}\nError details:\n{stderr}")
            else:
                logger.error(f"Failed to start daemon: {error_msg}")
            ctx.exit(1)


@cli.command()
@click.pass_context
def stop(ctx):
    """Stop the downloader daemon."""
    integration_service = ctx.obj["integration_service"]

    result = integration_service.safe_daemon_stop()

    if result["status"] == "stopped":
        logger.info(f"Daemon stopped successfully (PID {result['pid']})")
    elif result["status"] == "not_running":
        logger.info("Daemon is not running")
    else:
        logger.error(f"Failed to stop daemon: {result.get('error', 'Unknown error')}")
        ctx.exit(1)


@cli.command()
@click.option("--detailed", "-d", is_flag=True, help="Show detailed status")
@click.pass_context
def status(ctx, detailed):
    """Show daemon status."""
    integration_service = ctx.obj["integration_service"]

    result = integration_service.cli_integration.handle_daemon_status(detailed=detailed)

    if ctx.obj["output_format"] == "json":
        logger.info(json.dumps(result, indent=2))
    else:
        _format_status_output(result, detailed)


@cli.command()
@click.pass_context
def restart(ctx):
    """Restart the downloader daemon."""
    integration_service = ctx.obj["integration_service"]

    result = integration_service.cli_integration.handle_daemon_restart()

    if result["status"] == "restarted":
        stop_result = result["stop_result"]
        start_result = result["start_result"]

        if stop_result["status"] == "stopped":
            logger.info("Previous daemon stopped successfully")
        elif stop_result["status"] == "not_running":
            logger.info("No previous daemon was running")

        if start_result["status"] == "started":
            logger.info(
                f"New daemon started successfully with PID {start_result['pid']}"
            )
        else:
            click.echo(
                f"Failed to start new daemon: {start_result.get('error', 'Unknown error')}",
                err=True,
            )
            ctx.exit(1)
    else:
        click.echo(
            f"Failed to restart daemon: {result.get('error', 'Unknown error')}",
            err=True,
        )
        ctx.exit(1)


@cli.group()
@click.pass_context
def models(ctx):
    """Manage download models."""
    pass


@models.command("list")
@click.option(
    "--status",
    type=click.Choice(["all", "pending", "downloading", "completed", "failed"]),
    default="all",
    help="Filter by status",
)
@click.pass_context
def list_models(ctx, status):
    """List models."""
    integration_service = ctx.obj["integration_service"]

    result = integration_service.cli_integration.handle_model_list(status_filter=status)

    if result["status"] == "success":
        if ctx.obj["output_format"] == "json":
            logger.info(json.dumps(result["models"], indent=2))
        else:
            _format_models_output(result["models"])
    else:
        logger.error(f"Error: {result.get('error', 'Unknown error')}")
        ctx.exit(1)


@models.command("add")
@click.argument("model_name")
@click.option("--models", type=click.Path(exists=True), help="Models JSON file path")
@click.pass_context
def add_model(ctx, model_name, _models):
    """Add a model to the download queue."""
    integration_service = ctx.obj["integration_service"]

    result = integration_service.cli_integration.handle_model_add(model_name)

    if result["status"] == "created":
        logger.info(
            f"Model {model_name} added successfully with ID {result['model']['id']}"
        )
    elif result["status"] == "exists":
        logger.info(
            f"Model {model_name} already exists with status {result['model']['status']}"
        )
    else:
        logger.error(f"Error: {result.get('error', 'Unknown error')}")
        ctx.exit(1)


@models.command("remove")
@click.argument("model_name")
@click.pass_context
def remove_model(_ctx, model_name):
    """Remove a model from the download queue."""
    # This would require a delete method in DatabaseManager
    logger.warning(f"Model {model_name} removal not yet implemented")


@models.command("sync")
@click.pass_context
def sync_models(ctx):
    """Synchronize model status between JSON and database."""
    integration_service = ctx.obj["integration_service"]

    result = integration_service.sync_models()

    if result["success"]:
        logger.info("Model synchronization completed successfully")
        logger.info(
            f"JSON to DB: {result['json_to_db']['added']} added, {result['json_to_db']['skipped']} skipped"
        )
        logger.info(
            f"DB to JSON: {result['db_to_json']['updated']} updated, {result['db_to_json']['unchanged']} unchanged"
        )

        if result["remaining_differences"] > 0:
            logger.warning(
                f"Warning: {result['remaining_differences']} models still have differences"
            )
    else:
        click.echo(
            f"Synchronization failed: {result.get('error', 'Unknown error')}", err=True
        )
        ctx.exit(1)


@models.command("sync-status")
@click.pass_context
def sync_status(ctx):
    """Show models that need synchronization."""
    integration_service = ctx.obj["integration_service"]

    models_needing_sync = integration_service.get_models_needing_sync()

    if ctx.obj["output_format"] == "json":
        logger.info(json.dumps(models_needing_sync, indent=2))
    else:
        if not models_needing_sync:
            logger.info("All models are synchronized")
            return

        logger.info("Models needing synchronization:")
        logger.info(
            f"{'Name':<40} {'JSON Status':<12} {'DB Status':<12} {'Priority':<10}"
        )
        logger.info("-" * 80)

        for model in models_needing_sync:
            name = model.get("name", "N/A")
            json_status = model.get("json_status", "N/A")
            db_status = model.get("db_status", "N/A")
            priority = model.get("priority", "medium")

            logger.info(f"{name:<40} {json_status:<12} {db_status:<12} {priority:<10}")


@models.command("update-status")
@click.argument("model_name")
@click.argument("status")
@click.pass_context
def update_model_status(ctx, model_name, status):
    """Update status of a specific model in JSON file."""
    integration_service = ctx.obj["integration_service"]

    result = integration_service.update_model_status_in_json(model_name, status)

    if result:
        logger.info(f"Updated {model_name} status to {status} in JSON file")
    else:
        logger.error(f"Failed to update {model_name} status")
        ctx.exit(1)


@cli.group()
@click.pass_context
def schedule(ctx):
    """Manage download schedules."""
    pass


@schedule.command("list")
@click.pass_context
def list_schedules(ctx):
    """List schedules."""
    integration_service = ctx.obj["integration_service"]

    result = integration_service.cli_integration.handle_schedule_list()

    if result["status"] == "success":
        if ctx.obj["output_format"] == "json":
            logger.info(json.dumps(result["schedules"], indent=2))
        else:
            _format_schedules_output(result["schedules"])
    else:
        logger.error(f"Error: {result.get('error', 'Unknown error')}")
        ctx.exit(1)


@schedule.command("create")
@click.argument("name")
@click.argument("schedule_type", type=click.Choice(["daily", "weekly"]))
@click.argument("time_str")
@click.option(
    "--day-of-week",
    type=click.IntRange(0, 6),
    help="Day of week (0=Monday, 6=Sunday) for weekly schedules",
)
@click.option(
    "--max-concurrent",
    type=click.IntRange(1, 10),
    default=1,
    help="Maximum concurrent downloads",
)
@click.pass_context
def create_schedule(ctx, name, schedule_type, time_str, day_of_week, max_concurrent):
    """Create a new schedule."""
    integration_service = ctx.obj["integration_service"]

    result = integration_service.cli_integration.handle_schedule_create(
        name=name,
        schedule_type=schedule_type,
        time_str=time_str,
        day_of_week=day_of_week,
        max_concurrent_downloads=max_concurrent,
    )

    if result["status"] == "created":
        logger.info(
            f"Schedule '{name}' created successfully with ID {result['schedule']['id']}"
        )
    else:
        logger.error(f"Error: {result.get('error', 'Unknown error')}")
        ctx.exit(1)


@schedule.command("enable")
@click.argument("schedule_id", type=int)
@click.pass_context
def enable_schedule(ctx, schedule_id):
    """Enable a schedule."""
    integration_service = ctx.obj["integration_service"]

    result = integration_service.cli_integration.handle_schedule_enable(schedule_id)
    if result["status"] == "enabled":
        logger.info(f"Schedule {schedule_id} enabled successfully")
    else:
        click.echo(
            f"Error: {result.get('message', result.get('error', 'Unknown error'))}",
            err=True,
        )
        ctx.exit(1)


@schedule.command("disable")
@click.argument("schedule_id", type=int)
@click.pass_context
def disable_schedule(ctx, schedule_id):
    """Disable a schedule."""
    integration_service = ctx.obj["integration_service"]

    result = integration_service.cli_integration.handle_schedule_disable(schedule_id)
    if result["status"] == "disabled":
        logger.info(f"Schedule {schedule_id} disabled successfully")
    else:
        click.echo(
            f"Error: {result.get('message', result.get('error', 'Unknown error'))}",
            err=True,
        )
        ctx.exit(1)


@schedule.command("update")
@click.argument("schedule_id", type=int)
@click.option("--name", help="Schedule name")
@click.option(
    "--type",
    "schedule_type",
    type=click.Choice(["daily", "weekly"]),
    help="Schedule type",
)
@click.option("--time", help="Time in HH:MM format")
@click.option(
    "--day-of-week", type=click.IntRange(0, 6), help="Day of week (0=Monday, 6=Sunday)"
)
@click.option(
    "--max-concurrent", type=click.IntRange(1, 10), help="Maximum concurrent downloads"
)
@click.pass_context
def update_schedule(
    ctx, schedule_id, name, schedule_type, time, day_of_week, max_concurrent
):
    """Update a schedule configuration."""
    integration_service = ctx.obj["integration_service"]

    # Build kwargs for update
    kwargs = {}
    if name is not None:
        kwargs["name"] = name
    if schedule_type is not None:
        kwargs["type"] = schedule_type
    if time is not None:
        kwargs["time"] = time
    if day_of_week is not None:
        kwargs["day_of_week"] = day_of_week
    if max_concurrent is not None:
        kwargs["max_concurrent_downloads"] = max_concurrent

    result = integration_service.cli_integration.handle_schedule_update(
        schedule_id, **kwargs
    )
    if result["status"] == "updated":
        logger.info(f"Schedule {schedule_id} updated successfully")
    else:
        click.echo(
            f"Error: {result.get('message', result.get('error', 'Unknown error'))}",
            err=True,
        )
        ctx.exit(1)


@schedule.command("time-window")
@click.argument("schedule_id", type=int)
@click.option("--enable", is_flag=True, help="Enable time window restriction")
@click.option("--disable", is_flag=True, help="Disable time window restriction")
@click.option("--start-time", help="Start time in HH:MM format (e.g., 22:00)")
@click.option("--end-time", help="End time in HH:MM format (e.g., 07:00)")
@click.pass_context
def time_window_schedule(ctx, schedule_id, enable, disable, start_time, end_time):
    """Configure time window restrictions for a schedule."""
    integration_service = ctx.obj["integration_service"]

    # Validate options
    if enable and disable:
        logger.error("Error: Cannot specify both --enable and --disable")
        ctx.exit(1)

    if not enable and not disable:
        logger.error("Error: Must specify either --enable or --disable")
        ctx.exit(1)

    if enable and (not start_time or not end_time):
        click.echo(
            "Error: --start-time and --end-time are required when enabling time window",
            err=True,
        )
        ctx.exit(1)

    # Build kwargs for time window update
    kwargs = {
        "time_window_enabled": enable,
        "time_window_start": start_time if enable else None,
        "time_window_end": end_time if enable else None,
    }

    result = integration_service.cli_integration.handle_schedule_time_window(
        schedule_id, **kwargs
    )
    if result["status"] == "updated":
        if enable:
            logger.info(f"Time window enabled for schedule {schedule_id}")
            logger.info(f"Window: {start_time} - {end_time}")
        else:
            logger.info(f"Time window disabled for schedule {schedule_id}")
    else:
        click.echo(
            f"Error: {result.get('message', result.get('error', 'Unknown error'))}",
            err=True,
        )
        ctx.exit(1)


@schedule.command("time-window-status")
@click.argument("schedule_id", type=int)
@click.pass_context
def time_window_status(ctx, schedule_id):
    """Show time window status for a schedule."""
    integration_service = ctx.obj["integration_service"]

    result = integration_service.cli_integration.handle_time_window_status(schedule_id)
    if result["status"] == "success":
        schedule = result["schedule"]
        logger.info(f"Time Window Status for Schedule {schedule_id}:")
        logger.info(f"  Enabled: {'Yes' if schedule.time_window_enabled else 'No'}")

        if schedule.time_window_enabled:
            logger.info(f"  Start Time: {schedule.time_window_start}")
            logger.info(f"  End Time: {schedule.time_window_end}")
            logger.info(
                f"  Currently Active: {'Yes' if result['is_currently_active'] else 'No'}"
            )
            logger.info(
                f"  Can Start Downloads: {'Yes' if result['can_start_downloads'] else 'No'}"
            )

            if result.get("next_window_start"):
                logger.info(f"  Next Window Start: {result['next_window_start']}")
            if result.get("current_window_end"):
                logger.info(f"  Current Window End: {result['current_window_end']}")
    else:
        click.echo(
            f"Error: {result.get('message', result.get('error', 'Unknown error'))}",
            err=True,
        )
        ctx.exit(1)


@schedule.command("delete")
@click.argument("schedule_id", type=int)
@click.pass_context
def delete_schedule(ctx, schedule_id):
    """Delete a schedule."""
    integration_service = ctx.obj["integration_service"]

    result = integration_service.cli_integration.handle_schedule_delete(schedule_id)
    if result["status"] == "deleted":
        logger.info(f"Schedule {schedule_id} deleted successfully")
    else:
        click.echo(
            f"Error: {result.get('message', result.get('error', 'Unknown error'))}",
            err=True,
        )
        ctx.exit(1)


@schedule.command("backup")
@click.pass_context
def backup_schedules(ctx):
    """Create a backup of all schedules."""
    integration_service = ctx.obj["integration_service"]

    result = integration_service.cli_integration.handle_schedule_backup()
    if result["status"] == "success":
        logger.info("Schedule backup created successfully")
        logger.info(f"Backup timestamp: {result['timestamp']}")
        logger.info(f"Schedules backed up: {result['backup_count']}")
    else:
        logger.error(f"Error: {result.get('error', 'Unknown error')}")
        ctx.exit(1)


@schedule.command("restore")
@click.pass_context
def restore_schedules(ctx):
    """Restore schedules from backup."""
    integration_service = ctx.obj["integration_service"]

    result = integration_service.cli_integration.handle_schedule_restore()
    if result["status"] == "success":
        logger.info("Schedule restore completed successfully")
        logger.info(f"Backup timestamp: {result['backup_timestamp']}")
        logger.info(f"Schedules restored: {result['restored_count']}")
    else:
        logger.error(f"Error: {result.get('error', 'Unknown error')}")
        ctx.exit(1)


@cli.command()
@click.pass_context
def download(ctx):
    """Trigger a manual download run."""
    integration_service = ctx.obj["integration_service"]

    result = integration_service.safe_manual_download()

    if result["status"] == "triggered":
        logger.info("Manual download triggered successfully")
        logger.info(f"Schedule: {result['schedule']['name']}")
    else:
        click.echo(
            f"Failed to trigger manual download: {result.get('error', 'Unknown error')}",
            err=True,
        )
        ctx.exit(1)


@cli.group()
@click.pass_context
def sessions(ctx):
    """Manage download sessions."""
    pass


@sessions.command("list")
@click.option("--model", help="Filter by model name")
@click.option(
    "--status",
    help="Filter by status (started, in_progress, completed, failed, cancelled)",
)
@click.pass_context
def list_sessions(ctx, model, status):
    """List download sessions."""
    integration_service = ctx.obj["integration_service"]

    result = integration_service.cli_integration.handle_session_list(
        model_name=model, status=status
    )

    if result["status"] == "success":
        if ctx.obj["output_format"] == "json":
            logger.info(json.dumps(result, indent=2))
        else:
            _format_sessions_output(
                result["sessions"],
                result.get("filter_model"),
                result.get("filter_status"),
            )
    else:
        logger.error(f"Error: {result.get('error', 'Unknown error')}")
        ctx.exit(1)


@sessions.command("details")
@click.argument("session_id", type=int)
@click.pass_context
def session_details(ctx, session_id):
    """Show detailed information about a session."""
    integration_service = ctx.obj["integration_service"]

    result = integration_service.cli_integration.handle_session_details(session_id)

    if result["status"] == "success":
        if ctx.obj["output_format"] == "json":
            logger.info(json.dumps(result, indent=2))
        else:
            _format_session_details_output(result)
    else:
        logger.error(f"Error: {result.get('error', 'Unknown error')}")
        ctx.exit(1)


@sessions.command("cancel")
@click.argument("session_id", type=int)
@click.pass_context
def cancel_session(ctx, session_id):
    """Cancel a download session."""
    integration_service = ctx.obj["integration_service"]

    result = integration_service.cli_integration.handle_session_cancel(session_id)

    if result["status"] == "cancelled":
        logger.info(f"Session {session_id} cancelled successfully")
        logger.info(f"Model: {result['model']}")
    else:
        click.echo(
            f"Error: {result.get('message', result.get('error', 'Unknown error'))}",
            err=True,
        )
        ctx.exit(1)


@sessions.command("retry")
@click.argument("session_id", type=int)
@click.option("--schedule-id", type=int, help="Schedule ID to use for retry")
@click.pass_context
def retry_session(ctx, session_id, schedule_id):
    """Retry a failed download session."""
    integration_service = ctx.obj["integration_service"]

    result = integration_service.cli_integration.handle_session_retry(
        session_id, schedule_id
    )

    if result["status"] == "retry_created":
        logger.info("Retry session created successfully")
        logger.info(f"Original session: {result['original_session_id']}")
        logger.info(f"New session: {result['new_session_id']}")
        logger.info(f"Model: {result['model']}")
        logger.info(f"Retry count: {result['retry_count']}")
    else:
        click.echo(
            f"Error: {result.get('message', result.get('error', 'Unknown error'))}",
            err=True,
        )
        ctx.exit(1)


@sessions.command("cleanup")
@click.option(
    "--days", type=int, default=30, help="Number of days to keep (default: 30)"
)
@click.pass_context
def cleanup_sessions(ctx, days):
    """Clean up old download sessions."""
    integration_service = ctx.obj["integration_service"]

    result = integration_service.cli_integration.handle_session_cleanup(days)

    if result["status"] == "success":
        logger.info("Session cleanup completed successfully")
        logger.info(f"Deleted {result['deleted_count']} old sessions")
        logger.info(f"Kept sessions from last {days} days")
    else:
        logger.error(f"Error: {result.get('error', 'Unknown error')}")
        ctx.exit(1)


@cli.command("stats")
@click.option("--model", help="Show statistics for specific model")
@click.option("--schedule-id", type=int, help="Show statistics for specific schedule")
@click.option("--days", type=int, help="Show statistics for last N days")
@click.pass_context
def download_stats(ctx, model, schedule_id, days):
    """Show download statistics."""
    integration_service = ctx.obj["integration_service"]

    result = integration_service.cli_integration.handle_download_statistics(
        model_name=model, schedule_id=schedule_id, time_range_days=days
    )

    if result.get("status") == "success":
        if ctx.obj["output_format"] == "json":
            logger.info(json.dumps(result, indent=2))
        else:
            _format_statistics_output(result)
    else:
        logger.error(f"Error: {result.get('error', 'Unknown error')}")
        ctx.exit(1)


def _format_status_output(result: dict[str, Any], detailed: bool):
    """Format status output for table display."""
    status = result.get("status", "unknown")

    if status == "running":
        pid = result.get("pid", "unknown")
        uptime = result.get("uptime", "unknown")
        logger.info(f"Daemon is running (PID: {pid})")
        logger.info(f"Uptime: {uptime}")

        if detailed:
            memory = result.get("memory_usage")
            if memory:
                logger.info(f"Memory: {memory.get('rss_formatted', 'N/A')}")
                logger.info(f"CPU: {result.get('cpu_usage', 0):.1f}%")
    elif status == "stopped":
        logger.info("Daemon is not running")
    else:
        logger.info(f"Status: {status}")


def _format_models_output(models):
    """Format models output for table display."""
    if not models:
        logger.info("No models found")
        return

    logger.info(f"{'ID':<5} {'Name':<40} {'Status':<12} {'Size':<10} {'Created':<20}")
    logger.info("-" * 90)

    for model in models:
        # Handle both model objects and dictionaries
        if hasattr(model, "id"):
            # Model object
            model_id = model.id
            model_name = model.name
            model_status = model.status
            size_bytes = getattr(model, "size_bytes", None)
            created_at = getattr(model, "created_at", None)
        else:
            # Dictionary
            model_id = model.get("id", "N/A")
            model_name = model.get("name", "N/A")
            model_status = model.get("status", "N/A")
            size_bytes = model.get("size_bytes")
            created_at = model.get("created_at")

        size_str = f"{size_bytes / 1024 / 1024:.1f}MB" if size_bytes else "N/A"

        if created_at:
            if hasattr(created_at, "strftime"):
                created_str = created_at.strftime("%Y-%m-%d %H:%M:%S")
            else:
                created_str = str(created_at)[:19]  # Assume ISO format
        else:
            created_str = "N/A"

        logger.info(
            f"{model_id:<5} {model_name:<40} {model_status:<12} {size_str:<10} {created_str:<20}"
        )


def _format_schedules_output(schedules):
    """Format schedules output for table display."""
    if not schedules:
        logger.info("No schedules found")
        return

    logger.info(
        f"{'ID':<5} {'Name':<20} {'Type':<8} {'Time':<8} {'Day':<5} {'Enabled':<8} {'Concurrent':<10} {'Time Window':<15}"
    )
    logger.info("-" * 85)

    for schedule in schedules:
        day_str = (
            str(schedule.day_of_week) if schedule.day_of_week is not None else "N/A"
        )
        enabled_str = "Yes" if schedule.enabled else "No"

        # Format time window information
        if (
            schedule.time_window_enabled
            and schedule.time_window_start
            and schedule.time_window_end
        ):
            tw_str = f"{schedule.time_window_start}-{schedule.time_window_end}"
        elif schedule.time_window_enabled:
            tw_str = "Enabled (incomplete)"
        else:
            tw_str = "Disabled"

        logger.info(
            f"{schedule.id:<5} {schedule.name:<20} {schedule.type:<8} {schedule.time:<8} {day_str:<5} {enabled_str:<8} {schedule.max_concurrent_downloads:<10} {tw_str:<15}"
        )


def _format_sessions_output(sessions, filter_model=None, filter_status=None):
    """Format sessions output for table display."""
    if not sessions:
        logger.info("No sessions found")
        return

    # Show filter information
    if filter_model or filter_status:
        filter_info = []
        if filter_model:
            filter_info.append(f"Model: {filter_model}")
        if filter_status:
            filter_info.append(f"Status: {filter_status}")
        logger.info(f"Filtered by: {', '.join(filter_info)}")
        logger.info("")

    logger.info(
        f"{'ID':<5} {'Model ID':<8} {'Status':<12} {'Progress':<10} {'Downloaded':<12} {'Total':<10} {'Started':<20}"
    )
    logger.info("-" * 85)

    for session in sessions:
        # Handle both session objects and dictionaries
        if hasattr(session, "id"):
            session_id = session.id
            model_id = session.model_id
            status = session.status
            bytes_downloaded = getattr(session, "bytes_downloaded", 0)
            total_bytes = getattr(session, "total_bytes", 0)
            started_at = getattr(session, "started_at", None)
        else:
            session_id = session.get("id", "N/A")
            model_id = session.get("model_id", "N/A")
            status = session.get("status", "N/A")
            bytes_downloaded = session.get("bytes_downloaded", 0)
            total_bytes = session.get("total_bytes", 0)
            started_at = session.get("started_at")

        # Calculate progress
        progress = 0
        if total_bytes and total_bytes > 0:
            progress = (bytes_downloaded / total_bytes) * 100

        # Format sizes
        downloaded_str = (
            f"{bytes_downloaded / 1024 / 1024:.1f}MB" if bytes_downloaded else "0MB"
        )
        total_str = f"{total_bytes / 1024 / 1024:.1f}MB" if total_bytes else "N/A"

        # Format start time
        if started_at:
            if hasattr(started_at, "strftime"):
                started_str = started_at.strftime("%Y-%m-%d %H:%M:%S")
            else:
                started_str = str(started_at)[:19]  # Assume ISO format
        else:
            started_str = "N/A"

        logger.info(
            f"{session_id:<5} {model_id:<8} {status:<12} {progress:<9.1f}% {downloaded_str:<12} {total_str:<10} {started_str:<20}"
        )


def _format_session_details_output(result):
    """Format session details output for table display."""
    session = result["session"]
    model = result["model"]
    progress = result["progress_percentage"]
    duration = result["duration_seconds"]
    speed_bps = result["download_speed_bps"]
    speed_mbps = result["download_speed_mbps"]

    logger.info("Session Details")
    logger.info("=" * 50)
    logger.info(f"Session ID: {session['id']}")
    logger.info(f"Model: {model['name']} (ID: {session['model_id']})")
    logger.info(f"Status: {session['status']}")
    logger.info(f"Progress: {progress:.1f}%")
    logger.info(f"Downloaded: {session['bytes_downloaded'] / 1024 / 1024:.1f}MB")
    logger.info(
        f"Total Size: {session['total_bytes'] / 1024 / 1024:.1f}MB"
        if session["total_bytes"]
        else "Total Size: N/A"
    )

    if duration:
        logger.info(f"Duration: {duration:.1f} seconds")
    if speed_bps > 0:
        logger.info(f"Download Speed: {speed_mbps:.2f} Mbps")

    logger.info(f"Retry Count: {session['retry_count']}")
    logger.info(
        f"Started: {session['started_at'][:19] if session['started_at'] else 'N/A'}"
    )
    logger.info(
        f"Completed: {session['completed_at'][:19] if session['completed_at'] else 'N/A'}"
    )

    if session.get("error_message"):
        logger.info(f"Error: {session['error_message']}")

    if session.get("schedule_id"):
        logger.info(f"Schedule ID: {session['schedule_id']}")


def _format_statistics_output(stats):
    """Format statistics output for table display."""
    logger.info("Download Statistics")
    logger.info("=" * 50)

    logger.info("Sessions Summary:")
    logger.info(f"  Total Sessions: {stats['total_sessions']}")
    logger.info(f"  Completed: {stats['completed_sessions']}")
    logger.info(f"  Failed: {stats['failed_sessions']}")
    logger.info(f"  Cancelled: {stats['cancelled_sessions']}")
    logger.info(f"  Currently Active: {stats['active_sessions']}")
    logger.info(f"  Success Rate: {stats['success_rate']}%")

    logger.info("\nData Transfer:")
    logger.info(
        f"  Total Downloaded: {stats['total_bytes_downloaded'] / 1024 / 1024 / 1024:.2f} GB"
    )
    logger.info(
        f"  Total Requested: {stats['total_bytes_requested'] / 1024 / 1024 / 1024:.2f} GB"
    )
    logger.info(f"  Completion Rate: {stats['completion_rate']}%")

    if stats["average_download_speed_bps"] > 0:
        logger.info(f"  Average Speed: {stats['average_download_speed_mbps']:.2f} Mbps")

    if stats.get("current_active_downloads", 0) > 0:
        logger.info(
            f"\nCurrently Downloading: {stats['current_active_downloads']} models"
        )
        for model in stats.get("current_downloading_models", []):
            logger.info(f"  - {model}")

    if stats.get("total_models_tracked", 0) > 0:
        logger.info(f"\nTotal Models Tracked: {stats['total_models_tracked']}")


@cli.group()
def probe():
    """Model probing commands."""
    pass


@probe.command("model")
@click.argument("model_name")
@click.option("--timeout", "-t", type=int, default=5, help="Probe timeout in seconds")
@click.option("--json", "output_json", is_flag=True, help="Output in JSON format")
@click.pass_context
def probe_model(ctx, model_name, timeout, output_json):
    """Probe a single model to check its download status."""
    integration_service = ctx.obj["integration_service"]

    try:
        # Initialize model sync service with config from integration service
        config = integration_service.service_container.config
        model_sync_service = ModelSyncService(
            integration_service.service_container.db_manager,
            config.models_file,
            config.download_directory,
        )

        # Probe the model
        result = model_sync_service.probe_single_model(model_name, timeout)

        if output_json:
            logger.info(json.dumps(result, indent=2))
        else:
            _format_probe_model_output(result)

    except Exception as e:
        logger.error(f"Error probing model: {e}")
        ctx.exit(1)


@probe.command("pending")
@click.option(
    "--timeout", "-t", type=int, default=5, help="Probe timeout per model in seconds"
)
@click.option("--json", "output_json", is_flag=True, help="Output in JSON format")
@click.option(
    "--update", is_flag=True, help="Update model status based on probe results"
)
@click.pass_context
def probe_pending(ctx, timeout, output_json, update):
    """Probe all pending models to check their actual download status."""
    integration_service = ctx.obj["integration_service"]

    try:
        # Initialize model sync service with config from integration service
        config = integration_service.service_container.config
        model_sync_service = ModelSyncService(
            integration_service.service_container.db_manager,
            config.models_file,
            config.download_directory,
        )

        if update:
            # Probe and update status
            result = model_sync_service.probe_and_sync_pending_models(timeout)
        else:
            # Just probe without updating
            from ..services.model_probe import ModelProbeService

            probe_service = ModelProbeService(config.download_directory)

            # Get pending models
            pending_models = (
                integration_service.service_container.db_manager.get_models_by_status(
                    "pending"
                )
            )
            model_names = [model.name for model in pending_models]

            if not model_names:
                logger.info("No pending models found")
                return

            # Probe models
            probe_results = probe_service.probe_models_batch(model_names, timeout)
            summary = probe_service.get_status_summary(probe_results)

            result = {
                "timestamp": model_sync_service.db_manager.get_system_config(
                    "last_probe_time", ""
                ),
                "total_models": len(pending_models),
                "probed_models": len(probe_results),
                "probe_summary": summary,
                "results": {
                    name: result.to_dict() for name, result in probe_results.items()
                },
            }

        if output_json:
            logger.info(json.dumps(result, indent=2))
        else:
            _format_probe_pending_output(result)

    except Exception as e:
        logger.error(f"Error probing pending models: {e}")
        ctx.exit(1)


def _format_probe_model_output(result):
    """Format probe model output for display."""
    logger.info(f"Model: {result['model_name']}")
    logger.info("=" * 50)

    if "error" in result:
        logger.info(f"Error: {result['error']}")
        return

    probe_result = result["probe_result"]
    logger.info(f"Status: {probe_result['status']}")
    logger.info(f"Message: {probe_result['message']}")

    if probe_result.get("details"):
        details = probe_result["details"]
        logger.info("\nDetails:")
        for key, value in details.items():
            if isinstance(value, (int, float)):
                logger.info(f"  {key}: {value}")
            else:
                logger.info(f"  {key}: {str(value)[:100]}")  # Limit long strings

    logger.info(f"\nRecommendation: {result['recommendation']}")


def _format_probe_pending_output(result):
    """Format probe pending output for display."""
    logger.info("Pending Models Probe Results")
    logger.info("=" * 50)
    logger.info(f"Total pending models: {result['total_models']}")
    logger.info(f"Probed models: {result['probed_models']}")

    if "status_updates" in result:
        logger.info(f"Status updates: {result['status_updates']}")

    if "probe_summary" in result:
        summary = result["probe_summary"]
        logger.info("\nProbe Summary:")
        for status, count in summary.items():
            if isinstance(count, int) and count > 0:
                logger.info(f"  {status}: {count}")

    if result.get("updated_models"):
        logger.info("\nUpdated Models:")
        for model in result["updated_models"]:
            logger.info(
                f"  {model['name']}: {model['old_status']} → {model['new_status']}"
            )

    if "results" in result:
        logger.info("\nDetailed Results:")
        for model_name, probe_result in result["results"].items():
            status = probe_result["status"]
            message = probe_result["message"]
            logger.info(f"  {model_name}: {status}")
            if status in ["exists_locally", "not_found"]:
                logger.info(f"    {message}")


if __name__ == "__main__":
    cli()
