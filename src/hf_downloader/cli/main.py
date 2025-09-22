"""
Main CLI entry point for HF Downloader.

This module provides the command-line interface for the HF Downloader application.
"""

import json
import logging
from typing import Any

import click

from ..services.integration_service import IntegrationService
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

    # Set up logging
    logging.basicConfig(level=getattr(logging, log_level.upper()))

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
                click.echo(
                    "\nPending models that will be downloaded on next scheduled run:"
                )
                _format_models_output(models["models"])

        success = daemon.start()
        if not success:
            click.echo("Failed to start daemon", err=True)
            ctx.exit(1)
    else:
        # Start daemon in background
        result = integration_service.safe_daemon_start(foreground=False)

        if result["status"] == "started":
            click.echo(f"Daemon started successfully with PID {result['pid']}")
        elif result["status"] == "already_running":
            click.echo(f"Daemon is already running (PID {result['pid']})")
        else:
            error_msg = result.get('error', 'Unknown error')
            stderr = result.get('stderr', '')
            if stderr:
                click.echo(f"Failed to start daemon: {error_msg}\nError details:\n{stderr}", err=True)
            else:
                click.echo(f"Failed to start daemon: {error_msg}", err=True)
            ctx.exit(1)


@cli.command()
@click.pass_context
def stop(ctx):
    """Stop the downloader daemon."""
    integration_service = ctx.obj["integration_service"]

    result = integration_service.safe_daemon_stop()

    if result["status"] == "stopped":
        click.echo(f"Daemon stopped successfully (PID {result['pid']})")
    elif result["status"] == "not_running":
        click.echo("Daemon is not running")
    else:
        click.echo(
            f"Failed to stop daemon: {result.get('error', 'Unknown error')}", err=True
        )
        ctx.exit(1)


@cli.command()
@click.option("--detailed", "-d", is_flag=True, help="Show detailed status")
@click.pass_context
def status(ctx, detailed):
    """Show daemon status."""
    integration_service = ctx.obj["integration_service"]

    result = integration_service.cli_integration.handle_daemon_status(detailed=detailed)

    if ctx.obj["output_format"] == "json":
        click.echo(json.dumps(result, indent=2))
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
            click.echo("Previous daemon stopped successfully")
        elif stop_result["status"] == "not_running":
            click.echo("No previous daemon was running")

        if start_result["status"] == "started":
            click.echo(
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
            click.echo(json.dumps(result["models"], indent=2))
        else:
            _format_models_output(result["models"])
    else:
        click.echo(f"Error: {result.get('error', 'Unknown error')}", err=True)
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
        click.echo(
            f"Model {model_name} added successfully with ID {result['model']['id']}"
        )
    elif result["status"] == "exists":
        click.echo(
            f"Model {model_name} already exists with status {result['model']['status']}"
        )
    else:
        click.echo(f"Error: {result.get('error', 'Unknown error')}", err=True)
        ctx.exit(1)


@models.command("remove")
@click.argument("model_name")
@click.pass_context
def remove_model(_ctx, model_name):
    """Remove a model from the download queue."""
    # This would require a delete method in DatabaseManager
    click.echo(f"Model {model_name} removal not yet implemented")


@models.command("sync")
@click.pass_context
def sync_models(ctx):
    """Synchronize model status between JSON and database."""
    integration_service = ctx.obj["integration_service"]

    result = integration_service.sync_models()

    if result["success"]:
        click.echo("Model synchronization completed successfully")
        click.echo(
            f"JSON to DB: {result['json_to_db']['added']} added, {result['json_to_db']['skipped']} skipped"
        )
        click.echo(
            f"DB to JSON: {result['db_to_json']['updated']} updated, {result['db_to_json']['unchanged']} unchanged"
        )

        if result["remaining_differences"] > 0:
            click.echo(
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
        click.echo(json.dumps(models_needing_sync, indent=2))
    else:
        if not models_needing_sync:
            click.echo("All models are synchronized")
            return

        click.echo("Models needing synchronization:")
        click.echo(
            f"{'Name':<40} {'JSON Status':<12} {'DB Status':<12} {'Priority':<10}"
        )
        click.echo("-" * 80)

        for model in models_needing_sync:
            name = model.get("name", "N/A")
            json_status = model.get("json_status", "N/A")
            db_status = model.get("db_status", "N/A")
            priority = model.get("priority", "medium")

            click.echo(f"{name:<40} {json_status:<12} {db_status:<12} {priority:<10}")


@models.command("update-status")
@click.argument("model_name")
@click.argument("status")
@click.pass_context
def update_model_status(ctx, model_name, status):
    """Update status of a specific model in JSON file."""
    integration_service = ctx.obj["integration_service"]

    result = integration_service.update_model_status_in_json(model_name, status)

    if result:
        click.echo(f"Updated {model_name} status to {status} in JSON file")
    else:
        click.echo(f"Failed to update {model_name} status", err=True)
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
            click.echo(json.dumps(result["schedules"], indent=2))
        else:
            _format_schedules_output(result["schedules"])
    else:
        click.echo(f"Error: {result.get('error', 'Unknown error')}", err=True)
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
        click.echo(
            f"Schedule '{name}' created successfully with ID {result['schedule']['id']}"
        )
    else:
        click.echo(f"Error: {result.get('error', 'Unknown error')}", err=True)
        ctx.exit(1)


@schedule.command("enable")
@click.argument("schedule_id", type=int)
@click.pass_context
def enable_schedule(ctx, schedule_id):
    """Enable a schedule."""
    integration_service = ctx.obj["integration_service"]

    result = integration_service.cli_integration.handle_schedule_enable(schedule_id)
    if result["status"] == "enabled":
        click.echo(f"Schedule {schedule_id} enabled successfully")
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
        click.echo(f"Schedule {schedule_id} disabled successfully")
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
        click.echo(f"Schedule {schedule_id} updated successfully")
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
        click.echo(f"Schedule {schedule_id} deleted successfully")
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
        click.echo("Schedule backup created successfully")
        click.echo(f"Backup timestamp: {result['timestamp']}")
        click.echo(f"Schedules backed up: {result['backup_count']}")
    else:
        click.echo(f"Error: {result.get('error', 'Unknown error')}", err=True)
        ctx.exit(1)


@schedule.command("restore")
@click.pass_context
def restore_schedules(ctx):
    """Restore schedules from backup."""
    integration_service = ctx.obj["integration_service"]

    result = integration_service.cli_integration.handle_schedule_restore()
    if result["status"] == "success":
        click.echo("Schedule restore completed successfully")
        click.echo(f"Backup timestamp: {result['backup_timestamp']}")
        click.echo(f"Schedules restored: {result['restored_count']}")
    else:
        click.echo(f"Error: {result.get('error', 'Unknown error')}", err=True)
        ctx.exit(1)


@cli.command()
@click.pass_context
def download(ctx):
    """Trigger a manual download run."""
    integration_service = ctx.obj["integration_service"]

    result = integration_service.safe_manual_download()

    if result["status"] == "triggered":
        click.echo("Manual download triggered successfully")
        click.echo(f"Schedule: {result['schedule']['name']}")
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
            click.echo(json.dumps(result, indent=2))
        else:
            _format_sessions_output(
                result["sessions"],
                result.get("filter_model"),
                result.get("filter_status"),
            )
    else:
        click.echo(f"Error: {result.get('error', 'Unknown error')}", err=True)
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
            click.echo(json.dumps(result, indent=2))
        else:
            _format_session_details_output(result)
    else:
        click.echo(f"Error: {result.get('error', 'Unknown error')}", err=True)
        ctx.exit(1)


@sessions.command("cancel")
@click.argument("session_id", type=int)
@click.pass_context
def cancel_session(ctx, session_id):
    """Cancel a download session."""
    integration_service = ctx.obj["integration_service"]

    result = integration_service.cli_integration.handle_session_cancel(session_id)

    if result["status"] == "cancelled":
        click.echo(f"Session {session_id} cancelled successfully")
        click.echo(f"Model: {result['model']}")
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
        click.echo("Retry session created successfully")
        click.echo(f"Original session: {result['original_session_id']}")
        click.echo(f"New session: {result['new_session_id']}")
        click.echo(f"Model: {result['model']}")
        click.echo(f"Retry count: {result['retry_count']}")
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
        click.echo("Session cleanup completed successfully")
        click.echo(f"Deleted {result['deleted_count']} old sessions")
        click.echo(f"Kept sessions from last {days} days")
    else:
        click.echo(f"Error: {result.get('error', 'Unknown error')}", err=True)
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
            click.echo(json.dumps(result, indent=2))
        else:
            _format_statistics_output(result)
    else:
        click.echo(f"Error: {result.get('error', 'Unknown error')}", err=True)
        ctx.exit(1)


def _format_status_output(result: dict[str, Any], detailed: bool):
    """Format status output for table display."""
    status = result.get("status", "unknown")

    if status == "running":
        pid = result.get("pid", "unknown")
        uptime = result.get("uptime", "unknown")
        click.echo(f"Daemon is running (PID: {pid})")
        click.echo(f"Uptime: {uptime}")

        if detailed:
            memory = result.get("memory_usage")
            if memory:
                click.echo(f"Memory: {memory.get('rss_formatted', 'N/A')}")
                click.echo(f"CPU: {result.get('cpu_usage', 0):.1f}%")
    elif status == "stopped":
        click.echo("Daemon is not running")
    else:
        click.echo(f"Status: {status}")


def _format_models_output(models):
    """Format models output for table display."""
    if not models:
        click.echo("No models found")
        return

    click.echo(f"{'ID':<5} {'Name':<40} {'Status':<12} {'Size':<10} {'Created':<20}")
    click.echo("-" * 90)

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

        click.echo(
            f"{model_id:<5} {model_name:<40} {model_status:<12} {size_str:<10} {created_str:<20}"
        )


def _format_schedules_output(schedules):
    """Format schedules output for table display."""
    if not schedules:
        click.echo("No schedules found")
        return

    click.echo(
        f"{'ID':<5} {'Name':<20} {'Type':<8} {'Time':<8} {'Day':<5} {'Enabled':<8} {'Concurrent':<10}"
    )
    click.echo("-" * 70)

    for schedule in schedules:
        day_str = (
            str(schedule.day_of_week) if schedule.day_of_week is not None else "N/A"
        )
        enabled_str = "Yes" if schedule.enabled else "No"
        click.echo(
            f"{schedule.id:<5} {schedule.name:<20} {schedule.type:<8} {schedule.time:<8} {day_str:<5} {enabled_str:<8} {schedule.max_concurrent_downloads:<10}"
        )


def _format_sessions_output(sessions, filter_model=None, filter_status=None):
    """Format sessions output for table display."""
    if not sessions:
        click.echo("No sessions found")
        return

    # Show filter information
    if filter_model or filter_status:
        filter_info = []
        if filter_model:
            filter_info.append(f"Model: {filter_model}")
        if filter_status:
            filter_info.append(f"Status: {filter_status}")
        click.echo(f"Filtered by: {', '.join(filter_info)}")
        click.echo()

    click.echo(
        f"{'ID':<5} {'Model ID':<8} {'Status':<12} {'Progress':<10} {'Downloaded':<12} {'Total':<10} {'Started':<20}"
    )
    click.echo("-" * 85)

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

        click.echo(
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

    click.echo("Session Details")
    click.echo("=" * 50)
    click.echo(f"Session ID: {session['id']}")
    click.echo(f"Model: {model['name']} (ID: {session['model_id']})")
    click.echo(f"Status: {session['status']}")
    click.echo(f"Progress: {progress:.1f}%")
    click.echo(f"Downloaded: {session['bytes_downloaded'] / 1024 / 1024:.1f}MB")
    click.echo(
        f"Total Size: {session['total_bytes'] / 1024 / 1024:.1f}MB"
        if session["total_bytes"]
        else "Total Size: N/A"
    )

    if duration:
        click.echo(f"Duration: {duration:.1f} seconds")
    if speed_bps > 0:
        click.echo(f"Download Speed: {speed_mbps:.2f} Mbps")

    click.echo(f"Retry Count: {session['retry_count']}")
    click.echo(
        f"Started: {session['started_at'][:19] if session['started_at'] else 'N/A'}"
    )
    click.echo(
        f"Completed: {session['completed_at'][:19] if session['completed_at'] else 'N/A'}"
    )

    if session.get("error_message"):
        click.echo(f"Error: {session['error_message']}")

    if session.get("schedule_id"):
        click.echo(f"Schedule ID: {session['schedule_id']}")


def _format_statistics_output(stats):
    """Format statistics output for table display."""
    click.echo("Download Statistics")
    click.echo("=" * 50)

    click.echo("Sessions Summary:")
    click.echo(f"  Total Sessions: {stats['total_sessions']}")
    click.echo(f"  Completed: {stats['completed_sessions']}")
    click.echo(f"  Failed: {stats['failed_sessions']}")
    click.echo(f"  Cancelled: {stats['cancelled_sessions']}")
    click.echo(f"  Currently Active: {stats['active_sessions']}")
    click.echo(f"  Success Rate: {stats['success_rate']}%")

    click.echo("\nData Transfer:")
    click.echo(
        f"  Total Downloaded: {stats['total_bytes_downloaded'] / 1024 / 1024 / 1024:.2f} GB"
    )
    click.echo(
        f"  Total Requested: {stats['total_bytes_requested'] / 1024 / 1024 / 1024:.2f} GB"
    )
    click.echo(f"  Completion Rate: {stats['completion_rate']}%")

    if stats["average_download_speed_bps"] > 0:
        click.echo(f"  Average Speed: {stats['average_download_speed_mbps']:.2f} Mbps")

    if stats.get("current_active_downloads", 0) > 0:
        click.echo(
            f"\nCurrently Downloading: {stats['current_active_downloads']} models"
        )
        for model in stats.get("current_downloading_models", []):
            click.echo(f"  - {model}")

    if stats.get("total_models_tracked", 0) > 0:
        click.echo(f"\nTotal Models Tracked: {stats['total_models_tracked']}")


if __name__ == "__main__":
    cli()
