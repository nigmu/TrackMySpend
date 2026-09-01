from ..core.logging import configure_logging, get_logger
from .connection import connect
from .schema import SCHEMA_STATEMENTS

logger = get_logger(__name__)


def migrate() -> None:
    conn = connect()
    try:
        with conn.cursor() as cur:
            for stmt in SCHEMA_STATEMENTS:
                cur.execute(stmt)
        conn.commit()
        logger.info("migrate complete (%s statements)", len(SCHEMA_STATEMENTS))
    except Exception:
        conn.rollback()
        logger.exception("migrate failed")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    configure_logging()
    migrate()
