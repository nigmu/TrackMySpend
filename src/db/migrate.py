from ..core.logging import configure_logging, get_logger
from .connection import connect
from .schema import POST_SCHEMA_STATEMENTS, SCHEMA_STATEMENTS

logger = get_logger(__name__)


def migrate() -> None:
    conn = connect()
    statements = [*POST_SCHEMA_STATEMENTS[:1], *SCHEMA_STATEMENTS, *POST_SCHEMA_STATEMENTS[1:]]
    try:
        with conn.cursor() as cur:
            for stmt in statements:
                cur.execute(stmt)
        conn.commit()
        logger.info("migrate complete (%s statements)", len(statements))
    except Exception:
        conn.rollback()
        logger.exception("migrate failed")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    configure_logging()
    migrate()
