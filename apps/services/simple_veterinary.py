"""Opt-in workflow policy for the standalone veterinary installation."""
import os
import re


def workflow_profile():
    from apps.services.veterinary import mode
    profile = os.getenv('NEXTRIS_WORKFLOW_PROFILE', 'standard')
    if profile not in ('standard', 'simple_veterinary'):
        raise RuntimeError('Invalid NEXTRIS_WORKFLOW_PROFILE')
    return profile if mode() == 'veterinary' else 'standard'


def enabled():
    return workflow_profile() == 'simple_veterinary'


def report_sql(query):
    """Keep existing report filters/sorts, enriching the catalog projection from DICOM.

    The lateral projection also exists when studytype_id is NULL. No clinical
    study type is fabricated just to make a received study reportable.
    """
    if not enabled():
        return query
    replacement = """LEFT JOIN LATERAL (
        SELECT actual.guid, actual.studygroup_id, actual.bodypart_id, actual.default_predef_id,
            COALESCE(actual.description,NULLIF(ref.metadata #>> '{dicom,study_description}',''),
                NULLIF((SELECT s.study_desc FROM public.study s WHERE s.study_iuid=e.studyinstanceuid LIMIT 1),''),
                'Estudio DICOM') AS description,
            COALESCE(actual.modality_id,(SELECT m.guid FROM nextris.ismodality m
                WHERE upper(m.externalcode)=upper(COALESCE(ref.metadata #>> '{dicom,modality}',
                  (SELECT sr.modality FROM public.series sr JOIN public.study s ON s.pk=sr.study_fk
                   WHERE s.study_iuid=e.studyinstanceuid ORDER BY sr.pk LIMIT 1)))
                ORDER BY m.guid LIMIT 1)) AS modality_id
        FROM (VALUES(1)) seed(n)
        LEFT JOIN nextris.isstudytype actual ON actual.guid=e.studytype_id
        LEFT JOIN LATERAL (SELECT metadata FROM nextris.pacs_auto_order
            WHERE examination_guid=e.guid ORDER BY created_at,study_iuid LIMIT 1) ref ON TRUE
    ) st ON TRUE"""
    return re.sub(r'LEFT\s+JOIN\s+nextris\.isstudytype\s+st\s+ON\s+e\.studytype_id\s*=\s*st\.guid\b',
                  lambda _match: replacement, query, flags=re.IGNORECASE)
