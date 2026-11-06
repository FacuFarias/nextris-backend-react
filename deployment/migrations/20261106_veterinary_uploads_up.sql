BEGIN;
CREATE TABLE nextris.veterinary_upload_session (
 id uuid PRIMARY KEY,
 created_by varchar(50) NOT NULL REFERENCES nextris.tbuser(guid),
 state text NOT NULL DEFAULT 'receiving' CHECK (state IN
 ('receiving','queued_analysis','analyzing','ready','rejected','queued_transfer','transferring','verifying','retryable','completed','cancelled','expired')),
 total_bytes bigint NOT NULL DEFAULT 0 CHECK(total_bytes>=0),
 summary jsonb NOT NULL DEFAULT '{}',
 selection jsonb NOT NULL DEFAULT '{}',
 result jsonb NOT NULL DEFAULT '{}',
 transfer_started boolean NOT NULL DEFAULT false,
 error text,
 created_at timestamptz NOT NULL DEFAULT now(),
 updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX veterinary_upload_queue ON nextris.veterinary_upload_session(state,updated_at);
CREATE UNIQUE INDEX veterinary_upload_study_reservation ON nextris.veterinary_upload_session((summary->>'study_uid'))
 WHERE state IN ('queued_transfer','transferring','verifying','retryable');
CREATE TABLE nextris.veterinary_upload_file (
 id uuid PRIMARY KEY,
 session_id uuid NOT NULL REFERENCES nextris.veterinary_upload_session(id),
 name text NOT NULL,
 kind text NOT NULL DEFAULT 'input' CHECK(kind IN ('input','zip','dicom','ignored','duplicate')),
 expected_bytes bigint NOT NULL CHECK(expected_bytes>=0),
 received_bytes bigint NOT NULL DEFAULT 0 CHECK(received_bytes>=0 AND received_bytes<=expected_bytes),
 sha256 text,
 prepared_sha256 text,
 sop_uid text,
 series_uid text,
 metadata jsonb NOT NULL DEFAULT '{}',
 sent boolean NOT NULL DEFAULT false,
 verified boolean NOT NULL DEFAULT false,
 error text,
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX veterinary_upload_files_session ON nextris.veterinary_upload_file(session_id);
CREATE UNIQUE INDEX veterinary_upload_sop ON nextris.veterinary_upload_file(session_id,sop_uid) WHERE kind='dicom';
COMMIT;
