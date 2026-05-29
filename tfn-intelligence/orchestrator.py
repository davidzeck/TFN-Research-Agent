"""
Orchestrator — main controller for the TFN Sector Intelligence pipeline.

Usage:
  python orchestrator.py --run-now      # single run then exit
  python orchestrator.py --schedule     # run daily at 07:00 EAT (for VPS / systemd)
  python orchestrator.py --test-email   # send current workbook without fetching
"""

import argparse
import logging
import os
import sys
import time
from datetime import datetime
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

load_dotenv()

from config import LOG_DIR, SEND_DAY, SEND_TIME_EAT, WORKBOOK_PATH
from agents import io_agent, summarizer_agent, excel_agent

EAT = ZoneInfo("Africa/Nairobi")


def _setup_logging() -> None:
    os.makedirs(LOG_DIR, exist_ok=True)
    log_file = os.path.join(LOG_DIR, f"run-{datetime.now().strftime('%Y-%m-%d')}.log")
    fmt = "[%(asctime)s] %(levelname)s %(name)s: %(message)s"
    datefmt = "%H:%M:%S"
    logging.basicConfig(
        level=logging.INFO,
        format=fmt,
        datefmt=datefmt,
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )


logger = logging.getLogger("orchestrator")


def run_daily() -> None:
    """Execute the full pipeline: fetch → summarize → write → (Friday) deliver."""
    start = datetime.now()
    logger.info("=== Run started at %s ===", start.strftime("%Y-%m-%d %H:%M:%S"))

    # --- Fetch ---
    try:
        articles = io_agent.fetch_all_articles()
    except Exception as exc:
        logger.error("I/O Agent fetch crashed: %s", exc, exc_info=True)
        articles = []

    logger.info("Fetched %d articles", len(articles))

    # --- Summarize + Write ---
    written = 0
    skipped_summary = 0
    skipped_dup = 0

    for article in articles:
        try:
            row = summarizer_agent.process(article)
        except Exception as exc:
            logger.error("Summarizer crashed on '%s': %s", article.get("title", ""), exc, exc_info=True)
            skipped_summary += 1
            continue

        if row is None:
            skipped_summary += 1
            continue

        try:
            was_written = excel_agent.write_row(row)
        except Exception as exc:
            logger.error("Excel agent crashed writing '%s': %s", row.get("headline", ""), exc, exc_info=True)
            continue

        if was_written:
            written += 1
        else:
            skipped_dup += 1

    logger.info(
        "Summary: %d written | %d duplicates skipped | %d summarizer failures",
        written, skipped_dup, skipped_summary,
    )
    logger.info("Workbook total rows: %d", excel_agent.get_row_count())

    # --- Friday delivery (based on EAT, not host-local time) ---
    today = datetime.now(EAT).strftime("%A")
    if today == SEND_DAY:
        logger.info("Today is %s — sending workbook to recipients", SEND_DAY)
        try:
            success = io_agent.deliver_workbook(WORKBOOK_PATH)
            if not success:
                logger.error("Email delivery failed — check logs above")
        except Exception as exc:
            logger.error("Delivery crashed: %s", exc, exc_info=True)
    else:
        logger.info("Today is %s — skipping email (sends on %s)", today, SEND_DAY)

    elapsed = (datetime.now() - start).seconds
    logger.info("=== Run complete. Duration: %ds ===\n", elapsed)


def run_test_email() -> None:
    """Skip fetch/summarize — just deliver the current workbook for credential testing."""
    logger.info("Test email mode — sending current workbook")
    success = io_agent.deliver_workbook(WORKBOOK_PATH)
    if success:
        logger.info("Test email delivered successfully")
    else:
        logger.error("Test email failed — check GMAIL_SENDER and GMAIL_APP_PASSWORD in .env")


def _sentinel_path(eat_date: str) -> str:
    return os.path.join(LOG_DIR, f"ran-{eat_date}.sentinel")


def run_scheduler() -> None:
    """Run the pipeline once per day at SEND_TIME_EAT, anchored to Africa/Nairobi.

    Timezone-independent: behaves identically regardless of the host's local
    timezone. A per-day sentinel makes runs idempotent, so a process restart
    (e.g. systemd Restart=on-failure) never triggers a duplicate run or email.
    """
    os.makedirs(LOG_DIR, exist_ok=True)
    send_hour, send_minute = map(int, SEND_TIME_EAT.split(":"))

    logger.info("Scheduler started. Will run daily at %s EAT (Africa/Nairobi)", SEND_TIME_EAT)

    while True:
        now = datetime.now(EAT)
        today = now.strftime("%Y-%m-%d")
        sentinel = _sentinel_path(today)
        due = (now.hour, now.minute) >= (send_hour, send_minute)

        if due and not os.path.exists(sentinel):
            logger.info("Daily run due for %s EAT — starting", today)
            try:
                run_daily()
            finally:
                # Mark the day done even if the run raised, so we don't loop-retry
                # a hard failure every 30s. The next attempt is tomorrow.
                open(sentinel, "w").close()

        time.sleep(30)


def main() -> None:
    _setup_logging()
    parser = argparse.ArgumentParser(description="TFN Sector Intelligence Orchestrator")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--run-now", action="store_true", help="Execute one full pipeline run and exit")
    group.add_argument("--schedule", action="store_true", help="Start daily scheduler (for VPS / systemd)")
    group.add_argument("--test-email", action="store_true", help="Send current workbook without fetching")
    args = parser.parse_args()

    if args.run_now:
        run_daily()
    elif args.schedule:
        run_scheduler()
    elif args.test_email:
        run_test_email()


if __name__ == "__main__":
    main()
