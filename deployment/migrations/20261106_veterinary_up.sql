BEGIN;
CREATE SEQUENCE IF NOT EXISTS nextris.veterinary_patient_number;
CREATE TABLE IF NOT EXISTS nextris.veterinary_species (
 id uuid PRIMARY KEY, name text NOT NULL UNIQUE, code_value text, coding_scheme text,
 is_active boolean NOT NULL DEFAULT true,
 CHECK ((code_value IS NULL) = (coding_scheme IS NULL))
);
CREATE TABLE IF NOT EXISTS nextris.veterinary_breed (
 id uuid PRIMARY KEY, species_id uuid NOT NULL REFERENCES nextris.veterinary_species(id),
 name text NOT NULL, code_value text, coding_scheme text, is_active boolean NOT NULL DEFAULT true,
 UNIQUE(species_id,name), UNIQUE(id,species_id),
 CHECK ((code_value IS NULL) = (coding_scheme IS NULL))
);
INSERT INTO nextris.veterinary_species(id,name) VALUES
 ('a0000000-0000-4000-8000-000000000001','Canino'),
 ('a0000000-0000-4000-8000-000000000002','Felino') ON CONFLICT DO NOTHING;
ALTER TABLE nextris.datapatient
 ADD COLUMN patient_kind text NOT NULL DEFAULT 'human' CHECK(patient_kind IN ('human','animal')),
 ADD COLUMN species_id uuid REFERENCES nextris.veterinary_species(id),
 ADD COLUMN breed_id uuid,
 ADD COLUMN birthdate_estimated boolean NOT NULL DEFAULT false,
 ADD COLUMN reproductive_status text NOT NULL DEFAULT 'unknown' CHECK(reproductive_status IN ('unknown','intact','neutered')),
 ADD CONSTRAINT veterinary_breed_species FOREIGN KEY(breed_id,species_id) REFERENCES nextris.veterinary_breed(id,species_id);
CREATE UNIQUE INDEX veterinary_patient_identifier ON nextris.datapatient(patientid) WHERE patient_kind='animal';
CREATE TABLE nextris.responsible_party (
 id uuid PRIMARY KEY, kind text NOT NULL CHECK(kind IN ('person','organization')),
 name text NOT NULL CHECK(length(trim(name))>0), document text, email text, phone text,
 address text, organization text, is_active boolean NOT NULL DEFAULT true,
 created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE nextris.patient_responsibility (
 id uuid PRIMARY KEY, patient_id varchar(50) NOT NULL REFERENCES nextris.datapatient(guid),
 responsible_id uuid NOT NULL REFERENCES nextris.responsible_party(id),
 role text NOT NULL CHECK(role IN ('owner','guardian','custodian','veterinarian')),
 is_primary boolean NOT NULL DEFAULT false, portal_authorized boolean NOT NULL DEFAULT false,
 valid_from timestamptz NOT NULL DEFAULT now(), valid_to timestamptz,
 created_by varchar(50), ended_by varchar(50), reason text,
 CHECK(valid_to IS NULL OR valid_to>=valid_from)
);
CREATE UNIQUE INDEX veterinary_primary_responsible ON nextris.patient_responsibility(patient_id) WHERE is_primary AND valid_to IS NULL;
CREATE UNIQUE INDEX veterinary_active_responsible ON nextris.patient_responsibility(patient_id,responsible_id) WHERE valid_to IS NULL;
CREATE INDEX veterinary_responsible_access ON nextris.patient_responsibility(responsible_id,patient_id) WHERE portal_authorized AND valid_to IS NULL;
CREATE TABLE nextris.patient_clinical_entry (
 id uuid PRIMARY KEY, patient_id varchar(50) NOT NULL REFERENCES nextris.datapatient(guid),
 category text NOT NULL CHECK(category IN ('history','alert','weight','correction')),
 note text NOT NULL DEFAULT '', weight_kg numeric(12,3) CHECK(weight_kg>0),
 recorded_at timestamptz NOT NULL DEFAULT now(), created_at timestamptz NOT NULL DEFAULT now(),
 created_by varchar(50), corrects_id uuid REFERENCES nextris.patient_clinical_entry(id),
 CHECK(category<>'weight' OR weight_kg IS NOT NULL)
);
CREATE INDEX veterinary_clinical_history ON nextris.patient_clinical_entry(patient_id,recorded_at DESC);
CREATE TABLE nextris.veterinary_protocol (
 id uuid PRIMARY KEY, name text NOT NULL, species_id uuid REFERENCES nextris.veterinary_species(id),
 study_type_id varchar(50) REFERENCES nextris.isstudytype(guid),
 modality_id varchar(50) REFERENCES nextris.ismodality(guid),
 bodypart_id varchar(50) REFERENCES nextris.isanatomicalpart(guid),
 min_weight_kg numeric(12,3) CHECK(min_weight_kg>=0), max_weight_kg numeric(12,3) CHECK(max_weight_kg>0),
 preparation text NOT NULL DEFAULT '', checklist jsonb NOT NULL DEFAULT '[]',
 is_active boolean NOT NULL DEFAULT true, created_by varchar(50), updated_at timestamptz NOT NULL DEFAULT now(),
 CHECK(min_weight_kg IS NULL OR max_weight_kg IS NULL OR min_weight_kg<=max_weight_kg),
 CHECK(jsonb_typeof(checklist)='array')
);
ALTER TABLE nextris.tbuser_patient ALTER COLUMN datapatient_id DROP NOT NULL;
ALTER TABLE nextris.tbuser_patient ADD COLUMN responsible_party_id uuid REFERENCES nextris.responsible_party(id),
 ADD COLUMN portal_auth_version integer NOT NULL DEFAULT 0,
 ADD CONSTRAINT portal_subject_exclusive CHECK((datapatient_id IS NOT NULL)::int+(responsible_party_id IS NOT NULL)::int=1);
CREATE UNIQUE INDEX veterinary_portal_account_username ON nextris.tbuser_patient(lower(username)) WHERE responsible_party_id IS NOT NULL;
ALTER TABLE nextris.tbexamination ADD COLUMN veterinary_protocol_id uuid REFERENCES nextris.veterinary_protocol(id), ADD COLUMN veterinary_context jsonb;
ALTER TABLE nextris.tbagendaevents ADD COLUMN veterinary_protocol_id uuid REFERENCES nextris.veterinary_protocol(id), ADD COLUMN veterinary_context jsonb;
ALTER TABLE nextris.tbinfpredef ADD COLUMN patient_kind text NOT NULL DEFAULT 'human' CHECK(patient_kind IN ('human','animal','any')), ADD COLUMN species_id uuid REFERENCES nextris.veterinary_species(id);
ALTER TABLE nextris.tbreport ADD COLUMN veterinary_context jsonb;
ALTER TABLE nextris.tbviewer_share_link ADD COLUMN portal_account_id varchar(50) REFERENCES nextris.tbuser_patient(guid), ADD COLUMN patient_id varchar(50) REFERENCES nextris.datapatient(guid);
COMMIT;
