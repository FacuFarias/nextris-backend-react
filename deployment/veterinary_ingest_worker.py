#!/usr/bin/env python3
"""Independent PACS-to-RIS worker; never runs inside the PACS receive transaction."""
import argparse
import logging
from pathlib import Path
import signal
import sys
import time
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parents[1]/'.env')
from apps.services import veterinary as vet
from apps.services.simple_veterinary import enabled
from apps.services.veterinary_ingest import run_once


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--once', action='store_true')
    args = parser.parse_args()
    if not enabled():
        raise SystemExit('Worker requires simple_veterinary workflow')
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    running = True
    def stop(_signal, _frame):
        nonlocal running
        running = False
    signal.signal(signal.SIGTERM, stop); signal.signal(signal.SIGINT, stop)
    with vet.database() as lease:
        lease.autocommit = True
        with lease.cursor() as cursor:
            cursor.execute("SELECT pg_try_advisory_lock(hashtext('simple-veterinary-ingest-worker'))")
            if not cursor.fetchone()[0]:
                raise SystemExit('Another DICOM ingestion worker is running')
        while running:
            with lease.cursor() as cursor:
                cursor.execute('SELECT 1')
            result = run_once()
            if result['processed'] or result['failed']:
                logging.info('DICOM ingest: processed=%s failed=%s', result['processed'], result['failed'])
            if args.once:
                return
            if not result['processed']:
                for _ in range(50):
                    if not running:
                        break
                    time.sleep(0.1)


if __name__ == '__main__':
    main()
