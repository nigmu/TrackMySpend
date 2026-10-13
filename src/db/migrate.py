from ..core.logging import configure_logging, get_logger
from ..sms.db import rehash_sms_content_hashes
from .connection import connect, set_database_timezone
from .schema import POST_SCHEMA_STATEMENTS, SCHEMA_STATEMENTS

logger = get_logger(__name__)


def migrate() -> None:
    conn = connect()
    # POST_SCHEMA_STATEMENTS is split around SCHEMA_STATEMENTS on purpose:
    # [0] is the raw_sms -> raw_sms_data rename, which must run BEFORE
    # "CREATE TABLE IF NOT EXISTS raw_sms_data" (else the CREATE wins the race
    # and the rename becomes a no-op, orphaning the old table's data).
    # [1:] are column adds/backfills/constraints that must run AFTER the table
    # exists in its final shape. See schema.py for the full comment.
    statements = [*POST_SCHEMA_STATEMENTS[:1], *SCHEMA_STATEMENTS, *POST_SCHEMA_STATEMENTS[1:]]
    try:
        with conn.cursor() as cur:
            for stmt in statements:
                cur.execute(stmt)
        deleted = rehash_sms_content_hashes(conn)
        conn.commit()
        set_database_timezone()
        logger.info(
            "migrate complete (%s statements, sms rehash deleted_dupes=%s)",
            len(statements),
            deleted,
        )
    except Exception:
        conn.rollback()
        logger.exception("migrate failed")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    configure_logging()
    migrate()
