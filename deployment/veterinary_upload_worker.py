#!/usr/bin/env python3
"""Single persistent worker, guarded by a PostgreSQL session lock across restarts."""
import argparse
import logging
from pathlib import Path
import signal
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parents[1]/'.env')
from apps.services import veterinary as vet
from apps.services.veterinary_uploads import process_one, expire_abandoned


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--once',action='store_true')
    args=parser.parse_args()
    if vet.mode()!='veterinary':raise SystemExit('Worker requires veterinary mode')
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
    running=True
    def stop(_signal,_frame):
        nonlocal running
        running=False
    signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
    with vet.database() as lease:
        lease.autocommit=True
        with lease.cursor() as q:
            q.execute("SELECT pg_try_advisory_lock(hashtext('veterinary-upload-worker'))")
            if not q.fetchone()[0]:raise SystemExit('Another upload worker is already running')
        last_cleanup=0
        while running:
            # Losing this connection loses the singleton lease, so exit rather than process unlocked.
            with lease.cursor() as q:q.execute('SELECT 1')
            if time.monotonic()-last_cleanup>3600:
                expire_abandoned();last_cleanup=time.monotonic()
            worked=process_one()
            if args.once:break
            if not worked:time.sleep(1)


if __name__=='__main__':main()
