"""The background worker: scheduled sync, reminders and heartbeat.

    python -m app.worker

A plain 60-second loop rather than a scheduler. SRS 7.5 specifies a tick
every 60 seconds and FR-REM-03 repeats it, so a scheduler would add a
dependency and an abstraction to fake in tests, for nothing. `run_once` takes
the clock as an argument, which is what makes the six acceptance cases in
SRS 5.4 testable.

Exactly one replica may run: both the sync and the reminder log guard
themselves, but two workers would double the Kite calls for nothing.
"""

from __future__ import annotations

import datetime as dt
import logging
import signal
import time
from dataclasses import dataclass, field
from types import FrameType

import httpx
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import SessionLocal
from app.logging_config import configure_logging
from app.services import holidays, reminders, sync_service, token_store
from app.timezone import IST, ist_date, now_utc

logger = logging.getLogger("tj.worker")


@dataclass
class WorkerState:
    """What the loop has to remember between ticks."""

    last_heartbeat: dt.datetime | None = None
    sync_attempted_on: dt.date | None = None
    actions: list[str] = field(default_factory=list)


def scheduled_sync_time() -> dt.time:
    raw = get_settings().scheduled_sync_time_ist
    hour, minute = (int(part) for part in raw.split(":"))
    return dt.time(hour, minute)


def sync_is_due(now: dt.datetime, state: WorkerState, grace_minutes: int = 30) -> bool:
    """Whether the scheduled sync should run (FR-SYNC-02).

    Once per day, after the configured time, inside a grace window so a
    worker started at 18:00 does not fire the 15:45 sync as if it were now.
    """
    day = ist_date(now)
    if state.sync_attempted_on == day:
        return False

    local = now.astimezone(IST)
    due = local.replace(
        hour=scheduled_sync_time().hour,
        minute=scheduled_sync_time().minute,
        second=0,
        microsecond=0,
    )
    return due <= local <= due + dt.timedelta(minutes=grace_minutes)


def run_scheduled_sync(session: Session, now: dt.datetime, state: WorkerState) -> str | None:
    """The 15:45 sync, if a token exists. No token means a logged skip and a
    missed-sync alert from the reminder slots (FR-SYNC-06, FR-REM-08)."""
    if not holidays.is_trading_day(session, ist_date(now)):
        return None
    if not sync_is_due(now, state):
        return None

    state.sync_attempted_on = ist_date(now)

    account = token_store.get_account(session)
    if account is None:
        return "sync:not_configured"

    try:
        result = sync_service.run_sync(session, trigger="scheduled")
    except sync_service.AlreadyRunning:
        return "sync:already_running"
    except Exception:
        session.rollback()
        logger.error("Scheduled sync failed", extra={"event": "worker_sync_failed"})
        return "sync:failed"

    logger.info(
        "Scheduled sync finished",
        extra={"event": "worker_sync_done", "count": result.fills_new},
    )
    return f"sync:{result.status}"


def beat(state: WorkerState, now: dt.datetime, timeout: float = 10.0) -> bool:
    """Ping the external heartbeat (NFR-07).

    Reminders are only trustworthy if a dead worker is noticed, and nothing
    inside this process can report its own death.
    """
    settings = get_settings()
    url = settings.heartbeat_url
    if not url or url.endswith("<uuid>"):
        return False

    if state.last_heartbeat is not None:
        elapsed = (now - state.last_heartbeat).total_seconds()
        if elapsed < settings.heartbeat_every_seconds:
            return False

    state.last_heartbeat = now
    try:
        httpx.get(url, timeout=timeout)
    except httpx.HTTPError:
        logger.warning("Heartbeat ping failed", extra={"event": "worker_heartbeat_failed"})
        return False
    return True


def run_once(session: Session, now: dt.datetime, state: WorkerState) -> list[str]:
    """One tick. Pure with respect to time: everything reads `now`."""
    actions: list[str] = []

    if beat(state, now):
        actions.append("heartbeat")

    synced = run_scheduled_sync(session, now, state)
    if synced:
        actions.append(synced)

    actions.extend(reminders.tick(session, now))
    return actions


class Worker:
    def __init__(self) -> None:
        self.state = WorkerState()
        self.running = True

    def stop(self, signum: int, frame: FrameType | None) -> None:
        logger.info("Worker stopping", extra={"event": "worker_stop"})
        self.running = False

    def tick(self) -> list[str]:
        session = SessionLocal()
        try:
            actions = run_once(session, now_utc(), self.state)
            session.commit()
            return actions
        except Exception:
            session.rollback()
            logger.exception("Worker tick failed", extra={"event": "worker_tick_failed"})
            return ["error"]
        finally:
            session.close()

    def run(self) -> None:
        settings = get_settings()
        configure_logging()
        signal.signal(signal.SIGTERM, self.stop)
        signal.signal(signal.SIGINT, self.stop)

        logger.info(
            "Worker started",
            extra={"event": "worker_start", "count": settings.worker_tick_seconds},
        )

        while self.running:
            started = time.monotonic()
            actions = self.tick()
            if actions:
                logger.info(
                    "Worker tick", extra={"event": "worker_tick", "path": ",".join(actions)}
                )

            # Sleep in short slices so SIGTERM is answered promptly rather
            # than up to a minute later.
            remaining = settings.worker_tick_seconds - (time.monotonic() - started)
            while self.running and remaining > 0:
                time.sleep(min(1.0, remaining))
                remaining -= 1.0


def main() -> int:
    Worker().run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
