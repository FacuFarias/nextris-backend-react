-- Los hallazgos RMN deben conservar sus párrafos, pero sin texto en negrita.

BEGIN;

UPDATE nextris.tbinfpredef ip
SET findings = regexp_replace(
    regexp_replace(ip.findings, '<strong[^>]*>', '', 'gi'),
    '</strong>',
    '',
    'gi'
)
FROM nextris.isstudytype st
JOIN nextris.ismodality modality ON modality.guid = st.modality_id
WHERE st.guid = ip.studytype_id
  AND UPPER(COALESCE(modality.description, '')) LIKE '%RESONANCIA%'
  AND ip.findings ~* '</?strong';

COMMIT;
