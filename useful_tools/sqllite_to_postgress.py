import sqlite3
import psycopg

SQLITE_DB = "C:/NPersonal/Projects/TrackMySpend/DB/data/trackmyspend.db"
PG_URL = "postgresql://postgres:nigmu@localhost:5432/trackmyspend"

TABLES = [
    "email_accounts",
    "email_ingest_staging",
    "email_parse_queue_staging"
]

sqlite_conn = sqlite3.connect(SQLITE_DB)
sqlite_conn.row_factory = sqlite3.Row

pg_conn = psycopg.connect(PG_URL)

with pg_conn:
    with pg_conn.cursor() as pg_cur:
        for table in TABLES:
            s_cur = sqlite_conn.execute(f"SELECT * FROM {table}")
            cols = [col[0] for col in s_cur.description]

            col_list = ", ".join(cols)
            placeholders = ", ".join(["%s"] * len(cols))

            insert_sql = f"INSERT INTO {table} ({col_list}) VALUES ({placeholders})"

            for row in s_cur:
                values = []
                for c in cols:
                    v = row[c]
            
                    # Fix boolean fields
                    if c == "is_active" and v is not None:
                        v = bool(v)
            
                    values.append(v)
            
                pg_cur.execute(insert_sql, values)

print("done")