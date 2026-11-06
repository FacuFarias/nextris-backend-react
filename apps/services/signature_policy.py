"""Requisitos para firmar un informe. La matrícula es opcional."""

TEST_SIGNATURE_NAME = '[PRUEBA] Administrador'
TEST_SIGNATURE_REGISTRATION = 'PRUEBA'


def signature_problem(medical_data):
    """(error_code, message) when (firma_habilitada, aclaracion_firma) cannot sign; None otherwise."""
    if not medical_data:
        return ('MEDICAL_DATA_MISSING',
                'No se encontraron datos médicos para el usuario. Complete su perfil con aclaración de firma antes de firmar.')
    enabled, clarification = medical_data
    if not enabled:
        return ('SIGNATURE_NOT_ENABLED',
                'Su firma digital no está habilitada. Habilite su firma en Configuración > Datos Médicos antes de firmar reportes.')
    if not (clarification or '').strip():
        return ('SIGNATURE_DATA_INCOMPLETE', 'Falta la aclaración de firma. Complete su perfil médico antes de firmar.')
    return None
