"""Explicit migration for persistent veterinary uploads; shares the existing migration ledger."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import migrate_veterinary as migration

VERSION = '20261106_veterinary_uploads'


def migrate(connection, *, down=False):
    previous = migration.VERSION
    try:
        migration.VERSION = VERSION
        return migration.migrate(connection, down=down)
    finally:
        migration.VERSION = previous


if __name__ == '__main__':
    import argparse
    import os
    import psycopg2
    from dotenv import load_dotenv
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--down', action='store_true')
    args = parser.parse_args()
    load_dotenv(migration.ROOT / '.env')
    with psycopg2.connect(host=os.environ['DB_HOST'], port=os.getenv('DB_PORT','5432'),
                         dbname=os.environ['DB_NAME'], user=os.environ['DB_USER'], password=os.environ['DB_PASS']) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1 FROM nextris.veterinary_schema_migration WHERE version='20261106_veterinary'")
            if not cursor.fetchone(): raise SystemExit('Apply the veterinary base migration first')
        print('Changed:', migrate(connection, down=args.down)) if args.apply else print('Preflight passed; use --apply. No changes applied.')
