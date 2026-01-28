"""
Report Scheduler for HorecaMark.

Schedules daily report generation and email notifications.
"""

import signal
import sys
import time
from datetime import datetime, time as dt_time
from threading import Event

import schedule

from scraper.utils.config import Config
from scraper.utils.logger import get_logger
from scraper.utils.notifier import send_simple_report
from scraper.utils.reporter import ExcelReporter

logger = get_logger("scheduler")

# Global event for graceful shutdown
_shutdown_event = Event()


def generate_and_send_report() -> None:
    """Generate report and send email."""
    if _shutdown_event.is_set():
        return

    try:
        logger.info("Starting scheduled report generation...")

        # Generate report
        reporter = ExcelReporter()
        report_path = reporter.generate_daily_report()

        # Clean up old reports
        removed = reporter.cleanup_old_reports(keep_days=30)
        if removed:
            logger.info(f"Cleaned up {len(removed)} old reports")

        # Send email
        logger.info("Sending report email...")
        success = send_simple_report()

        if success:
            logger.info("Daily report sent successfully")
        else:
            logger.warning("Failed to send report email")

    except Exception as e:
        logger.error(f"Error generating scheduled report: {e}", exc_info=True)


def schedule_daily_report(report_time: str = None) -> schedule.Job:
    """Schedule daily report generation.

    Args:
        report_time: Time to run report in HH:MM format (default: from Config)

    Returns:
        schedule.Job instance
    """
    if report_time is None:
        report_time = Config.SCRAPE_TIME

    try:
        hour, minute = map(int, report_time.split(":"))
        schedule_time = dt_time(hour=hour, minute=minute)
    except ValueError:
        logger.error(f"Invalid time format: {report_time}. Using default 08:00")
        schedule_time = dt_time(hour=8, minute=0)

    job = schedule.every().day.at(report_time).do(generate_and_send_report)

    logger.info(f"Scheduled daily report for {report_time}")
    return job


def schedule_weekly_report(weekday: int = 0, report_time: str = None) -> schedule.Job:
    """Schedule weekly report generation.

    Args:
        weekday: Day of week (0=Monday, 6=Sunday)
        report_time: Time to run report in HH:MM format

    Returns:
        schedule.Job instance
    """
    if report_time is None:
        report_time = Config.SCRAPE_TIME

    job = schedule.every().week.at(report_time).do(generate_and_send_report)

    logger.info(f"Scheduled weekly report for {report_time} on weekday {weekday}")
    return job


def schedule_hourly_report() -> schedule.Job:
    """Schedule hourly report generation (for testing/frequent updates).

    Returns:
        schedule.Job instance
    """
    job = schedule.every().hour.do(generate_and_send_report)
    logger.info("Scheduled hourly report")
    return job


def run_scheduler() -> None:
    """Run the scheduler loop.

    This function blocks until interrupted.
    """
    # Schedule default daily report
    schedule_daily_report()

    # Setup signal handlers for graceful shutdown
    def signal_handler(signum, frame):
        logger.info(f"Received signal {signum}, shutting down...")
        _shutdown_event.set()
        schedule.clear()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    logger.info("Scheduler started. Press Ctrl+C to stop.")

    # Run scheduler loop
    while not _shutdown_event.is_set():
        try:
            schedule.run_pending()
            time.sleep(1)
        except KeyboardInterrupt:
            break
        except Exception as e:
            logger.error(f"Error in scheduler loop: {e}", exc_info=True)
            time.sleep(60)  # Wait before retry

    logger.info("Scheduler stopped")


def run_once() -> None:
    """Run report generation once and exit.

    Useful for testing or cron-based execution.
    """
    logger.info("Running single report generation...")
    generate_and_send_report()
    logger.info("Report generation complete")


def run_scheduler_once(report_time: str = None) -> None:
    """Run scheduler until next report time, then exit.

    Args:
        report_time: Time to run report (default: from Config)
    """
    schedule_daily_report(report_time)

    logger.info(f"Waiting for scheduled time {report_time or Config.SCRAPE_TIME}...")

    while not _shutdown_event.is_set():
        try:
            schedule.run_pending()

            # Check if job ran today
            if schedule.next_run() is None:
                logger.info("Scheduled job completed, exiting...")
                break

            time.sleep(60)

        except KeyboardInterrupt:
            break
        except Exception as e:
            logger.error(f"Error in scheduler: {e}", exc_info=True)
            time.sleep(60)


def list_scheduled_jobs() -> list[str]:
    """List all scheduled jobs.

    Returns:
        List of job descriptions
    """
    jobs = []
    for job in schedule.jobs:
        jobs.append(str(job))
    return jobs


def clear_scheduled_jobs() -> None:
    """Clear all scheduled jobs."""
    schedule.clear()
    logger.info("All scheduled jobs cleared")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="HorecaMark Report Scheduler")
    parser.add_argument(
        "command",
        choices=["run", "once", "list", "clear"],
        help="Command to execute",
        nargs="?",
        default="run",
    )
    parser.add_argument(
        "--time",
        type=str,
        help="Report time in HH:MM format",
    )

    args = parser.parse_args()

    if args.command == "run":
        run_scheduler()
    elif args.command == "once":
        run_once()
    elif args.command == "list":
        jobs = list_scheduled_jobs()
        if jobs:
            print("Scheduled jobs:")
            for job in jobs:
                print(f"  - {job}")
        else:
            print("No jobs scheduled")
    elif args.command == "clear":
        clear_scheduled_jobs()
