"""
Entrypoint for running the seeder inside Docker.
Retries the DB connection until it's ready.
"""

import time
import sys
import os

# Wait for PostgreSQL to be ready
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def wait_for_db(max_retries=30):
    import psycopg2
    import re
    db_url = os.getenv("DATABASE_URL", "postgresql://fleetguard:fleetguard@localhost:5432/fleetguard")
    m = re.match(r"postgresql://(\w+):(\w+)@([\w.]+):(\d+)/(\w+)", db_url)
    if not m:
        raise ValueError(f"Cannot parse DATABASE_URL: {db_url}")
    user, password, host, port, dbname = m.groups()

    for attempt in range(max_retries):
        try:
            conn = psycopg2.connect(host=host, port=port, dbname=dbname, user=user, password=password)
            conn.close()
            print(f"Database ready after {attempt+1} attempt(s)")
            return
        except Exception as e:
            print(f"Waiting for DB... ({attempt+1}/{max_retries}): {e}")
            time.sleep(2)
    raise RuntimeError("Could not connect to the database")


if __name__ == "__main__":
    wait_for_db()
    from seed_db import seed
    seed()
