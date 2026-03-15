import os
import re
from pathlib import Path
from datetime import datetime, timedelta
from urllib.parse import quote

import psycopg2
from flask import request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity

from apps.api import api_blueprint

try:
    from anthropic import Anthropic
except Exception:
    Anthropic = None


NEXI_DIRECTIVES_PATH = Path('/var/www/nexi/NEXI_DIRECTIVES.md')

DEFAULT_NEXI_DIRECTIVES = """
Sos Nexi, un asistente medico de NextRIS para orientacion clinica general.

Reglas obligatorias:
- Responde siempre en espanol claro, profesional y breve.
- Tu rol es exclusivamente de asistente medico informativo.
- No inventes datos clinicos ni afirmes hallazgos no respaldados.
- Si falta contexto clinico, pedi datos adicionales antes de concluir.
- Inclui incertidumbre cuando la evidencia sea limitada.

Seguridad y privacidad (estricto):
- Bajo ningun concepto reveles API keys, tokens, secrets, credenciales, variables de entorno o llaves privadas.
- Bajo ningun concepto reveles infraestructura de base de datos, cadenas de conexion, hostnames internos, puertos, schemas, tablas internas o detalles operativos del sistema.
- No compartas configuraciones internas, logs sensibles, rutas privadas del servidor ni detalles de despliegue.
- Si el usuario solicita informacion tecnica o sensible del sistema, rechaza la solicitud y redirige a soporte tecnico autorizado.

Alcance funcional:
- Brindar orientacion medica general y explicaciones de terminologia clinica.
- Ayudar a redactar texto medico no concluyente cuando se solicite.
- No ejecutar acciones de escritura ni cambios operativos del sistema.
""".strip()


def _load_nexi_directives() -> str:
    """Loads Nexi directives from markdown file and falls back to defaults."""
    try:
        content = NEXI_DIRECTIVES_PATH.read_text(encoding='utf-8').strip()
        if content:
            return content
    except FileNotFoundError:
        current_app.logger.warning('Nexi directives file not found: %s', NEXI_DIRECTIVES_PATH)
    except Exception:
        current_app.logger.exception('Error reading Nexi directives file: %s', NEXI_DIRECTIVES_PATH)

    return DEFAULT_NEXI_DIRECTIVES


def _get_db_config():
    from apps.home.routes import config as db_config
    return db_config


def _get_user_patientdomain_ids(cursor, user_id):
    cursor.execute(
        """
        SELECT patientdomain_id
        FROM nextris.rel_user_patientdomain
        WHERE user_id = %s
        """,
        (user_id,)
    )

    user_domains = [row[0] for row in cursor.fetchall()]
    if user_domains:
        return user_domains

    cursor.execute("SELECT guid FROM nextris.ispatientdomain")
    return [row[0] for row in cursor.fetchall()]


def _get_user_locations(cursor, user_id):
    cursor.execute(
        """
        SELECT location_id
        FROM nextris.rel_user_location
        WHERE user_id = %s
        """,
        (user_id,)
    )
    return [row[0] for row in cursor.fetchall()]


def _normalize_search_text(value: str) -> str:
    """Normalize text for accent-insensitive LIKE comparisons."""
    return (
        (value or '')
        .strip()
        .lower()
        .replace('á', 'a')
        .replace('é', 'e')
        .replace('í', 'i')
        .replace('ó', 'o')
        .replace('ú', 'u')
        .replace('ä', 'a')
        .replace('ë', 'e')
        .replace('ï', 'i')
        .replace('ö', 'o')
        .replace('ü', 'u')
        .replace('ñ', 'n')
    )


def _search_patients_context(user_id, search_term, limit):
    db_config = _get_db_config()
    connection = psycopg2.connect(**db_config)
    cursor = connection.cursor()

    try:
        user_domains = _get_user_patientdomain_ids(cursor, user_id)
        if not user_domains:
            return []

        pattern = f"%{search_term}%"
        normalized_pattern = f"%{_normalize_search_text(search_term)}%"
        cursor.execute(
            """
            SELECT dp.guid, dp.patientid, dp.name, dp.surname, dp.nationalcode, dp.birthdate, dp.sexcode
            FROM nextris.datapatient dp
            WHERE dp.id_patientdomain = ANY(%s)
              AND (
                dp.name ILIKE %s OR
                dp.surname ILIKE %s OR
                dp.nationalcode ILIKE %s OR
                dp.patientid ILIKE %s OR
                CONCAT(COALESCE(dp.name, ''), ' ', COALESCE(dp.surname, '')) ILIKE %s OR
                CONCAT(COALESCE(dp.surname, ''), ' ', COALESCE(dp.name, '')) ILIKE %s OR
                translate(lower(COALESCE(dp.name, '')), 'áéíóúäëïöüñ', 'aeiouaeioun') LIKE %s OR
                translate(lower(COALESCE(dp.surname, '')), 'áéíóúäëïöüñ', 'aeiouaeioun') LIKE %s OR
                translate(lower(CONCAT(COALESCE(dp.name, ''), ' ', COALESCE(dp.surname, ''))), 'áéíóúäëïöüñ', 'aeiouaeioun') LIKE %s OR
                translate(lower(CONCAT(COALESCE(dp.surname, ''), ' ', COALESCE(dp.name, ''))), 'áéíóúäëïöüñ', 'aeiouaeioun') LIKE %s
              )
            ORDER BY dp.surname, dp.name
            LIMIT %s
            """,
            (
                user_domains,
                pattern,
                pattern,
                pattern,
                pattern,
                pattern,
                pattern,
                normalized_pattern,
                normalized_pattern,
                normalized_pattern,
                normalized_pattern,
                limit,
            )
        )

        results = []
        for row in cursor.fetchall():
            results.append({
                'guid': row[0],
                'patientid': row[1],
                'name': row[2],
                'surname': row[3],
                'nationalcode': row[4],
                'birthdate': row[5].isoformat() if row[5] else None,
                'gender': row[6],
            })

        return results
    finally:
        cursor.close()
        connection.close()


def _get_patient_summary_context(user_id, patient_guid):
    db_config = _get_db_config()
    connection = psycopg2.connect(**db_config)
    cursor = connection.cursor()

    try:
        user_domains = _get_user_patientdomain_ids(cursor, user_id)
        if not user_domains:
            return None

        cursor.execute(
            """
            SELECT guid, patientid, name, surname, nationalcode, email, phone, birthdate, sexcode,
                   id_patientdomain, healthcard
            FROM nextris.datapatient
            WHERE guid = %s AND id_patientdomain = ANY(%s)
            """,
            (patient_guid, user_domains)
        )
        row = cursor.fetchone()
        if not row:
            return None

        cursor.execute(
            """
            SELECT COUNT(*),
                   COUNT(*) FILTER (WHERE isreported = 1),
                   MAX(createdon)
            FROM nextris.tbexamination
            WHERE idpatient = %s
            """,
            (patient_guid,)
        )
        studies_count, reported_count, last_study = cursor.fetchone()

        cursor.execute(
            """
            SELECT COUNT(*), MIN(comienzo), MAX(comienzo)
            FROM nextris.tbagendaevents
            WHERE idpatient = %s
            """,
            (patient_guid,)
        )
        appointments_count, first_appointment, last_appointment = cursor.fetchone()

        return {
            'guid': row[0],
            'patientid': row[1],
            'name': row[2],
            'surname': row[3],
            'nationalcode': row[4],
            'email': row[5],
            'phone': row[6],
            'birthdate': row[7].isoformat() if row[7] else None,
            'gender': row[8],
            'patientdomain_id': row[9],
            'healthcard': row[10],
            'stats': {
                'studies_total': studies_count or 0,
                'studies_reported': reported_count or 0,
                'last_study_at': last_study.isoformat() if last_study else None,
                'appointments_total': appointments_count or 0,
                'first_appointment_at': first_appointment.isoformat() if first_appointment else None,
                'last_appointment_at': last_appointment.isoformat() if last_appointment else None,
            }
        }
    finally:
        cursor.close()
        connection.close()


def _get_patient_studies_context(user_id, patient_guid, limit, reported_only=False):
    db_config = _get_db_config()
    connection = psycopg2.connect(**db_config)
    cursor = connection.cursor()

    try:
        user_domains = _get_user_patientdomain_ids(cursor, user_id)
        if not user_domains:
            return []

        user_locations = _get_user_locations(cursor, user_id)
        where_clauses = [
            "e.idpatient = %s",
            "dp.id_patientdomain = ANY(%s)",
        ]
        params = [patient_guid, user_domains]

        if user_locations:
            where_clauses.append("(eq.location_id = ANY(%s) OR eq.location_id IS NULL)")
            params.append(user_locations)

        if reported_only:
            where_clauses.append("(COALESCE(e.isreported, 0) = 1 OR rep.idexamination IS NOT NULL)")

        params.append(limit)

        cursor.execute(
            f"""
            SELECT e.guid,
                   e.createdon,
                   e.localacc,
                   e.status,
                   e.isreported,
                   e.isexecuted,
                   e.studyinstanceuid,
                   st.description,
                   rep.pdfpath,
                   eq.aetitle,
                   loc.name
            FROM nextris.tbexamination e
            INNER JOIN nextris.datapatient dp ON dp.guid = e.idpatient
            LEFT JOIN nextris.isstudytype st ON st.guid = e.studytype_id
            LEFT JOIN nextris.tbreport rep ON rep.idexamination = e.guid
            LEFT JOIN nextris.isequipment eq ON eq.guid = e.idequipment
            LEFT JOIN nextris.tblocation loc ON loc.guid = eq.location_id
                        WHERE {' AND '.join(where_clauses)}
            ORDER BY e.createdon DESC
            LIMIT %s
            """,
            tuple(params)
        )

        studies = []
        for row in cursor.fetchall():
            studies.append({
                'guid': row[0],
                'created_on': row[1].isoformat() if row[1] else None,
                'local_accession': row[2],
                'status': row[3],
                'is_reported': bool(row[4]),
                'is_executed': bool(row[5]),
                'study_instance_uid': row[6],
                'study_type': row[7],
                'report_pdf_path': row[8],
                'equipment_aetitle': row[9],
                'location_name': row[10],
            })

        return studies
    finally:
        cursor.close()
        connection.close()


def _get_agenda_context(user_id, date_from, date_to, patient_guid, equipment_aetitle, limit):
    db_config = _get_db_config()
    connection = psycopg2.connect(**db_config)
    cursor = connection.cursor()

    try:
        user_locations = _get_user_locations(cursor, user_id)
        where_clauses = ["a.comienzo >= %s", "a.comienzo < %s"]
        params = [date_from, date_to]

        if user_locations:
            where_clauses.append("eq.location_id = ANY(%s)")
            params.append(user_locations)

        if patient_guid:
            where_clauses.append("a.idpatient = %s")
            params.append(patient_guid)

        if equipment_aetitle:
            where_clauses.append("eq.aetitle = %s")
            params.append(equipment_aetitle)

        params.append(limit)

        cursor.execute(
            f"""
            SELECT a.guid,
                   a.comienzo,
                   a.fin,
                   p.guid,
                   p.name,
                   p.surname,
                   p.nationalcode,
                   st.description,
                   eq.aetitle,
                   loc.name,
                   loc.timezone
            FROM nextris.tbagendaevents a
            LEFT JOIN nextris.datapatient p ON p.guid = a.idpatient
            LEFT JOIN nextris.isstudytype st ON st.guid = a.idexam
            LEFT JOIN nextris.isequipment eq ON eq.guid = a.idequipment
            LEFT JOIN nextris.tblocation loc ON loc.guid = eq.location_id
            WHERE {' AND '.join(where_clauses)}
            ORDER BY a.comienzo ASC
            LIMIT %s
            """,
            tuple(params)
        )

        events = []
        for row in cursor.fetchall():
            events.append({
                'guid': row[0],
                'start': row[1].isoformat() if row[1] else None,
                'end': row[2].isoformat() if row[2] else None,
                'patient_guid': row[3],
                'patient_name': f"{row[5] or ''} {row[4] or ''}".strip(),
                'patient_nationalcode': row[6],
                'study_type': row[7],
                'equipment_aetitle': row[8],
                'location_name': row[9],
                'timezone': row[10],
            })

        return events
    finally:
        cursor.close()
        connection.close()


def _format_anthropic_error(exc: Exception) -> str:
    message = str(exc)
    lowered = message.lower()

    if 'credit balance is too low' in lowered or 'purchase credits' in lowered:
        return 'La cuenta de Claude no tiene saldo disponible para responder en este momento. Revisá Plans & Billing de Anthropic.'

    return f'Error al consultar Claude: {message}'


def _extract_patient_search_term(message: str) -> str | None:
    """Extracts a probable patient search term from a study-related question."""
    text = (message or '').strip()
    if not text:
        return None

    term = None
    patterns = [
        # "ultimo estudio de Lucia Diaz"
        r"(?:estudio|estudios|paciente|historial)\s+(?:de|del|para)\s+([a-zA-Z0-9ÁÉÍÓÚáéíóúÑñ\-\s']{3,80})",
        # "ultimo estudio con reporte de Lucia Diaz"
        r"(?:estudio|estudios|paciente|historial)(?:\s+(?:con|sin)\s+(?:reporte|informe|resultado)s?)?\s+(?:de|del|para)\s+([a-zA-Z0-9ÁÉÍÓÚáéíóúÑñ\-\s']{3,80})",
        # fallback when sentence already contains study intent and then "de <persona>"
        r"(?:ultimo|ultimos|reciente|recientes)?\s*(?:estudio|estudios|reporte|informes?).*?\b(?:de|del)\s+([a-zA-Z0-9ÁÉÍÓÚáéíóúÑñ\-\s']{3,80})",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            term = match.group(1).strip(" .,:;!?\"'")
            break

    if not term:
        return None

    # Remove trailing qualifiers that are not part of patient name (e.g. "con reporte").
    term = re.sub(
        r"\s+(?:con|sin)\s+(?:reporte|informe|resultado)s?$",
        "",
        term,
        flags=re.IGNORECASE,
    ).strip(" .,:;!?\"'")
    if len(term) < 3:
        return None

    return term


def _wants_reported_only(message: str) -> bool:
    """Detects if user requests studies with report."""
    text = (message or '').lower()
    patterns = [
        r"\bcon\s+reporte\b",
        r"\bcon\s+informe\b",
        r"\breportado\b",
        r"\binformado\b",
        r"\bque\s+este\s+reportado\b",
    ]
    return any(re.search(pattern, text) for pattern in patterns)


def _build_images_link(study_instance_uid: str | None, exam_guid: str | None = None) -> str | None:
    """Builds an external viewer link for study images."""
    uid = (study_instance_uid or '').strip()
    if not uid:
        return None

    viewer_url = (os.getenv('DICOM_VIEWER_URL') or '').strip()
    # Guard against malformed/sensitive env values; fallback to canonical viewer URL.
    if not viewer_url or 'anthropic' in viewer_url.lower() or 'api_key' in viewer_url.lower():
        viewer_url = 'https://viewer.nextris.cloud/viewer'

    viewer_url = viewer_url.replace('viewer.html', 'viewer')
    base = viewer_url.split('?', 1)[0].rstrip('/')
    if not base.lower().startswith('http') or 'viewer.nextris.cloud' not in base.lower():
        base = 'https://viewer.nextris.cloud/viewer'

    url = f"{base}?StudyInstanceUIDs={uid}"
    if exam_guid:
        url = f"{url}&exam_id={exam_guid}"
    return url


def _build_report_link(study: dict, base_url: str) -> str | None:
    """Builds a link for report visualization/download."""
    exam_guid = (study.get('guid') or '').strip()
    if exam_guid:
        encoded_exam = quote(exam_guid)
        return f"{base_url.rstrip('/')}/api/pdfs/by-exam/{encoded_exam}"

    report_path = (study.get('report_pdf_path') or '').strip()

    if report_path:
        # Backward-compatible fallback by filename.
        safe_filename = os.path.basename(report_path)
        if safe_filename:
            encoded = quote(safe_filename)
            return f"{base_url.rstrip('/')}/api/pdfs/{encoded}"

    return None


def _extract_patient_id_term(message: str) -> str | None:
    """Extracts patient identifier terms like patient ID or DNI from free text."""
    text = (message or '').strip()
    if not text:
        return None

    match = re.search(
        r"(?:id\s*(?:de)?\s*paciente|patient[_\s-]?id|dni|documento)\s*(?:es|:)?\s*([A-Za-z0-9\-]{3,40})",
        text,
        flags=re.IGNORECASE,
    )
    if match:
        return match.group(1).strip()

    # Fallback for terse messages like: "NR00000002"
    standalone = re.search(r"\b([A-Za-z]{1,6}\d{3,20}|\d{6,20})\b", text)
    if standalone and len(text.split()) <= 6:
        return standalone.group(1).strip()

    return None


def _extract_accession_number_term(message: str) -> str | None:
    """Extracts study accession/local accession from free text."""
    text = (message or '').strip()
    if not text:
        return None

    labeled = re.search(
        r"(?:accesi[oó]n|accession|localacc|n[úu]mero\s+de\s+accesi[oó]n)\s*(?:number|nro|n[uú]mero|num)?\s*(?:es|:)?\s*([A-Za-z0-9\-]{3,40})",
        text,
        flags=re.IGNORECASE,
    )
    if labeled:
        return labeled.group(1).strip().upper()

    acc_token = re.search(r"\bACC[0-9A-Za-z\-]{2,30}\b", text, flags=re.IGNORECASE)
    if acc_token:
        return acc_token.group(0).strip().upper()

    return None


def _extract_dni_term(message: str) -> str | None:
    """Extracts DNI/document number from free text."""
    text = (message or '').strip()
    if not text:
        return None

    labeled = re.search(
        r"(?:dni|documento|n[úu]mero\s+de\s+documento)\s*(?:es|:)?\s*([0-9]{6,12})",
        text,
        flags=re.IGNORECASE,
    )
    if labeled:
        return labeled.group(1).strip()

    return None


def _extract_study_date_term(message: str) -> str | None:
    """Extracts date filter in YYYY-MM-DD from free text if present."""
    text = (message or '').strip()
    if not text:
        return None

    iso_match = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", text)
    if iso_match:
        try:
            return datetime.strptime(iso_match.group(1), '%Y-%m-%d').date().isoformat()
        except ValueError:
            pass

    slash_match = re.search(r"\b(\d{2})/(\d{2})/(\d{4})\b", text)
    if slash_match:
        try:
            day, month, year = slash_match.groups()
            parsed = datetime.strptime(f"{year}-{month}-{day}", '%Y-%m-%d').date()
            return parsed.isoformat()
        except ValueError:
            pass

    return None


def _search_studies_with_filters_context(
    user_id,
    accession_number: str | None,
    dni: str | None,
    study_date_iso: str | None,
    reported_only: bool,
    limit: int,
):
    """Searches studies by accession number, DNI and/or date respecting user scope."""
    db_config = _get_db_config()
    connection = psycopg2.connect(**db_config)
    cursor = connection.cursor()

    try:
        user_domains = _get_user_patientdomain_ids(cursor, user_id)
        if not user_domains:
            return []

        user_locations = _get_user_locations(cursor, user_id)
        where_clauses = ["dp.id_patientdomain = ANY(%s)"]
        params = [user_domains]

        if user_locations:
            where_clauses.append("(eq.location_id = ANY(%s) OR eq.location_id IS NULL)")
            params.append(user_locations)

        if accession_number:
            where_clauses.append("e.localacc ILIKE %s")
            params.append(accession_number)

        if dni:
            where_clauses.append("dp.nationalcode = %s")
            params.append(dni)

        if study_date_iso:
            where_clauses.append("DATE(e.createdon) = %s")
            params.append(study_date_iso)

        if reported_only:
            where_clauses.append("(COALESCE(e.isreported, 0) = 1 OR rep.idexamination IS NOT NULL)")

        params.append(limit)

        cursor.execute(
            f"""
            SELECT e.guid,
                   e.createdon,
                   e.localacc,
                   e.status,
                   e.isreported,
                   e.isexecuted,
                   e.studyinstanceuid,
                   st.description,
                   rep.pdfpath,
                   eq.aetitle,
                   loc.name,
                   dp.guid,
                   dp.patientid,
                   dp.name,
                   dp.surname,
                   dp.nationalcode
            FROM nextris.tbexamination e
            INNER JOIN nextris.datapatient dp ON dp.guid = e.idpatient
            LEFT JOIN nextris.isstudytype st ON st.guid = e.studytype_id
            LEFT JOIN nextris.tbreport rep ON rep.idexamination = e.guid
            LEFT JOIN nextris.isequipment eq ON eq.guid = e.idequipment
            LEFT JOIN nextris.tblocation loc ON loc.guid = eq.location_id
            WHERE {' AND '.join(where_clauses)}
            ORDER BY e.createdon DESC
            LIMIT %s
            """,
            tuple(params),
        )

        studies = []
        for row in cursor.fetchall():
            studies.append({
                'guid': row[0],
                'created_on': row[1].isoformat() if row[1] else None,
                'local_accession': row[2],
                'status': row[3],
                'is_reported': bool(row[4]),
                'is_executed': bool(row[5]),
                'study_instance_uid': row[6],
                'study_type': row[7],
                'report_pdf_path': row[8],
                'equipment_aetitle': row[9],
                'location_name': row[10],
                'patient_guid': row[11],
                'patientid': row[12],
                'patient_name': row[13],
                'patient_surname': row[14],
                'patient_dni': row[15],
            })

        return studies
    finally:
        cursor.close()
        connection.close()


def _build_studies_context_block(user_id, user_message: str, base_url: str) -> str | None:
    """Builds an internal context block for patient-study queries."""
    search_term = _extract_patient_search_term(user_message)
    id_term = _extract_patient_id_term(user_message)
    accession_number = _extract_accession_number_term(user_message)
    dni_term = _extract_dni_term(user_message)
    study_date_iso = _extract_study_date_term(user_message)
    reported_only = _wants_reported_only(user_message)

    has_direct_study_filters = bool(accession_number or dni_term or study_date_iso)

    if not search_term and not id_term and not has_direct_study_filters:
        return None

    if has_direct_study_filters:
        try:
            studies = _search_studies_with_filters_context(
                user_id=user_id,
                accession_number=accession_number,
                dni=dni_term,
                study_date_iso=study_date_iso,
                reported_only=reported_only,
                limit=10,
            )
        except Exception:
            current_app.logger.exception('Error consultando estudios por filtros (accesion/dni/fecha) en Nexi')
            return None

        lines = ['CONTEXTO_INTERNO_NEXI:']
        applied = []
        if accession_number:
            applied.append(f"accesion={accession_number}")
        if dni_term:
            applied.append(f"dni={dni_term}")
        if study_date_iso:
            applied.append(f"fecha={study_date_iso}")

        lines.append(f"- Filtros aplicados: {', '.join(applied) if applied else 'sin filtros'}")

        if not studies:
            lines.append('- No se encontraron estudios con esos filtros dentro del alcance de acceso del usuario actual.')
            return '\n'.join(lines)

        lines.append(f"- Estudios encontrados: {len(studies)} (ordenados por fecha descendente)")
        for study in studies:
            report_link = _build_report_link(study, base_url)
            images_link = _build_images_link(study.get('study_instance_uid'), study.get('guid'))
            lines.append(
                f"  - paciente={study.get('patient_surname', '')} {study.get('patient_name', '')} | "
                f"dni={study.get('patient_dni') or 'N/D'} | patientid={study.get('patientid') or 'N/D'} | "
                f"fecha={study.get('created_on') or 'N/D'} | local_accession={study.get('local_accession') or 'N/D'} | "
                f"tipo={study.get('study_type') or 'N/D'} | estado={study.get('status') or 'N/D'} | "
                f"is_reported={study.get('is_reported')} | report_link={report_link or 'N/D'} | images_link={images_link or 'N/D'}"
            )

        if reported_only:
            lines.append('- El usuario pidio estudios con reporte: no devuelvas estudios sin reporte.')
        lines.append('- Responde priorizando el primer estudio cuando pidan "el ultimo".')
        lines.append('- Si hay report_link o images_link, incluilos explicitamente en la respuesta al usuario.')
        return '\n'.join(lines)

    if id_term:
        search_term = id_term

    if not search_term:
        return None

    try:
        candidates = _search_patients_context(user_id, search_term, 5)
    except Exception:
        current_app.logger.exception('Error buscando pacientes para contexto automatico de Nexi')
        return None

    if id_term and candidates:
        id_term_normalized = id_term.strip().lower()
        exact = [
            c for c in candidates
            if (c.get('patientid') and str(c.get('patientid')).strip().lower() == id_term_normalized)
            or (c.get('nationalcode') and str(c.get('nationalcode')).strip().lower() == id_term_normalized)
        ]
        if exact:
            candidates = exact

    if not candidates:
        return (
            "CONTEXTO_INTERNO_NEXI:\n"
            f"- No se encontraron pacientes para el termino '{search_term}'.\n"
            "- Debes pedir al usuario mas identificadores: nombre completo, DNI o patient_id."
        )

    if len(candidates) > 1:
        lines = [
            'CONTEXTO_INTERNO_NEXI:',
            f"- Se encontraron {len(candidates)} pacientes para '{search_term}':",
        ]
        for item in candidates:
            lines.append(
                f"  - guid={item.get('guid')} | nombre={item.get('surname', '')} {item.get('name', '')} | "
                f"dni={item.get('nationalcode') or 'N/D'} | patientid={item.get('patientid') or 'N/D'}"
            )
        lines.append('- Debes pedir confirmacion explicita del paciente antes de informar estudios.')
        return '\n'.join(lines)

    patient = candidates[0]
    patient_guid = patient.get('guid')
    if not patient_guid:
        return None

    try:
        studies = _get_patient_studies_context(user_id, patient_guid, 5, reported_only=reported_only)
    except Exception:
        current_app.logger.exception('Error consultando estudios para contexto automatico de Nexi')
        return None

    header = [
        'CONTEXTO_INTERNO_NEXI:',
        '- Paciente identificado de forma univoca:',
        f"  - guid={patient_guid} | nombre={patient.get('surname', '')} {patient.get('name', '')} | "
        f"dni={patient.get('nationalcode') or 'N/D'} | patientid={patient.get('patientid') or 'N/D'}",
    ]

    if not studies:
        if reported_only:
            header.append('- No hay estudios reportados disponibles para este paciente en el alcance de acceso del usuario actual.')
        else:
            header.append('- No hay estudios disponibles para este paciente en el alcance de acceso del usuario actual.')
        return '\n'.join(header)

    if reported_only:
        header.append('- Ultimos estudios con reporte (max 5):')
    else:
        header.append('- Ultimos estudios (max 5):')

    for study in studies:
        report_link = _build_report_link(study, base_url)
        images_link = _build_images_link(study.get('study_instance_uid'), study.get('guid'))
        header.append(
            f"  - fecha={study.get('created_on') or 'N/D'} | tipo={study.get('study_type') or 'N/D'} | "
            f"estado={study.get('status') or 'N/D'} | is_reported={study.get('is_reported')} | "
            f"local_accession={study.get('local_accession') or 'N/D'} | "
            f"report_link={report_link or 'N/D'} | images_link={images_link or 'N/D'}"
        )

    if reported_only:
        header.append('- El usuario pidio estudios con reporte: no devuelvas estudios sin reporte.')
    header.append('- Si el usuario pidio el ultimo estudio, usar el primer elemento de la lista (orden descendente por fecha).')
    header.append('- Si hay report_link o images_link, incluilos explicitamente en la respuesta al usuario.')
    return '\n'.join(header)


@api_blueprint.route('/nexi/directives', methods=['GET'])
@jwt_required()
def get_nexi_directives():
    directives = _load_nexi_directives()

    return jsonify({
        'success': True,
        'data': {
            'directives': directives,
            'capabilities': [
                'patients_search',
                'patient_summary',
                'patient_study_history',
                'agenda_search',
            ],
            'mode': 'read-only'
        }
    }), 200


@api_blueprint.route('/nexi/context/patients/search', methods=['GET'])
@jwt_required()
def nexi_search_patients_context():
    user_id = get_jwt_identity()
    search_term = request.args.get('q', '').strip()
    limit = request.args.get('limit', 10, type=int)
    limit = max(1, min(limit, 25))

    if len(search_term) < 2:
        return jsonify({
            'success': False,
            'error': 'El parametro q debe tener al menos 2 caracteres'
        }), 400

    try:
        return jsonify({
            'success': True,
            'data': _search_patients_context(user_id, search_term, limit)
        }), 200
    except Exception as exc:
        current_app.logger.exception('Error en contexto Nexi: search patients')
        return jsonify({'success': False, 'error': str(exc)}), 500


@api_blueprint.route('/nexi/context/patients/<patient_guid>', methods=['GET'])
@jwt_required()
def nexi_get_patient_context(patient_guid):
    user_id = get_jwt_identity()

    try:
        patient = _get_patient_summary_context(user_id, patient_guid)
        if not patient:
            return jsonify({'success': False, 'error': 'Paciente no encontrado o sin acceso'}), 404

        return jsonify({'success': True, 'data': patient}), 200
    except Exception as exc:
        current_app.logger.exception('Error en contexto Nexi: patient summary')
        return jsonify({'success': False, 'error': str(exc)}), 500


@api_blueprint.route('/nexi/context/patients/<patient_guid>/studies', methods=['GET'])
@jwt_required()
def nexi_get_patient_studies_context(patient_guid):
    user_id = get_jwt_identity()
    limit = request.args.get('limit', 20, type=int)
    limit = max(1, min(limit, 50))

    try:
        patient = _get_patient_summary_context(user_id, patient_guid)
        if not patient:
            return jsonify({'success': False, 'error': 'Paciente no encontrado o sin acceso'}), 404

        studies = _get_patient_studies_context(user_id, patient_guid, limit)
        return jsonify({
            'success': True,
            'data': {
                'patient': {
                    'guid': patient['guid'],
                    'patientid': patient['patientid'],
                    'name': patient['name'],
                    'surname': patient['surname'],
                    'nationalcode': patient['nationalcode'],
                },
                'studies': studies,
            }
        }), 200
    except Exception as exc:
        current_app.logger.exception('Error en contexto Nexi: patient studies')
        return jsonify({'success': False, 'error': str(exc)}), 500


@api_blueprint.route('/nexi/context/agenda', methods=['GET'])
@jwt_required()
def nexi_get_agenda_context():
    user_id = get_jwt_identity()
    date_from_raw = request.args.get('date_from')
    date_to_raw = request.args.get('date_to')
    patient_guid = request.args.get('patient_guid')
    equipment_aetitle = request.args.get('equipment_aetitle')
    limit = request.args.get('limit', 25, type=int)
    limit = max(1, min(limit, 100))

    try:
        if date_from_raw:
            date_from = datetime.strptime(date_from_raw, '%Y-%m-%d')
        else:
            date_from = datetime.utcnow()

        if date_to_raw:
            date_to = datetime.strptime(date_to_raw, '%Y-%m-%d') + timedelta(days=1)
        else:
            date_to = date_from + timedelta(days=7)

        events = _get_agenda_context(user_id, date_from, date_to, patient_guid, equipment_aetitle, limit)
        return jsonify({
            'success': True,
            'data': {
                'filters': {
                    'date_from': date_from.isoformat(),
                    'date_to': date_to.isoformat(),
                    'patient_guid': patient_guid,
                    'equipment_aetitle': equipment_aetitle,
                    'limit': limit,
                },
                'events': events,
            }
        }), 200
    except ValueError:
        return jsonify({'success': False, 'error': 'Formato de fecha invalido. Use YYYY-MM-DD'}), 400
    except Exception as exc:
        current_app.logger.exception('Error en contexto Nexi: agenda')
        return jsonify({'success': False, 'error': str(exc)}), 500


@api_blueprint.route('/nexi/chat', methods=['POST'])
@jwt_required()
def nexi_chat():
    """Proxy de chat Nexi hacia Claude (Anthropic)."""
    if Anthropic is None:
        return jsonify({
            'success': False,
            'error': 'Dependencia anthropic no instalada en backend'
        }), 500

    api_key = os.getenv('ANTHROPIC_API_KEY', '').strip()
    if not api_key:
        return jsonify({
            'success': False,
            'error': 'ANTHROPIC_API_KEY no configurada en el servidor'
        }), 500

    user_id = get_jwt_identity()
    payload = request.get_json(silent=True) or {}
    user_message = (payload.get('message') or '').strip()
    history = payload.get('history') or []

    if not user_message:
        return jsonify({
            'success': False,
            'error': 'El mensaje es obligatorio'
        }), 400

    model = os.getenv('ANTHROPIC_MODEL', 'claude-sonnet-4-20250514').strip()
    directives = _load_nexi_directives()

    # Convertimos el historial al formato esperado por Anthropic
    anthropic_messages = []
    for item in history:
        role = item.get('role')
        content = (item.get('content') or '').strip()
        if role in ('user', 'assistant') and content:
            anthropic_messages.append({
                'role': role,
                'content': content
            })

    base_url = request.host_url.rstrip('/')
    auto_context = _build_studies_context_block(user_id, user_message, base_url)
    system_prompt = directives
    if auto_context:
        system_prompt = f"{directives}\n\n{auto_context}"

    anthropic_messages.append({
        'role': 'user',
        'content': user_message
    })

    try:
        client = Anthropic(api_key=api_key)
        response = client.messages.create(
            model=model,
            max_tokens=1024,
            temperature=0.2,
            system=system_prompt,
            messages=anthropic_messages
        )

        text_parts = []
        for block in getattr(response, 'content', []) or []:
            if getattr(block, 'type', None) == 'text':
                text_parts.append(getattr(block, 'text', ''))

        reply = '\n'.join([t for t in text_parts if t]).strip()
        if not reply:
            reply = 'No pude generar una respuesta en este momento.'

        return jsonify({
            'success': True,
            'reply': reply,
            'model': model
        }), 200

    except Exception as exc:
        current_app.logger.exception('Error consultando Claude desde Nexi')
        return jsonify({
            'success': False,
            'error': _format_anthropic_error(exc)
        }), 502
