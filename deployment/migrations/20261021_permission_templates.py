"""One-time permission migration and audit. No Flask import or clinical writes.

Dry run: venv/bin/python deployment/migrations/20261021_permission_templates.py
Apply:   ... --apply --report deployment/audits/permission_templates.json
"""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import uuid

from psycopg2 import sql
from psycopg2.extras import Json

ROOT = Path(__file__).resolve().parents[2]
from dotenv import load_dotenv
load_dotenv(ROOT / '.env')
spec = importlib.util.spec_from_file_location('permission_policy', ROOT / 'apps/permission_policy.py')
policy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(policy)
VERSION = '20261021_permission_templates_v1'

# Frozen inheritance from the previously deployed policy; never use new templates here.
LEGACY_ROLE_PERMISSIONS = {'sysadmin': {'*'},
 'administrativo': {'images.share_link',
                    'images.view',
                    'tabs.admissions.view',
                    'tabs.appointments.view',
                    'tabs.distribution.view',
                    'tabs.patients.view',
                    'tabs.worklist.view'},
 'administrador': {'images.share_link',
                   'images.view',
                   'worklist.link_missing_images'},
 'admin': {'worklist.link_missing_images'},
 'tecnico': {'images.view',
             'patients.view',
             'tabs.images.view',
             'tabs.patients.view',
             'tabs.worklist.view',
             'worklist.confirm_execute'},
 'medico': {'admissions.create_spontaneous',
            'admissions.view',
            'dicom.studies.manage',
            'distribution.perform',
            'distribution.send_report',
            'distribution.send_report_whatsapp',
            'distribution.update_email',
            'distribution.view',
            'images.view',
            'patients.manage',
            'patients.view',
            'reports.assign',
            'reports.sign',
            'reports.write',
            'tabs.admissions.view',
            'tabs.distribution.view',
            'tabs.gestion.view',
            'tabs.images.view',
            'tabs.patients.view',
            'tabs.worklist.view',
            'templates.manage'}}

def snapshot(connection, schema='nextris'):
    with connection.cursor() as cursor:
        cursor.execute(sql.SQL('''SELECT u.guid, u.username, r.description,
            COALESCE(array_agg(p.code) FILTER (WHERE up.is_granted AND p.is_active), ARRAY[]::varchar[])
            FROM {s}.tbuser u LEFT JOIN {s}.isrole r ON r.guid=u.idrole
            LEFT JOIN {s}.rel_user_permission up ON up.user_id=u.guid
            LEFT JOIN {s}.ispermission p ON p.guid=up.permission_id
            GROUP BY u.guid,u.username,r.description ORDER BY u.username''').format(s=sql.Identifier(schema)))
        return [dict(user_id=row[0], username=row[1], role=row[2], custom_permissions=sorted(row[3]))
                for row in cursor.fetchall()]


def preserved_codes(user):
    inherited = LEGACY_ROLE_PERMISSIONS.get(policy.normalize_role_name(user['role']), set())
    return sorted(set(policy.normalize_permission_codes(user['custom_permissions'] + list(inherited)))
                  & policy.VALID_PERMISSION_CODES)


def migrate(connection, apply=False, schema='nextris'):
    """Caller owns commit/rollback. Schema argument supports isolated DB tests."""
    s = sql.Identifier(schema)
    with connection.cursor() as cursor:
        if apply:
            cursor.execute('SELECT pg_advisory_xact_lock(hashtext(%s))', (schema + ':' + VERSION,))
        cursor.execute('SELECT to_regclass(%s)', (schema + '.permission_policy_migration',))
        marker_exists = cursor.fetchone()[0] is not None
        if marker_exists:
            cursor.execute(sql.SQL('SELECT audit FROM {s}.permission_policy_migration WHERE version=%s').format(s=s), (VERSION,))
            marker = cursor.fetchone()
            if marker:
                return dict(status='already_applied', version=VERSION, original_audit=marker[0], current=snapshot(connection, schema))
        before = snapshot(connection, schema)
        users = []
        for user in before:
            inherited = LEGACY_ROLE_PERMISSIONS.get(policy.normalize_role_name(user['role']), set())
            effective = sorted(set(user['custom_permissions']) | inherited)
            after = preserved_codes(user)
            users.append(dict(**user, before_effective=effective, after_permissions=after,
                              after_effective=['*'] if policy.normalize_role_name(user['role']) == 'sysadmin' else after))
        role_counts = {}
        for user in users:
            role_counts[user['role']] = role_counts.get(user['role'], 0) + 1
        audit = dict(version=VERSION, status='applied' if apply else 'preview',
                     disabled_modules=sorted(policy.DISABLED_MODULES), roles=role_counts, users=users)
        if not apply:
            return audit
        # Store complete permission tables for a reviewable pre-migration snapshot.
        for table in ('ispermission', 'rel_user_permission'):
            cursor.execute(sql.SQL('SELECT row_to_json(t) FROM {s}.{t} t').format(s=s,t=sql.Identifier(table)))
            audit[table + '_before'] = [row[0] for row in cursor.fetchall()]
        cursor.execute(sql.SQL('''CREATE TABLE IF NOT EXISTS {s}.permission_policy_migration (
            version TEXT PRIMARY KEY, applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), audit JSONB NOT NULL
        )''').format(s=s))
        for item in policy.PERMISSION_CATALOG:
            cursor.execute(sql.SQL('''INSERT INTO {s}.ispermission(guid,code,module,action,description,is_active)
                VALUES (%s,%s,%s,%s,%s,TRUE) ON CONFLICT (code) DO UPDATE SET
                module=EXCLUDED.module,action=EXCLUDED.action,description=EXCLUDED.description,is_active=TRUE''').format(s=s),
                (str(uuid.uuid4()),item['code'],item['module'],item['action'],item['description']))
        cursor.execute(sql.SQL('UPDATE {s}.ispermission SET is_active=FALSE WHERE NOT(code=ANY(%s))').format(s=s),
                       (list(policy.VALID_PERMISSION_CODES),))
        for user in users:
            cursor.execute(sql.SQL('DELETE FROM {s}.rel_user_permission WHERE user_id=%s').format(s=s), (user['user_id'],))
            for code in user['after_permissions']:
                cursor.execute(sql.SQL('''INSERT INTO {s}.rel_user_permission(guid,user_id,permission_id,is_granted)
                    SELECT %s,%s,guid,TRUE FROM {s}.ispermission WHERE code=%s''').format(s=s),
                    (str(uuid.uuid4()),user['user_id'],code))
        actual = {user['user_id']:user['custom_permissions'] for user in snapshot(connection,schema)}
        if any(actual[user['user_id']] != user['after_permissions'] for user in users):
            raise RuntimeError('La verificación de permisos migrados no coincide con el relevamiento')
        cursor.execute(sql.SQL('INSERT INTO {s}.permission_policy_migration(version,audit) VALUES (%s,%s)').format(s=s),
                       (VERSION,Json(audit)))
        return audit


def main():
    import psycopg2
    from dotenv import load_dotenv
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply',action='store_true')
    parser.add_argument('--report',type=Path)
    args=parser.parse_args()
    load_dotenv(ROOT / '.env')
    connection=psycopg2.connect(user=os.getenv('DB_USER'),password=os.getenv('DB_PASS'),
                              host=os.getenv('DB_HOST'),port=os.getenv('DB_PORT'),dbname=os.getenv('DB_NAME'))
    try:
        if not args.apply:
            connection.set_session(readonly=True)
        audit=migrate(connection,args.apply)
        if args.report:
            args.report.parent.mkdir(parents=True,exist_ok=True)
            # Reports contain staff authorization data; do not expose through the web server.
            fd=os.open(args.report,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
            with os.fdopen(fd,'w') as stream:
                json.dump(audit,stream,ensure_ascii=False,indent=2,default=str)
        if args.apply:
            connection.commit()
        else:
            connection.rollback()
        print(json.dumps(dict(status=audit['status'],version=VERSION,
                              users=len(audit.get('users',audit.get('current',[]))),report=str(args.report or '')),ensure_ascii=False))
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


if __name__ == '__main__':
    main()
