"""Hide IOCM rejection notes in the existing normal archive view.

Read-only by default. Run with --apply to update only hideRejected's note list.
No retention/purge settings or other retrieval views are changed.
"""
import argparse
import copy
import json
from pathlib import Path
import sys
from urllib.parse import quote

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / '.env')
from apps.services.image_deletions import PacsClient


def views(value):
    if isinstance(value, dict):
        for k, v in value.items():
            if k == 'dcmQueryRetrieveView':
                yield from v
            else:
                yield from views(v)
    elif isinstance(value, list):
        for v in value:
            yield from views(v)


def configure(apply=False):
    pacs = PacsClient()
    response = pacs.request('GET', pacs.root + '/devices')
    response.raise_for_status()
    changed = 0
    for device in response.json():
        name = device.get('dicomDeviceName') if isinstance(device, dict) else device
        if not name:
            continue
        url = pacs.root + '/devices/' + quote(name, safe='')
        response = pacs.request('GET', url)
        response.raise_for_status()
        config = response.json()
        original = copy.deepcopy(config)
        for view in views(config):
            if view.get('dcmQueryRetrieveViewID') != 'hideRejected':
                continue
            hidden = view.setdefault('dcmHideRejectionNoteWithCode', [])
            for code in ('(113001, DCM, "Rejected for Quality Reasons")',
                         '(113037, DCM, "Rejected for Patient Safety Reasons")',
                         '(113038, DCM, "Incorrect Modality Worklist Entry")'):
                if code not in hidden:
                    hidden.append(code)
        if config != original:
            changed += 1
            print('Normal retrieval view requires IOCM note filtering:', name)
            if apply:
                # Store only the previous view list, never the full device credentials.
                backup = Path('/tmp') / ('nextris-rejection-view-' + quote(name, safe='') + '.json')
                if not backup.exists():
                    with backup.open('x', encoding='utf8') as f:
                        backup.chmod(0o600)
                        json.dump(list(views(original)), f)
                updated = pacs.request('PUT', url, json=config)
                updated.raise_for_status()
                verify = pacs.request('GET', url)
                verify.raise_for_status()
                assert list(views(verify.json())) == list(views(config))
    if apply and changed:
        response = pacs.request('POST', pacs.root + '/ctrl/reload')
        response.raise_for_status()
    print('Updated devices:' if apply else 'Devices needing update:', changed)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    configure(parser.parse_args().apply)
