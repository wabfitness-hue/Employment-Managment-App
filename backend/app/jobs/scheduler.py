"""
Standalone daily scheduler.

Runs as its OWN single-instance container (see the `scheduler` service in
docker-compose) rather than inside the web process — the API runs multiple
uvicorn workers, so an in-process timer would fire the job once per worker and
send duplicate emails. Keeping it separate guarantees exactly one run per day.

Currently: contract-expiry alert sweep once daily at RUN_HOUR (container time).
"""
import asyncio
import logging
from datetime import datetime, timedelta

from app.database import SessionLocal
from app.services.contracts import send_expiry_alerts

logging.basicConfig(level=logging.INFO, format="%(asctime)s [scheduler] %(message)s")
log = logging.getLogger("scheduler")

RUN_HOUR = 7  # 07:00 container-local time


async def run_expiry_sweep() -> None:
    db = SessionLocal()
    try:
        result = await send_expiry_alerts(db)
        log.info("expiry alert sweep complete: %s", result)
    except Exception:
        log.exception("expiry alert sweep failed")
    finally:
        db.close()


def _seconds_until_next_run() -> float:
    now = datetime.now()
    nxt = now.replace(hour=RUN_HOUR, minute=0, second=0, microsecond=0)
    if nxt <= now:
        nxt += timedelta(days=1)
    return (nxt - now).total_seconds()


async def main() -> None:
    log.info("scheduler started — daily expiry sweep at %02d:00 container time", RUN_HOUR)
    while True:
        wait = _seconds_until_next_run()
        log.info("next expiry sweep in %.1f hours", wait / 3600)
        await asyncio.sleep(wait)
        await run_expiry_sweep()


if __name__ == "__main__":
    asyncio.run(main())
