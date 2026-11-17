"""Configure an isolated PACS purge code for confirmed NextRIS deletions.

Read-only by default. Does not change retention or purge behavior of any
standard rejection reason, or delete previously rejected clinical objects.
Enables explicit whole-study deletion only on the AE selected by PACS_STOW_URL.
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
    aet = pacs.base.split('/aets/', 1)[1].split('/', 1)[0]
    target_ae = next((ae for ae in config.get('dicomNetworkAE', [])
                      if ae.get('dicomAETitle') == aet), None)
    if target_ae is None:
        raise RuntimeError('Configured PACS AE was not found on the archive device')
    archive_ae = target_ae['dcmNetworkAE']['dcmArchiveNetworkAE']
    permission_key = 'dcmAllowDeleteStudyPermanently'
    previous_permission = {'aet': aet, 'present': permission_key in archive_ae,
                           'value': archive_ae.get(permission_key)}
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
    # The PACS defaults to REJECTED, which rejects DELETE of an ordinary study.
    # Scope the override to this integration's AE, preserving the device default
    # and other AEs. This only permits an explicit API request; it schedules none.
    archive_ae[permission_key] = 'ALWAYS'
    changed = archive != before or previous_permission['value'] != 'ALWAYS'
    print('Permanent deletion configuration requires update:', changed)
    if apply and changed:
        # Save only changed policy areas, without device credentials.
        with tempfile.NamedTemporaryFile(mode='w', prefix='nextris-permanent-delete-', suffix='.json',
                                         delete=False) as f:
            backup = {k: before.get(k) for k in ('dcmRejectionNote', 'dcmQueryRetrieveView')}
            backup['studyDeletionPermission'] = previous_permission
            json.dump(backup, f, indent=2)
            print('Policy backup:', f.name)
        response = pacs.request('PUT', url, json=config)
        response.raise_for_status()
        response = pacs.request('POST', pacs.root + '/ctrl/reload')
        response.raise_for_status()
    if apply:
        if not pacs.permanent_deletion_available():
            raise RuntimeError('PACS did not expose the private deletion policy after reload')
        response = pacs.request('GET', url)
        response.raise_for_status()
        verified_ae = next(ae for ae in response.json()['dicomNetworkAE'] if ae['dicomAETitle'] == aet)
        if verified_ae['dcmNetworkAE']['dcmArchiveNetworkAE'].get(permission_key) != 'ALWAYS':
            raise RuntimeError('PACS did not preserve whole-study deletion permission on the selected AE')
        print('Private permanent deletion policy and selected AE permission verified')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    configure(parser.parse_args().apply)
