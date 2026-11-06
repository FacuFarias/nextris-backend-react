"""Freeze general-edition inherited access once, without replacing custom grants."""
import uuid
from psycopg2.extras import Json
from apps.permission_policy import normalize_permission_codes, normalize_role_name, VALID_PERMISSION_CODES

VERSION = '20261105_general_permission_inheritance'
LEGACY_ROLE_PERMISSIONS = {'sysadmin': {'*'}, 'administrativo': {'tabs.admissions.view', 'tabs.appointments.view', 'tabs.distribution.view', 'tabs.patients.view'}, 'tecnico': {'tabs.execution.view', 'tabs.patients.view'}, 'medico': {'distribution.send_report', 'tabs.patients.view', 'distribution.view', 'tabs.reports.view', 'distribution.perform', 'distribution.send_report_whatsapp', 'admissions.view', 'reports.sign', 'tabs.admissions.view', 'admissions.create_spontaneous', 'tabs.distribution.view', 'patients.manage', 'distribution.update_email'}}


def migrate(connection):
    with connection.cursor() as cursor:
        cursor.execute('SELECT pg_advisory_xact_lock(hashtext(%s))', (VERSION,))
        cursor.execute("""CREATE TABLE IF NOT EXISTS nextris.permission_policy_migration (
            version text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now(), audit jsonb NOT NULL)""")
        cursor.execute('SELECT 1 FROM nextris.permission_policy_migration WHERE version=%s',(VERSION,))
        if cursor.fetchone():
            return
        cursor.execute('SELECT up.user_id,p.code,up.is_granted FROM nextris.rel_user_permission up JOIN nextris.ispermission p ON p.guid=up.permission_id')
        saved = cursor.fetchall()
        for user_id, old_code, granted in saved:
            codes = normalize_permission_codes([old_code])
            for code in set(codes) & VALID_PERMISSION_CODES:
                if code == old_code:
                    continue
                cursor.execute("""INSERT INTO nextris.rel_user_permission(guid,user_id,permission_id,is_granted)
                    SELECT %s,%s,guid,%s FROM nextris.ispermission WHERE code=%s
                    ON CONFLICT(user_id,permission_id) DO NOTHING""",(str(uuid.uuid4()),user_id,granted,code))
        cursor.execute('SELECT u.guid,r.description FROM nextris.tbuser u LEFT JOIN nextris.isrole r ON r.guid=u.idrole')
        users = cursor.fetchall()
        grants = []
        for user_id, role in users:
            inherited = normalize_permission_codes(LEGACY_ROLE_PERMISSIONS.get(normalize_role_name(role),set()))
            for code in sorted(set(inherited) & VALID_PERMISSION_CODES):
                cursor.execute("""INSERT INTO nextris.rel_user_permission(guid,user_id,permission_id,is_granted)
                    SELECT %s,%s,guid,true FROM nextris.ispermission WHERE code=%s
                    ON CONFLICT(user_id,permission_id) DO NOTHING""",(str(uuid.uuid4()),user_id,code))
                if cursor.rowcount:
                    grants.append(dict(user_id=user_id,code=code))
        cursor.execute('INSERT INTO nextris.permission_policy_migration(version,audit) VALUES(%s,%s)',
                       (VERSION,Json(dict(inherited_grants=grants))))
