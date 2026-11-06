-- Single-institution conversion. Legacy tables remain archived; no clinical rows are deleted.
BEGIN;
DO $$
DECLARE n bigint;
BEGIN
    IF to_regclass('nextris.tbfacility') IS NOT NULL THEN
        EXECUTE 'LOCK TABLE nextris.tbfacility IN SHARE MODE';
        EXECUTE 'SELECT count(*) FROM nextris.tbfacility' INTO n;
        IF n > 1 THEN
            RAISE EXCEPTION 'Multiple institutions detected (%); select and migrate an institution explicitly before conversion', n;
        END IF;
    END IF;
    IF to_regclass('nextris.ispatientdomain') IS NOT NULL THEN
        EXECUTE 'SELECT count(*) FROM nextris.ispatientdomain' INTO n;
        IF n > 1 THEN
            RAISE EXCEPTION 'Multiple patient domains detected (%); resolve them explicitly before conversion', n;
        END IF;
    END IF;
END $$;
CREATE TABLE IF NOT EXISTS nextris.app_config (
    id integer PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    name varchar(255) NOT NULL DEFAULT 'NextRIS', code varchar(50), email varchar(150),
    contact_person varchar(150), description text, address varchar(255), city varchar(100),
    country varchar(100), phone varchar(50), smtp_server varchar(255), smtp_port integer,
    smtp_user varchar(150), smtp_password varchar(255), smtp_from varchar(150), smtp_from_name varchar(150),
    use_tls boolean DEFAULT true, whatsapp_api_url varchar(500), whatsapp_api_token varchar(500),
    whatsapp_phone_number_id varchar(100), whatsapp_business_account_id varchar(100),
    whatsapp_webhook_verify_token varchar(255), whatsapp_is_active boolean DEFAULT false,
    plan_id varchar(50), created_at timestamp DEFAULT now(), updated_at timestamp DEFAULT now()
);
DO $$
DECLARE legacy jsonb;
BEGIN
    IF to_regclass('nextris.tbfacility') IS NOT NULL THEN
        EXECUTE 'SELECT to_jsonb(f) FROM nextris.tbfacility f' INTO legacy;
        IF legacy IS NOT NULL THEN
            legacy := legacy - 'guid' - 'id' || jsonb_build_object('id', 1);
            INSERT INTO nextris.app_config SELECT (jsonb_populate_record(NULL::nextris.app_config, legacy)).*
            ON CONFLICT (id) DO NOTHING;
        END IF;
    END IF;
END $$;
INSERT INTO nextris.app_config(id, name, code) VALUES (1, 'NextRIS', 'NRIS') ON CONFLICT (id) DO NOTHING;
CREATE TABLE IF NOT EXISTS nextris.app_modules (
    module_id varchar(50) PRIMARY KEY, is_active boolean NOT NULL DEFAULT true, updated_at timestamp DEFAULT now()
);
DO $$
BEGIN
    IF to_regclass('nextris.ismodule') IS NOT NULL THEN
        IF to_regclass('nextris.rel_facility_module') IS NOT NULL THEN
            INSERT INTO nextris.app_modules(module_id, is_active)
            SELECT m.guid, COALESCE(bool_or(r.is_active), true)
            FROM nextris.ismodule m LEFT JOIN nextris.rel_facility_module r ON r.module_id=m.guid
            GROUP BY m.guid ON CONFLICT(module_id) DO NOTHING;
        ELSE
            INSERT INTO nextris.app_modules(module_id,is_active)
            SELECT guid,is_active FROM nextris.ismodule ON CONFLICT(module_id) DO NOTHING;
        END IF;
    END IF;
END $$;
COMMIT;
