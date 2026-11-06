BEGIN;
DO $$ BEGIN
 IF EXISTS(SELECT 1 FROM nextris.datapatient WHERE patient_kind='animal')
 OR EXISTS(SELECT 1 FROM nextris.responsible_party)
 OR EXISTS(SELECT 1 FROM nextris.veterinary_protocol)
 OR EXISTS(SELECT 1 FROM nextris.tbuser_patient WHERE responsible_party_id IS NOT NULL)
 OR EXISTS(SELECT 1 FROM nextris.tbinfpredef WHERE patient_kind<>'human')
 OR EXISTS(SELECT 1 FROM nextris.veterinary_breed)
 OR EXISTS(SELECT 1 FROM nextris.veterinary_species WHERE id NOT IN ('a0000000-0000-4000-8000-000000000001','a0000000-0000-4000-8000-000000000002'))
 OR EXISTS(SELECT 1 FROM nextris.veterinary_species WHERE code_value IS NOT NULL OR coding_scheme IS NOT NULL OR (id='a0000000-0000-4000-8000-000000000001' AND name<>'Canino') OR (id='a0000000-0000-4000-8000-000000000002' AND name<>'Felino'))
 OR EXISTS(SELECT 1 FROM nextris.tbreport WHERE veterinary_context IS NOT NULL)
 OR EXISTS(SELECT 1 FROM nextris.tbexamination WHERE veterinary_context IS NOT NULL)
 OR EXISTS(SELECT 1 FROM nextris.tbagendaevents WHERE veterinary_context IS NOT NULL)
 THEN RAISE EXCEPTION 'Veterinary data exists. Downgrade refused to prevent data loss; keep the additive schema or export and verify recovery first.'; END IF;
END $$;
ALTER TABLE nextris.tbviewer_share_link DROP COLUMN portal_account_id, DROP COLUMN patient_id;
ALTER TABLE nextris.tbreport DROP COLUMN veterinary_context;
ALTER TABLE nextris.tbinfpredef DROP COLUMN patient_kind, DROP COLUMN species_id;
ALTER TABLE nextris.tbagendaevents DROP COLUMN veterinary_protocol_id, DROP COLUMN veterinary_context;
ALTER TABLE nextris.tbexamination DROP COLUMN veterinary_protocol_id, DROP COLUMN veterinary_context;
DROP INDEX nextris.veterinary_portal_account_username;
ALTER TABLE nextris.tbuser_patient DROP CONSTRAINT portal_subject_exclusive, DROP COLUMN responsible_party_id, DROP COLUMN portal_auth_version;
ALTER TABLE nextris.tbuser_patient ALTER COLUMN datapatient_id SET NOT NULL;
DROP TABLE nextris.patient_clinical_entry;
DROP TABLE nextris.patient_responsibility;
DROP TABLE nextris.responsible_party;
DROP TABLE nextris.veterinary_protocol;
ALTER TABLE nextris.datapatient DROP CONSTRAINT veterinary_breed_species;
DROP INDEX nextris.veterinary_patient_identifier;
ALTER TABLE nextris.datapatient DROP COLUMN patient_kind, DROP COLUMN species_id, DROP COLUMN breed_id, DROP COLUMN birthdate_estimated, DROP COLUMN reproductive_status;
DROP TABLE nextris.veterinary_breed;
DROP TABLE nextris.veterinary_species;
DROP SEQUENCE nextris.veterinary_patient_number;
COMMIT;
