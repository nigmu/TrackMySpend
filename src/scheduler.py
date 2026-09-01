import asyncio

from .core.config import POLLER_TICK_SEC
from .core.logging import get_logger
from .db.connection import connect
from .ingestion.service import run_due_accounts

logger = get_logger(__name__)


def _tick() -> None:
    conn = connect()
    try:
        run_due_accounts(conn)
        conn.commit()
    except Exception:
        conn.rollback()
        logger.exception("poller tick failed")
    finally:
        conn.close()


async def poller_loop() -> None:
    logger.info("poller started tick_sec=%s", POLLER_TICK_SEC)
    while True:
        await asyncio.sleep(POLLER_TICK_SEC)
        try:
            await asyncio.to_thread(_tick)
        except asyncio.CancelledError:
            logger.info("poller stopped")
            raise
        except Exception:
            logger.exception("poller loop error")
