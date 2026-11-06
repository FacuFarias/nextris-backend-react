"""Explicit, locked and reversible veterinary migration. Never launches application workers."""
import argparse
import os
from pathlib import Path
import psycopg2
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
VERSION = '20261106_veterinary'


def migrate(connection, *, down=False):
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_lock(hashtext('nextris-veterinary-migration'))")
    try:
        with connection.cursor() as cursor:
            cursor.execute('CREATE TABLE IF NOT EXISTS nextris.veterinary_schema_migration(version text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now())')
            cursor.execute('SELECT 1 FROM nextris.veterinary_schema_migration WHERE version=%s', (VERSION,))
            exists = bool(cursor.fetchone())
        connection.commit()
        if exists == (not down):
            return False
        script = ROOT / 'deployment/migrations' / (VERSION + ('_down.sql' if down else '_up.sql'))
        with connection.cursor() as cursor:
            cursor.execute(script.read_text().strip().removeprefix('BEGIN;').removesuffix('COMMIT;'))
            if down:
                cursor.execute('DELETE FROM nextris.veterinary_schema_migration WHERE version=%s', (VERSION,))
            else:
                cursor.execute('INSERT INTO nextris.veterinary_schema_migration(version) VALUES(%s)', (VERSION,))
        connection.commit()
        return True
    finally:
        connection.rollback()
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_unlock(hashtext('nextris-veterinary-migration'))")
        connection.commit()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--down', action='store_true')
    args = parser.parse_args()
    load_dotenv(ROOT / '.env')
    with psycopg2.connect(host=os.environ['DB_HOST'], port=os.getenv('DB_PORT', '5432'),
                         dbname=os.environ['DB_NAME'], user=os.environ['DB_USER'], password=os.environ['DB_PASS']) as connection:
        if args.apply:
            print('Changed:', migrate(connection, down=args.down))
        else:
            with connection.cursor() as cursor:
                cursor.execute("SELECT to_regclass('nextris.datapatient')")
                if not cursor.fetchone()[0]:
                    raise SystemExit('Initialize the general edition first')
            print('Preflight passed. No changes applied. Use --apply; --down refuses data loss.')
