"""Explicit schema migration for the single-institution edition; never starts workers."""
import argparse
import importlib.util
import os
from pathlib import Path
import sys
import psycopg2
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
MIGRATIONS = [
    '20260509_single_tenant_migration.sql',
    '20261105_institution_hl7.sql',
    '20261105_general_compatibility.sql',
    '../sql/20260917_user_impersonation.sql',
    '20260426_add_owner_id_to_tbinfpredef.sql',
    'add_gateway_transmission_to_tblocation.sql',
    'add_require_execution_before_reporting_to_tblocation.sql',
    'create_viewer_share_links.sql',
    '20260815_add_viewer_share_short_code.sql',
    '20260815_harden_viewer_share_links.sql',
    '20260816_hanging_protocols.sql',
    '20260820_add_requestingphysician_name.sql',
    '20260820_create_examination_notes.sql',
    '20260821_shared_access_link_types.sql',
    '20260903_canonical_report_fields.sql',
    '20260909_track_applied_report_template.sql',
    '20261016_patient_contact_fields.sql',
    '20261019_medical_integration_id.sql',
    '20261105_manual_upload_links.sql',
    '20261020_image_deletions.sql',
    '20261023_patient_email_verification.sql',
    '20261023_viewer_presentation_states.sql',
    '20261026_medical_stamp.sql',
    '20261027_permanent_image_deletions.sql',
    '20261105_local_study_workflow.sql',
]


def preflight(connection):
    with connection.cursor() as cursor:
        for table in ('tbfacility', 'ispatientdomain'):
            cursor.execute('SELECT to_regclass(%s)', ('nextris.' + table,))
            if cursor.fetchone()[0]:
                cursor.execute('SELECT count(*) FROM nextris.' + table)
                if cursor.fetchone()[0] > 1:
                    raise ValueError('Multiple institutions or patient domains; explicit selection/migration is required')
    connection.rollback()


def migrate(connection, *, initialize=False):
    preflight(connection)
    if initialize:
        with connection.cursor() as cursor:
            cursor.execute((ROOT / 'deployment/schema.sql').read_text())
        connection.commit()
    with connection.cursor() as cursor:
        cursor.execute('CREATE TABLE IF NOT EXISTS nextris.general_schema_migration (name text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now())')
    connection.commit()
    for name in MIGRATIONS:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1 FROM nextris.general_schema_migration WHERE name=%s', (name,))
            if cursor.fetchone():
                continue
            cursor.execute((ROOT / 'deployment/migrations' / name).read_text())
            cursor.execute('INSERT INTO nextris.general_schema_migration(name) VALUES(%s)', (name,))
        connection.commit()
        print('Applied:', name)
    from apps.home.services.app_config_service import ensure_app_config_table
    from apps.api.facility_plan_usage import ensure_plan_management_schema
    from apps.api.permissions import ensure_permissions_schema, seed_permissions
    ensure_app_config_table(connection)
    ensure_plan_management_schema(connection)
    ensure_permissions_schema(connection)
    seed_permissions(connection)
    spec = importlib.util.spec_from_file_location('general_permissions', ROOT / 'deployment/migrations/20261105_preserve_general_permissions.py')
    permission_migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(permission_migration)
    permission_migration.migrate(connection)
    connection.commit()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--initialize', action='store_true', help='Create the empty NextRIS foundation schema first')
    parser.add_argument('--apply', action='store_true', help='Apply to the configured database; default is preflight only')
    args = parser.parse_args()
    load_dotenv(ROOT / '.env')
    from apps.home.services.config_service import ConfigService
    with psycopg2.connect(**ConfigService.get_db_config()) as connection:
        preflight(connection)
        if args.apply:
            migrate(connection, initialize=args.initialize)
        else:
            print('Preflight passed. Pending sequence:', ', '.join(MIGRATIONS))


if __name__ == '__main__':
    main()
