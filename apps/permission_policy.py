"""Deployment permission policy. Pure definitions shared by the API and migration."""
import os
import unicodedata

# This deployment disables these screens, never their external integration APIs.
DISABLED_MODULES = frozenset(filter(None, (item.strip() for item in os.getenv(
    'NEXTRIS_DISABLED_MODULES', ''
).split(','))))

PERMISSION_CATALOG = [{'code': 'tabs.appointments.view',
  'module': 'appointments',
  'action': 'view',
  'description': 'Ver pestaña Citas'},
 {'code': 'tabs.admissions.view',
  'module': 'admissions',
  'action': 'view',
  'description': 'Ver pestaña Admisión'},
 {'code': 'tabs.worklist.view',
  'module': 'worklist',
  'action': 'view',
  'description': 'Ver Lista de trabajo'},
 {'code': 'tabs.config.view',
  'module': 'config',
  'action': 'view',
  'description': 'Gestionar configuración del sistema'},
 {'code': 'tabs.gestion.view',
  'module': 'gestion',
  'action': 'view',
  'description': 'Gestionar unificación, reasignación e integraciones'},
 {'code': 'reports.sign', 'module': 'reports', 'action': 'sign', 'description': 'Firmar informe'},
 {'code': 'reports.unsign', 'module': 'reports', 'action': 'unsign', 'description': 'Desfirmar informe'},
 {'code': 'distribution.send_report',
  'module': 'distribution',
  'action': 'send_report',
  'description': 'Enviar informe por email'},
 {'code': 'distribution.send_report_whatsapp',
  'module': 'distribution',
  'action': 'send_report_whatsapp',
  'description': 'Enviar informe por WhatsApp'},
 {'code': 'distribution.update_email',
  'module': 'distribution',
  'action': 'update_email',
  'description': 'Actualizar email para distribución'},
 {'code': 'users.manage', 'module': 'users', 'action': 'manage', 'description': 'Gestionar usuarios'},
 {'code': 'users.impersonate',
  'module': 'users',
  'action': 'impersonate',
  'description': 'Conectarse como otro usuario del personal'},
 {'code': 'users.permissions.manage',
  'module': 'users',
  'action': 'manage_permissions',
  'description': 'Gestionar permisos de usuarios'},
 {'code': 'admissions.view', 'module': 'admissions', 'action': 'view', 'description': 'Ver admisiones'},
 {'code': 'admissions.create_spontaneous',
  'module': 'admissions',
  'action': 'create_spontaneous',
  'description': 'Generar admisión espontánea'},
 {'code': 'admissions.admit_appointments',
  'module': 'admissions',
  'action': 'admit_appointments',
  'description': 'Admisionar citas'},
 {'code': 'appointments.view', 'module': 'appointments', 'action': 'view', 'description': 'Ver citas'},
 {'code': 'appointments.create',
  'module': 'appointments',
  'action': 'create',
  'description': 'Generar citas'},
 {'code': 'distribution.view',
  'module': 'distribution',
  'action': 'view',
  'description': 'Consultar distribución'},
 {'code': 'distribution.perform',
  'module': 'distribution',
  'action': 'perform',
  'description': 'Hacer la distribución'},
 {'code': 'worklist.share',
  'module': 'worklist',
  'action': 'share',
  'description': 'Compartir imágenes y estudio'},
 {'code': 'worklist.confirm_execute',
  'module': 'worklist',
  'action': 'confirm_execute',
  'description': 'Confirmar o ejecutar estudios'},
 {'code': 'worklist.link_missing_images',
  'module': 'worklist',
  'action': 'link_missing_images',
  'description': 'Vincular imágenes faltantes desde la Lista de trabajo'},
 {'code': 'patients.view', 'module': 'patients', 'action': 'view', 'description': 'Ver pacientes'},
 {'code': 'patients.manage',
  'module': 'patients',
  'action': 'manage',
  'description': 'Generar nuevos pacientes / editar pacientes'},
 {'code': 'images.view', 'module': 'images', 'action': 'view', 'description': 'Ver imágenes DICOM'},
 {'code': 'images.share_link',
  'module': 'images',
  'action': 'share_link',
  'description': 'Generar enlace compartido de imágenes'},
 {'code': 'images.presentation_states.delete_any',
  'module': 'images',
  'action': 'delete_any_presentation_state',
  'description': 'Eliminar Presentation States de otros usuarios (incluye PR sin autor)'},
 {'code': 'images.delete',
  'module': 'images',
  'action': 'delete',
  'description': 'Gestión de imágenes: eliminar estudios, series e imágenes'},
 {'code': 'reports.write', 'module': 'reports', 'action': 'write', 'description': 'Redactar informes'},
 {'code': 'templates.manage',
  'module': 'templates',
  'action': 'manage',
  'description': 'Gestionar informes predefinidos'},
 {'code': 'dicom.studies.manage',
  'module': 'dicom',
  'action': 'manage_studies',
  'description': 'Cargar, vincular y desvincular estudios DICOM'},
 {'code': 'reports.assign',
  'module': 'reports',
  'action': 'assign',
  'description': 'Asignar estudio a un usuario'},
 {'code': 'reports.notes.delete',
  'module': 'reports',
  'action': 'delete_notes',
  'description': 'Eliminar notas de estudios'}]

PERMISSION_CATALOG += [{'code': 'tabs.structured_reports.view', 'module': 'structured_reports', 'action': 'view', 'description': 'Ver pestaña Reportes estructurados'}, {'code': 'tabs.nexi.view', 'module': 'nexi', 'action': 'view', 'description': 'Ver pestaña Nexi'}]

PERMISSION_CATALOG = [p for p in PERMISSION_CATALOG if p["module"] not in DISABLED_MODULES]
VALID_PERMISSION_CODES = frozenset(p["code"] for p in PERMISSION_CATALOG)

DEPRECATED_PERMISSION_ALIASES = {'tabs.preferences.view': 'tabs.gestion.view',
 'tabs.execution.view': 'tabs.worklist.view',
 'execution.view_pending': 'tabs.worklist.view',
 'execution.execute': 'worklist.confirm_execute',
 'tabs.reports.view': 'tabs.worklist.view',
 'reports.view_writing': 'reports.write',
 'reports.view_reports': 'templates.manage',
 'tabs.patients.view': 'patients.view',
 'tabs.images.view': 'images.view',
 'tabs.distribution.view': 'distribution.view'}

ROLE_BASED_PERMISSIONS = {'sysadmin': {'*'},
 'administrador': {'dicom.studies.manage',
                   'distribution.perform',
                   'distribution.send_report',
                   'distribution.send_report_whatsapp',
                   'distribution.update_email',
                   'distribution.view',
                   'images.share_link',
                   'images.view',
                   'patients.manage',
                   'patients.view',
                   'reports.assign',
                   'tabs.config.view',
                   'tabs.gestion.view',
                   'tabs.worklist.view',
                   'users.manage',
                   'users.permissions.manage',
                   'worklist.confirm_execute',
                   'worklist.link_missing_images'},
 'administrativo': {'distribution.perform',
                    'distribution.send_report',
                    'distribution.send_report_whatsapp',
                    'distribution.update_email',
                    'distribution.view',
                    'patients.manage',
                    'patients.view',
                    'tabs.worklist.view'},
 'medico': {'reports.unsign',
            'images.share_link',
            'images.view',
            'patients.view',
            'reports.sign',
            'reports.write',
            'tabs.worklist.view',
            'templates.manage'},
 'tecnico': {'dicom.studies.manage',
             'images.view',
             'patients.view',
             'tabs.worklist.view',
             'worklist.confirm_execute'}}
ROLE_BASED_PERMISSIONS["admin"] = ROLE_BASED_PERMISSIONS["administrador"]

def normalize_role_name(role_name):
    normalized = unicodedata.normalize('NFD', str(role_name or ''))
    return ''.join(c for c in normalized if unicodedata.category(c) != 'Mn').strip().lower()


def normalize_permission_code(code):
    return DEPRECATED_PERMISSION_ALIASES.get(code, code)


def normalize_permission_codes(codes):
    return list(dict.fromkeys(normalize_permission_code(code) for code in codes or [] if code and code != '*'))


def get_default_permissions_for_role(role_name):
    role = normalize_role_name(role_name)
    codes = set(ROLE_BASED_PERMISSIONS.get(role, set()))
    if role != 'patient' and '*' not in codes:
        codes.add('worklist.share')
    return sorted(code for code in codes if code == '*' or code in VALID_PERMISSION_CODES)


def validate_permission_codes(codes):
    if not isinstance(codes, list) or any(not isinstance(code, str) for code in codes):
        raise ValueError('permission_codes debe ser una lista de códigos de permisos')
    normalized = normalize_permission_codes(codes)
    invalid = sorted(set(normalized) - VALID_PERMISSION_CODES)
    if '*' in codes:
        invalid.append('*')
    if invalid:
        raise ValueError('Permisos no válidos: ' + ', '.join(invalid))
    return normalized
