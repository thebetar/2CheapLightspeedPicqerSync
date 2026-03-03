#!/usr/bin/env python3

import schedule
import time

from main import run_sync
from modules.config import log


if __name__ == "__main__":
    schedule.every().day.at("06:00").do(run_sync)
    schedule.every().day.at("10:00").do(run_sync)
    schedule.every().day.at("14:00").do(run_sync)
    schedule.every().day.at("20:00").do(run_sync)

    log.info("Scheduler started. Syncs at 06:00, 10:00, 14:00, 20:00")
    log.info("Next run: %s", schedule.next_run())

    while True:
        schedule.run_pending()
        time.sleep(60)
