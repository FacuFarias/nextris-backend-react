"""Adjust existing doctors/technicians without replacing their custom permissions.

Run with --apply to persist; --report writes a private before/after JSON.
"""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import uuid

import psycopg2
from psycopg2 import sql
from psycopg2.extras import Json

spec = importlib.util.spec_from_file_location('previous_permission_migration',
    Path(__file__).with_name('20261021_permission_templates.py'))
previous = importlib.util.module_from_spec(spec)
spec.loader.exec_module(previous)
policy = previous.policy
VERSION = '20261021_clinical_role_adjustments_v2'


def migrate(connection, apply=False, schema='nextris'):
    s = sql.Identifier(schema)
    with connection.cursor() as cursor:
        if apply:
            cursor.execute('SELECT pg_advisory_xact_lock(hashtext(%s))', (schema + ':' + VERSION,))
        cursor.execute('SELECT to_regclass(%s)', (schema + '.permission_policy_migration',))
        if cursor.fetchone()[0]:
            cursor.execute(sql.SQL('SELECT audit FROM {s}.permission_policy_migration WHERE version=%s').format(s=s), (VERSION,))
            marker = cursor.fetchone()
            if marker:
                return dict(status='already_applied',version=VERSION,original_audit=marker[0],current=previous.snapshot(connection,schema))
        before = previous.snapshot(connection,schema)
        affected = []
        for user in before:
            role = policy.normalize_role_name(user['role'])
            if role not in {'medico','tecnico'}:
                continue
            codes = set(user['custom_permissions'])
            if role == 'medico':
                codes = {code for code in codes if policy.normalize_permission_code(code) != 'tabs.gestion.view'}
                codes.add('reports.unsign')
            else:
                codes.add('dicom.studies.manage')
            affected.append(dict(**user,after_permissions=sorted(codes)))
        audit = dict(version=VERSION,status='applied' if apply else 'preview',users=affected)
        if not apply:
            return audit
        for user in affected:
            if policy.normalize_role_name(user['role']) == 'medico':
                cursor.execute(sql.SQL('''DELETE FROM {s}.rel_user_permission up USING {s}.ispermission p
                    WHERE up.permission_id=p.guid AND up.user_id=%s AND p.code=ANY(%s)''').format(s=s),
                    (user['user_id'],['tabs.gestion.view','tabs.preferences.view']))
                code = 'reports.unsign'
            else:
                code = 'dicom.studies.manage'
            cursor.execute(sql.SQL('''SELECT guid FROM {s}.ispermission WHERE code=%s AND is_active''').format(s=s),(code,))
            permission = cursor.fetchone()
            if not permission:
                raise RuntimeError('Permiso no disponible: ' + code)
            cursor.execute(sql.SQL('''INSERT INTO {s}.rel_user_permission(guid,user_id,permission_id,is_granted)
                VALUES (%s,%s,%s,TRUE) ON CONFLICT(user_id,permission_id)
                DO UPDATE SET is_granted=TRUE,updated_on=NOW()''').format(s=s),
                (str(uuid.uuid4()),user['user_id'],permission[0]))
        current = {u['user_id']:u['custom_permissions'] for u in previous.snapshot(connection,schema)}
        if any(current[u['user_id']] != u['after_permissions'] for u in affected):
            raise RuntimeError('No coincide la verificación de permisos clínicos')
        cursor.execute(sql.SQL('''CREATE TABLE IF NOT EXISTS {s}.permission_policy_migration (
            version TEXT PRIMARY KEY, applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), audit JSONB NOT NULL)''').format(s=s))
        cursor.execute(sql.SQL('INSERT INTO {s}.permission_policy_migration(version,audit) VALUES (%s,%s)').format(s=s),(VERSION,Json(audit)))
        return audit


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply',action='store_true')
    parser.add_argument('--report',type=Path)
    args = parser.parse_args()
    connection = psycopg2.connect(user=os.getenv('DB_USER'),password=os.getenv('DB_PASS'),
        host=os.getenv('DB_HOST'),port=os.getenv('DB_PORT'),dbname=os.getenv('DB_NAME'))
    try:
        if not args.apply:
            connection.set_session(readonly=True)
        audit = migrate(connection,args.apply)
        if args.report:
            args.report.parent.mkdir(parents=True,exist_ok=True)
            fd = os.open(args.report,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
            with os.fdopen(fd,'w') as stream:
                json.dump(audit,stream,ensure_ascii=False,indent=2)
        if args.apply:
            connection.commit()
        else:
            connection.rollback()
        print(json.dumps(dict(status=audit['status'],users=len(audit.get('users',[])),version=VERSION)))
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


if __name__ == '__main__':
    main()
