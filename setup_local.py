"""
setup_local.py - One-shot local database setup for FleetGuard.

Run ONCE before starting the backend:
    python setup_local.py

What it does:
  1. Connects to local PostgreSQL as 'postgres' superuser
  2. Creates the 'fleetguard' role + database
  3. Applies database/schema.sql
  4. Seeds all data (machines, telemetry, predictions, alerts)
"""

import os
import sys
import getpass
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

PG_HOST   = "localhost"
PG_PORT   = 5432
FG_USER   = "fleetguard"
FG_PASS   = "fleetguard"
FG_DB     = "fleetguard"

ROOT        = os.path.dirname(os.path.abspath(__file__))
SCHEMA_FILE = os.path.join(ROOT, "database", "schema.sql")


def superconn(pwd: str):
    return psycopg2.connect(
        host=PG_HOST, port=PG_PORT,
        dbname="postgres", user="postgres",
        password=pwd, connect_timeout=5,
    )


def step1_create_role_db(pwd: str):
    print("\n[1/3] Creating role and database...")
    conn = superconn(pwd)
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cur = conn.cursor()

    cur.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (FG_USER,))
    if not cur.fetchone():
        cur.execute(f"CREATE ROLE {FG_USER} WITH LOGIN PASSWORD %s", (FG_PASS,))
        print(f"  + Created role '{FG_USER}'")
    else:
        print(f"  - Role '{FG_USER}' already exists")

    cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (FG_DB,))
    if not cur.fetchone():
        cur.execute(f"CREATE DATABASE {FG_DB} OWNER {FG_USER}")
        print(f"  + Created database '{FG_DB}'")
    else:
        print(f"  - Database '{FG_DB}' already exists")

    cur.close()
    conn.close()


def step2_apply_schema():
    print("\n[2/3] Applying schema...")
    conn = psycopg2.connect(
        host=PG_HOST, port=PG_PORT,
        dbname=FG_DB, user=FG_USER, password=FG_PASS,
    )
    with open(SCHEMA_FILE) as f:
        sql = f.read()
    cur = conn.cursor()
    cur.execute(sql)
    conn.commit()
    cur.close()
    conn.close()
    print("  + Schema applied")


def step3_seed():
    print("\n[3/3] Seeding data...")
    sys.path.insert(0, ROOT)
    os.environ["DATABASE_URL"] = (
        f"postgresql://{FG_USER}:{FG_PASS}@{PG_HOST}:{PG_PORT}/{FG_DB}"
    )
    from database.seed_db import seed
    seed()


def main():
    print("=" * 55)
    print("  FleetGuard — Local Database Setup")
    print("=" * 55)
    print(f"\nTarget: postgresql://postgres@{PG_HOST}:{PG_PORT}")

    # Try common passwords before prompting
    pg_pass = None
    for attempt, pwd in enumerate(["", "postgres", "admin", None]):
        if pwd is None:
            pwd = getpass.getpass(
                "\nEnter your PostgreSQL 'postgres' superuser password: "
            )
        try:
            superconn(pwd).close()
            pg_pass = pwd
            print("  Connected to PostgreSQL successfully")
            break
        except psycopg2.OperationalError as e:
            if attempt < 3:
                continue
            print(f"\n  ERROR: {e}")
            print(
                "\n  Hint: Make sure PostgreSQL is running on port 5432\n"
                "  and that your 'postgres' user password is correct."
            )
            sys.exit(1)

    step1_create_role_db(pg_pass)
    step2_apply_schema()
    step3_seed()

    print("\n" + "=" * 55)
    print("  Setup complete! Start the project:")
    print()
    print("  Terminal 1 (backend):")
    print("    cd backend")
    print("    uvicorn app.main:app --reload --port 8000")
    print()
    print("  Terminal 2 (frontend):")
    print("    cd frontend")
    print("    npm run dev")
    print()
    print("  Open: http://localhost:5173")
    print("=" * 55)


if __name__ == "__main__":
    main()
