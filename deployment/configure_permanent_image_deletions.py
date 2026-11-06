"""Configure an isolated PACS purge code for confirmed NextRIS deletions.

Read-only by default. Does not change retention or purge behavior of any
standard rejection reason, or delete previously rejected clinical objects.
"""
import argparse
import copy
import json
from pathlib import Path
import sys
import tempfile

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / '.env')
from apps.services.image_deletions import PacsClient


CODE = '(NEXTDEL, 99NEXTRIS, "NextRIS permanent deletion")'


def configure(apply=False):
    pacs = PacsClient()
    url = pacs.root + '/devices/dcm4chee-arc'
    response = pacs.request('GET', url)
    response.raise_for_status()
    config = response.json()
    archive = config['dcmDevice']['dcmArchiveDevice']
    before = copy.deepcopy(archive)
    notes = archive.setdefault('dcmRejectionNote', [])
    expected = {
        'dcmRejectionNoteLabel': 'NextRIS Permanent Delete',
        'dcmRejectionNoteCode': CODE,
        'dcmRejectionNoteType': 'REJECTED_FOR_QUALITY_REASONS',
        'dcmAcceptPreviousRejectedInstance': 'RESTORE',
        'dcmOverwritePreviousRejection': [
            '(113001, DCM, "Rejected for Quality Reasons")',
            '(113037, DCM, "Rejected for Patient Safety Reasons")',
            '(113038, DCM, "Incorrect Modality Worklist Entry")',
        ],
        'dcmDeleteRejectedInstanceDelay': 'PT0S',
        'dcmDeleteRejectionNoteDelay': 'PT0S',
    }
    existing = next((n for n in notes if n.get('dcmRejectionNoteLabel') == expected['dcmRejectionNoteLabel']), None)
    if existing is not None and any(existing.get(k) != v for k, v in expected.items()):
        raise RuntimeError('Existing private deletion policy differs; inspect it before changing it')
    if existing is None:
        if any('NEXTDEL' in n.get('dcmRejectionNoteCode', '') for n in notes):
            raise RuntimeError('Private deletion code already belongs to another policy')
        notes.append(expected)
    for view in archive.get('dcmQueryRetrieveView', []):
        if view.get('dcmQueryRetrieveViewID') in {'hideRejected', 'regularUse'}:
            hidden = view.setdefault('dcmHideRejectionNoteWithCode', [])
            if CODE not in hidden:
                hidden.append(CODE)
    changed = archive != before
    print('Private deletion policy requires update:', changed)
    if apply and changed:
        # Save only changed policy areas, without device credentials.
        with tempfile.NamedTemporaryFile(mode='w', prefix='nextris-permanent-delete-', suffix='.json',
                                         delete=False) as f:
            json.dump({k: before.get(k) for k in ('dcmRejectionNote', 'dcmQueryRetrieveView')}, f, indent=2)
            print('Policy backup:', f.name)
        response = pacs.request('PUT', url, json=config)
        response.raise_for_status()
        response = pacs.request('POST', pacs.root + '/ctrl/reload')
        response.raise_for_status()
    if apply:
        if not pacs.permanent_deletion_available():
            raise RuntimeError('PACS did not expose the private deletion policy after reload')
        print('Private permanent deletion policy verified')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    configure(parser.parse_args().apply)
