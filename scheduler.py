"""Nightly job: extract ERP snapshot -> run risk model -> refresh dashboard CSVs.
Run and leave open:  python scheduler.py
(Or skip the scheduler and trigger `python scheduler.py --now` from Windows Task Scheduler / cron.)
"""
import logging, sys
from apscheduler.schedulers.blocking import BlockingScheduler
import risk_model, build_dashboard_data

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                    handlers=[logging.FileHandler("scheduler.log"), logging.StreamHandler()])
log = logging.getLogger("scheduler")


def nightly_job():
    log.info("Nightly run started")
    try:
        # TODO (real ERP): call your extractor here to load fresh inventory snapshots into the DB
        build_dashboard_data.main(regenerate=False)     # re-score existing data + refresh CSVs
        log.info("Nightly run finished OK")
    except Exception:
        log.exception("Nightly run FAILED")


if __name__ == "__main__":
    if "--now" in sys.argv:
        nightly_job()
    else:
        sched = BlockingScheduler()
        sched.add_job(nightly_job, "cron", hour=2, minute=0)    # every night at 02:00
        log.info("Scheduler running: model runs nightly at 02:00. Ctrl+C to stop.")
        sched.start()
