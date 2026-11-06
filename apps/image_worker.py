"""Minimal Flask CLI app: no web app initialization or unrelated queue workers."""
from pathlib import Path
import logging

import click
from dotenv import load_dotenv
from flask import Flask

load_dotenv(Path(__file__).resolve().parents[1] / '.env')
app = Flask(__name__, instance_path=str(Path(__file__).resolve().parents[1] / 'instance'))


@app.cli.command('image-deletion-worker')
@click.option('--once', is_flag=True, help='Reconcile and process a bounded batch, then exit.')
def image_deletion_worker(once):
    from apps.services.image_deletions import reconcile, work_once, run_worker
    logging.basicConfig(level=logging.INFO)
    if once:
        reconcile()
        work_once()
    else:
        run_worker()
