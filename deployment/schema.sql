-- =============================================================================
-- NextRIS - Schema Completo: nextris
-- Generado: 2026-05-19 (actualizado desde pg_dump de la BD real)
-- Base de datos: PostgreSQL 17
-- Ejecutar: psql -h $DB_HOST -U $DB_USER -d $DB_NAME -f nextris_schema.sql
-- =============================================================================

BEGIN;

-- Crear schema si no existe
CREATE SCHEMA IF NOT EXISTS nextris;

-- =============================================================================
-- 1. FUNCIONES
-- =============================================================================

CREATE OR REPLACE FUNCTION nextris.fn_assign_location_from_aet()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_location_id VARCHAR(100);
    v_study_iuid VARCHAR(255);
BEGIN
    IF NEW.study_fk IS NULL OR NEW.sending_aet IS NULL OR NEW.sending_aet = '' THEN
        RETURN NEW;
    END IF;

    SELECT l.guid
      INTO v_location_id
      FROM nextris.tblocation l
     WHERE l.gateway_aet = NEW.sending_aet
     LIMIT 1;

    IF v_location_id IS NULL THEN
        RETURN NEW;
    END IF;

    SELECT s.study_iuid
      INTO v_study_iuid
      FROM public.study s
     WHERE s.pk = NEW.study_fk;

    IF v_study_iuid IS NULL THEN
        RETURN NEW;
    END IF;

    UPDATE public.study
    SET location_id = v_location_id
    WHERE pk = NEW.study_fk;

    INSERT INTO nextris.tbpacs_location_assignment (
        pacs_study_pk, pacs_study_iuid, location_id, sending_aet, matched_at
    ) VALUES (
        NEW.study_fk, v_study_iuid, v_location_id, NEW.sending_aet, NOW()
    )
    ON CONFLICT (pacs_study_pk)
    DO UPDATE SET
        pacs_study_iuid = EXCLUDED.pacs_study_iuid,
        location_id = EXCLUDED.location_id,
        sending_aet = EXCLUDED.sending_aet,
        matched_at = NOW();

    RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION nextris.prevent_audit_facility_module_change_mutation()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'audit_facility_module_change es append-only y no permite UPDATE/DELETE';
END;
$$;

-- =============================================================================
-- 2. TABLAS DE CATÁLOGOS / LOOKUP (is*)
-- =============================================================================

CREATE TABLE IF NOT EXISTS nextris.isrole (
    guid        VARCHAR(50) PRIMARY KEY,
    description VARCHAR(150) NOT NULL
);

CREATE TABLE IF NOT EXISTS nextris.isplan (
    guid                  VARCHAR(50) PRIMARY KEY,
    code                  VARCHAR(50) NOT NULL UNIQUE,
    name                  VARCHAR(120) NOT NULL,
    description           TEXT,
    max_receive_monthly   INTEGER,
    max_read_monthly      INTEGER,
    max_distribute_monthly INTEGER,
    dicom_retention_days  INTEGER,
    max_users             INTEGER,
    is_active             BOOLEAN NOT NULL DEFAULT TRUE,
    created_at            TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at            TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS nextris.ismodality (
    guid          VARCHAR(50) PRIMARY KEY,
    externalcode  VARCHAR(50),
    description   VARCHAR(150) NOT NULL
);

CREATE TABLE IF NOT EXISTS nextris.isanatomicalpart (
    guid        VARCHAR(50) PRIMARY KEY,
    description VARCHAR(150) NOT NULL
);

CREATE TABLE IF NOT EXISTS nextris.isstudytypegroup (
    guid        VARCHAR(50) PRIMARY KEY,
    description VARCHAR(150) NOT NULL
);

CREATE TABLE IF NOT EXISTS nextris.isstudytype (
    guid              VARCHAR(50) PRIMARY KEY,
    code              VARCHAR(50),
    description       VARCHAR(255) NOT NULL,
    studygroup_id     VARCHAR(50),
    bodypart_id       VARCHAR(50),
    modality_id       VARCHAR(50),
    rvu               VARCHAR(50),
    nofviews          VARCHAR(50),
    default_predef_id VARCHAR(50)
);

CREATE TABLE IF NOT EXISTS nextris.isequipment (
    guid          VARCHAR(50) PRIMARY KEY,
    description   VARCHAR(150) NOT NULL,
    aetitle       VARCHAR(64),
    externalcode  VARCHAR(50),
    idmodality    VARCHAR(50),
    isactive      INTEGER DEFAULT 1,
    location_id   VARCHAR(50)
);

CREATE TABLE IF NOT EXISTS nextris.isseverity (
    guid        VARCHAR(50) PRIMARY KEY,
    description VARCHAR(100) NOT NULL
);

CREATE TABLE IF NOT EXISTS nextris.islaterality (
    guid        VARCHAR(50) PRIMARY KEY,
    description VARCHAR(100) NOT NULL
);

CREATE TABLE IF NOT EXISTS nextris.isrequestingphysician (
    guid        VARCHAR(50) PRIMARY KEY,
    description VARCHAR(255) NOT NULL,
    phone       VARCHAR(50),
    mail        VARCHAR(150),
    note        VARCHAR(255),
    location_id VARCHAR(50)
);

CREATE TABLE IF NOT EXISTS nextris.ispricelist (
    guid        VARCHAR(50) PRIMARY KEY,
    description VARCHAR(255) NOT NULL
);

CREATE TABLE IF NOT EXISTS nextris.ishealthinsurances (
    guid              VARCHAR(50) PRIMARY KEY,
    description       VARCHAR(255) NOT NULL,
    isactive          INTEGER DEFAULT 1,
    externalcode      VARCHAR(50),
    headerdescription VARCHAR(255)
);

CREATE TABLE IF NOT EXISTS nextris.isbasicinformation (
    guid        VARCHAR(50) PRIMARY KEY,
    name        VARCHAR(150),
    mail        VARCHAR(150),
    address     VARCHAR(255),
    phone       VARCHAR(50),
    logo_path   VARCHAR(500)
);

CREATE TABLE IF NOT EXISTS nextris.ismodule (
    guid        VARCHAR(50) PRIMARY KEY,
    code        VARCHAR(50) NOT NULL UNIQUE,
    name        VARCHAR(120) NOT NULL,
    description TEXT,
    is_active   BOOLEAN NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS nextris.ispermission (
    guid        VARCHAR(50) PRIMARY KEY,
    code        VARCHAR(100) NOT NULL UNIQUE,
    module      VARCHAR(50) NOT NULL,
    action      VARCHAR(50) NOT NULL,
    description VARCHAR(255) NOT NULL,
    is_active   BOOLEAN DEFAULT TRUE,
    created_on  TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()
);

-- =============================================================================
-- 3. TABLAS DE CONFIGURACIÓN DE APLICACIÓN
-- =============================================================================

CREATE TABLE IF NOT EXISTS nextris.app_config (
    id                              INTEGER DEFAULT 1 NOT NULL PRIMARY KEY,
    name                            VARCHAR(255) NOT NULL DEFAULT 'NextRIS',
    code                            VARCHAR(50),
    email                           VARCHAR(150),
    contact_person                  VARCHAR(150),
    description                     TEXT,
    address                         VARCHAR(255),
    city                            VARCHAR(100),
    country                         VARCHAR(100),
    phone                           VARCHAR(50),
    smtp_server                     VARCHAR(255),
    smtp_port                       INTEGER,
    smtp_user                       VARCHAR(150),
    smtp_password                   VARCHAR(255),
    smtp_from                       VARCHAR(150),
    smtp_from_name                  VARCHAR(150),
    use_tls                         BOOLEAN DEFAULT TRUE,
    whatsapp_api_url                VARCHAR(500),
    whatsapp_api_token              VARCHAR(500),
    whatsapp_phone_number_id        VARCHAR(100),
    whatsapp_business_account_id    VARCHAR(100),
    whatsapp_webhook_verify_token   VARCHAR(255),
    whatsapp_is_active              BOOLEAN DEFAULT FALSE,
    plan_id                         VARCHAR(50),
    created_at                      TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
    updated_at                      TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
    CONSTRAINT single_row CHECK (id = 1)
);

CREATE TABLE IF NOT EXISTS nextris.app_modules (
    module_id   VARCHAR(50) NOT NULL PRIMARY KEY,
    is_active   BOOLEAN NOT NULL DEFAULT TRUE,
    updated_at  TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()
);

-- =============================================================================
-- 4. TABLAS PRINCIPALES
-- =============================================================================

CREATE TABLE IF NOT EXISTS nextris.tblocation (
    guid                                VARCHAR(50) PRIMARY KEY,
    name                                VARCHAR(255) NOT NULL,
    code                                VARCHAR(50),
    address                             VARCHAR(255),
    phone                               VARCHAR(50),
    status                              VARCHAR(20) DEFAULT 'Active',
    created_at                          TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
    updated_at                          TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
    mail                                VARCHAR(150),
    logo_path                           VARCHAR(500),
    geographic_location                 VARCHAR(255),
    timezone                            VARCHAR(100),
    gateway_aet                         VARCHAR(64),
    gateway_ip                          VARCHAR(45),
    transmission_type                   VARCHAR(16) DEFAULT 'Manual'
        CONSTRAINT tblocation_transmission_type_check CHECK (transmission_type IN ('Manual', 'Automatic')),
    retention_days                      INTEGER,
    require_execution_before_reporting  BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS nextris.tbuser (
    guid            VARCHAR PRIMARY KEY,
    username        VARCHAR(64) UNIQUE,
    mail            VARCHAR(64),
    password        VARCHAR(255),
    name            VARCHAR(100),
    surname         VARCHAR(100),
    nationalnumber  VARCHAR(20),
    idrole          VARCHAR,
    isactive        SMALLINT,
    first_login     SMALLINT
);

CREATE TABLE IF NOT EXISTS nextris.tbuser_medical_data (
    id                  SERIAL PRIMARY KEY,
    user_id             VARCHAR(50) NOT NULL UNIQUE,
    aclaracion_firma    VARCHAR(255) NOT NULL,
    matricula_nacional  VARCHAR(100) NOT NULL,
    firma_digital       VARCHAR(500),
    firma_habilitada    BOOLEAN DEFAULT FALSE,
    fecha_creacion      TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
    fecha_actualizacion TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
    FOREIGN KEY (user_id) REFERENCES nextris.tbuser(guid) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS nextris.datapatient (
    guid          VARCHAR(50) PRIMARY KEY,
    patientid     VARCHAR(50) NOT NULL,
    name          VARCHAR(100),
    surname       VARCHAR(100),
    nationalcode  VARCHAR(50),
    sexcode       VARCHAR(10),
    birthdate     DATE,
    email         VARCHAR(150),
    phone         VARCHAR(50),
    healthcard    VARCHAR(100),
    trial190      VARCHAR(50),
    isanonymous   BIT(1) DEFAULT '0',
    ismerged      BIT(1) DEFAULT '0'
);

CREATE TABLE IF NOT EXISTS nextris.tbuser_patient (
    guid            VARCHAR(50) PRIMARY KEY,
    username        VARCHAR(150) NOT NULL,
    password        VARCHAR(255) NOT NULL,
    datapatient_id  VARCHAR(50) NOT NULL,
    status          VARCHAR(20) DEFAULT 'Active',
    firstlogin      INTEGER DEFAULT 1,
    lastlogin       TIMESTAMP WITHOUT TIME ZONE,
    CONSTRAINT fk_tbuser_patient_datapatient FOREIGN KEY (datapatient_id) REFERENCES nextris.datapatient(guid) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS nextris.tbexamination (
    guid                    VARCHAR(50) PRIMARY KEY,
    studyinstanceuid        VARCHAR(255),
    idpatient               VARCHAR(50),
    studytype_id            VARCHAR(50),
    idequipment             VARCHAR(50),
    admisionnumber          VARCHAR(50),
    localacc                VARCHAR(50),
    createdon               TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
    status                  VARCHAR(50) DEFAULT 'Scheduled',
    isexecuted              INTEGER DEFAULT 0,
    isreported              INTEGER DEFAULT 0,
    isimage                 INTEGER DEFAULT 0,
    ispublicated            INTEGER DEFAULT 0,
    isadmitted              INTEGER DEFAULT 0,
    idrequestingphysician   VARCHAR(50),
    idreferringphysician    VARCHAR(50),
    idseverity              VARCHAR(50),
    idpricelist             VARCHAR(50),
    location_id             VARCHAR(50),
    assignto                VARCHAR(50),
    blockby                 VARCHAR(50),
    reportdate              TIMESTAMP WITHOUT TIME ZONE,
    executedon              TIMESTAMP WITHOUT TIME ZONE,
    history                 TEXT,
    clinicalquestion        TEXT,
    othersdetails           TEXT,
    numberofviews           VARCHAR(50),
    stat                    VARCHAR(50),
    laterality_id           VARCHAR(50),
    tag_ids                 VARCHAR(50)[],
    CONSTRAINT fk_tbexamination_patient FOREIGN KEY (idpatient) REFERENCES nextris.datapatient(guid) ON DELETE SET NULL,
    CONSTRAINT fk_tbexamination_studytype FOREIGN KEY (studytype_id) REFERENCES nextris.isstudytype(guid) ON DELETE SET NULL,
    CONSTRAINT fk_tbexamination_equipment FOREIGN KEY (idequipment) REFERENCES nextris.isequipment(guid) ON DELETE SET NULL,
    CONSTRAINT fk_tbexamination_severity FOREIGN KEY (idseverity) REFERENCES nextris.isseverity(guid) ON DELETE SET NULL,
    CONSTRAINT fk_tbexamination_location FOREIGN KEY (location_id) REFERENCES nextris.tblocation(guid) ON DELETE SET NULL,
    CONSTRAINT fk_tbexamination_laterality FOREIGN KEY (laterality_id) REFERENCES nextris.islaterality(guid) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS nextris.tbreport (
    guid          VARCHAR(50) PRIMARY KEY,
    idexamination VARCHAR(50) NOT NULL,
    idpatient     VARCHAR(50),
    admnumber     VARCHAR(50),
    iduser        VARCHAR(50),
    findings      TEXT,
    impressions   TEXT,
    techniques    TEXT,
    conclusions   TEXT,
    wassaved      BOOLEAN DEFAULT FALSE,
    createdon     TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
    date          TIMESTAMP WITHOUT TIME ZONE,
    CONSTRAINT fk_tbreport_examination FOREIGN KEY (idexamination) REFERENCES nextris.tbexamination(guid) ON DELETE CASCADE,
    CONSTRAINT fk_tbreport_patient FOREIGN KEY (idpatient) REFERENCES nextris.datapatient(guid) ON DELETE SET NULL,
    CONSTRAINT fk_tbreport_user FOREIGN KEY (iduser) REFERENCES nextris.tbuser(guid) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS nextris.tbagendaevents (
    guid                VARCHAR(50) PRIMARY KEY,
    comienzo            TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    fin                 TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    idpatient           VARCHAR(50),
    idexam              VARCHAR(50),
    idequipment         VARCHAR(50),
    idmed               VARCHAR(50),
    idmed_sol           VARCHAR(50),
    location_id         VARCHAR(50),
    createdon           TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
    isadmitted          BOOLEAN DEFAULT FALSE,
    title               VARCHAR(255),
    medico_solicitante  VARCHAR(150),
    rads                VARCHAR(150),
    obrasocial          VARCHAR(150),
    timezone            VARCHAR(100),
    CONSTRAINT fk_tbagendaevents_patient FOREIGN KEY (idpatient) REFERENCES nextris.datapatient(guid) ON DELETE SET NULL,
    CONSTRAINT fk_tbagendaevents_equipment FOREIGN KEY (idequipment) REFERENCES nextris.isequipment(guid) ON DELETE SET NULL,
    CONSTRAINT fk_tbagendaevents_location FOREIGN KEY (location_id) REFERENCES nextris.tblocation(guid) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS nextris.tbinfpredef (
    guid          VARCHAR(50) PRIMARY KEY,
    tittle        VARCHAR(255),
    findings      TEXT,
    impression    TEXT,
    technique     TEXT,
    conclusion    TEXT,
    studytype_id  VARCHAR(50),
    report_type   VARCHAR(20) DEFAULT 'simple',
    owner_id      VARCHAR(45) NOT NULL DEFAULT 'nextris',
    CONSTRAINT fk_tbinfpredef_studytype FOREIGN KEY (studytype_id) REFERENCES nextris.isstudytype(guid) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS nextris.tbmanual_uploads (
    guid                    VARCHAR(50) PRIMARY KEY,
    filename                VARCHAR(255),
    filepath                VARCHAR(500),
    file_size               BIGINT,
    patient_name            VARCHAR(255),
    patient_id              VARCHAR(50),
    study_date              VARCHAR(20),
    study_time              VARCHAR(20),
    study_description       VARCHAR(255),
    modality                VARCHAR(20),
    study_instance_uid      VARCHAR(255),
    series_instance_uid     VARCHAR(255),
    sop_instance_uid        VARCHAR(255),
    accession_number        VARCHAR(100),
    uploaded_by_user_guid   VARCHAR(50),
    uploaded_by_username    VARCHAR(150),
    pacs_status             VARCHAR(20),
    pacs_message            TEXT,
    pacs_sent_date          TIMESTAMP WITHOUT TIME ZONE,
    location_id             VARCHAR(50),
    islinked                INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS nextris.tbtags (
    guid        VARCHAR(50) PRIMARY KEY,
    description VARCHAR(100) NOT NULL,
    is_active   BOOLEAN DEFAULT TRUE,
    created_at  TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
    updated_at  TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS nextris.tb_filter_preset (
    guid        VARCHAR(50) PRIMARY KEY,
    user_id     VARCHAR(50) NOT NULL,
    name        VARCHAR(150) NOT NULL,
    filters     JSONB NOT NULL,
    sort_order  INTEGER DEFAULT 0,
    is_active   BOOLEAN DEFAULT FALSE,
    created_on  TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
    updated_on  TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()
);

-- =============================================================================
-- 5. TABLAS DE RELACIÓN (rel_*)
-- =============================================================================

CREATE TABLE IF NOT EXISTS nextris.rel_user_location (
    user_id      VARCHAR(50) NOT NULL,
    location_id  VARCHAR(50) NOT NULL,
    is_default   BOOLEAN DEFAULT FALSE,
    PRIMARY KEY (user_id, location_id),
    CONSTRAINT fk_rel_user_location_user FOREIGN KEY (user_id) REFERENCES nextris.tbuser(guid) ON DELETE CASCADE,
    CONSTRAINT fk_rel_user_location_location FOREIGN KEY (location_id) REFERENCES nextris.tblocation(guid) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS nextris.rel_user_permission (
    guid            VARCHAR(50) PRIMARY KEY,
    user_id         VARCHAR(50) NOT NULL,
    permission_id   VARCHAR(50) NOT NULL,
    is_granted      BOOLEAN DEFAULT TRUE,
    created_on      TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
    updated_on      TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
    CONSTRAINT uq_user_permission UNIQUE (user_id, permission_id),
    CONSTRAINT fk_rel_user_perm_user FOREIGN KEY (user_id) REFERENCES nextris.tbuser(guid) ON DELETE CASCADE,
    CONSTRAINT fk_rel_user_perm_perm FOREIGN KEY (permission_id) REFERENCES nextris.ispermission(guid) ON DELETE CASCADE
);


CREATE TABLE IF NOT EXISTS nextris.rel_infpredef_location (
    guid        VARCHAR(45) PRIMARY KEY,
    template_id VARCHAR(45) NOT NULL,
    location_id VARCHAR(45) NOT NULL,
    created_on  TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_rel_infpredef_location UNIQUE (template_id, location_id)
);

CREATE TABLE IF NOT EXISTS nextris.tbinfpredef_user_default (
    user_id        VARCHAR(45) NOT NULL,
    template_id    VARCHAR(45) NOT NULL,
    study_type_id  VARCHAR(45) NOT NULL,
    created_on     TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, study_type_id)
);

CREATE TABLE IF NOT EXISTS nextris.rel_insurance_location (
    guid          VARCHAR(50) PRIMARY KEY,
    insurance_id  VARCHAR(50) NOT NULL,
    location_id   VARCHAR(50) NOT NULL,
    is_default    BOOLEAN DEFAULT FALSE,
    CONSTRAINT fk_rel_ins_loc_insurance FOREIGN KEY (insurance_id) REFERENCES nextris.ishealthinsurances(guid) ON DELETE CASCADE,
    CONSTRAINT fk_rel_ins_loc_location FOREIGN KEY (location_id) REFERENCES nextris.tblocation(guid) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS nextris.rel_medico_studygroup (
    guid          VARCHAR(50) PRIMARY KEY,
    med_id        VARCHAR(50) NOT NULL,
    studygroup_id VARCHAR(50) NOT NULL,
    CONSTRAINT fk_rel_med_sg_med FOREIGN KEY (med_id) REFERENCES nextris.tbuser(guid) ON DELETE CASCADE,
    CONSTRAINT fk_rel_med_sg_group FOREIGN KEY (studygroup_id) REFERENCES nextris.isstudytypegroup(guid) ON DELETE CASCADE
);

-- =============================================================================
-- 6. TABLAS DE AGENDAS
-- =============================================================================

CREATE TABLE IF NOT EXISTS nextris.isagendameditem (
    guid        VARCHAR(50) PRIMARY KEY,
    idmed       VARCHAR(50) NOT NULL,
    day         VARCHAR(20),
    timefrom    TIME WITHOUT TIME ZONE,
    timeto      TIME WITHOUT TIME ZONE,
    initday     DATE,
    finishday   DATE,
    location_id VARCHAR(50),
    CONSTRAINT fk_agendamed_location FOREIGN KEY (location_id) REFERENCES nextris.tblocation(guid) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS nextris.isagendaequip (
    guid        VARCHAR(50) PRIMARY KEY,
    idequipment VARCHAR(50) NOT NULL,
    day         INTEGER,
    timefrom    TIME WITHOUT TIME ZONE,
    timeto      TIME WITHOUT TIME ZONE,
    CONSTRAINT fk_agendaequip_equipment FOREIGN KEY (idequipment) REFERENCES nextris.isequipment(guid) ON DELETE CASCADE
);

-- =============================================================================
-- 7. TABLAS DE INTEGRACIÓN PACS
-- =============================================================================

CREATE TABLE IF NOT EXISTS nextris.tbpacs_study_link (
    id                    BIGSERIAL PRIMARY KEY,
    pacs_study_pk         BIGINT NOT NULL,
    pacs_study_iuid       VARCHAR(255) NOT NULL,
    order_guid            VARCHAR(100) NOT NULL,
    order_study_uuid      VARCHAR(255),
    manual_upload_guid    VARCHAR(100),
    link_status           VARCHAR(20) NOT NULL DEFAULT 'linked',
    source                VARCHAR(30) NOT NULL DEFAULT 'manual',
    linked_at             TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    unlinked_at           TIMESTAMP WITHOUT TIME ZONE,
    linked_by_user_guid   VARCHAR(100),
    linked_by_username    VARCHAR(255),
    unlinked_reason       TEXT,
    created_at            TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at            TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_tbpacs_study_link_status CHECK (link_status IN ('linked', 'unlinked')),
    CONSTRAINT chk_tbpacs_study_link_source CHECK (source IN ('manual', 'reconcile', 'auto')),
    CONSTRAINT fk_tbpacs_study_link_order FOREIGN KEY (order_guid) REFERENCES nextris.tbexamination(guid) ON DELETE RESTRICT,
    CONSTRAINT fk_tbpacs_study_link_manual_upload FOREIGN KEY (manual_upload_guid) REFERENCES nextris.tbmanual_uploads(guid) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS nextris.tbpacs_location_assignment (
    pacs_study_pk   BIGINT PRIMARY KEY,
    pacs_study_iuid VARCHAR(255) NOT NULL,
    location_id     VARCHAR(100) NOT NULL,
    sending_aet     VARCHAR(64) NOT NULL,
    matched_at      TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_pla_location FOREIGN KEY (location_id) REFERENCES nextris.tblocation(guid) ON DELETE CASCADE
);

-- =============================================================================
-- 8. TABLAS DE COMPARTIR / VIEWER
-- =============================================================================

CREATE TABLE IF NOT EXISTS nextris.tbviewer_share_link (
    guid                VARCHAR(100) PRIMARY KEY,
    token_hash          VARCHAR(128) NOT NULL UNIQUE,
    study_iuid          VARCHAR(255) NOT NULL,
    location_id         VARCHAR(100) NOT NULL,
    created_by_user_id  VARCHAR(100) NOT NULL,
    created_at          TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    expires_at          TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    revoked             BOOLEAN NOT NULL DEFAULT FALSE,
    revoked_at          TIMESTAMP WITHOUT TIME ZONE,
    reason              TEXT,
    patient_email       VARCHAR(255),
    open_count          INTEGER NOT NULL DEFAULT 0,
    last_opened_at      TIMESTAMP WITHOUT TIME ZONE,
    created_ip          VARCHAR(64),
    last_opened_ip      VARCHAR(64),
    raw_token           VARCHAR(255),
    CONSTRAINT fk_viewer_share_location FOREIGN KEY (location_id) REFERENCES nextris.tblocation(guid) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS nextris.tbviewer_share_link_access (
    id              BIGSERIAL PRIMARY KEY,
    share_guid      VARCHAR(100) NOT NULL,
    opened_at       TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    success         BOOLEAN NOT NULL,
    failure_reason  VARCHAR(255),
    ip_address      VARCHAR(64),
    user_agent      TEXT,
    reason          TEXT,
    CONSTRAINT fk_viewer_share_access_share FOREIGN KEY (share_guid) REFERENCES nextris.tbviewer_share_link(guid) ON DELETE CASCADE
);

-- =============================================================================
-- 9. TABLAS DE ANALYTICS Y LOGS
-- =============================================================================

CREATE TABLE IF NOT EXISTS nextris.tb_analytics_events (
    id            BIGSERIAL PRIMARY KEY,
    event_id      UUID NOT NULL DEFAULT gen_random_uuid(),
    user_id       VARCHAR(100),
    session_id    VARCHAR(100),
    event_type    VARCHAR(50) NOT NULL DEFAULT 'api_request',
    route         VARCHAR(500),
    http_method   VARCHAR(10),
    http_status   SMALLINT,
    duration_ms   INTEGER,
    ip_address    VARCHAR(45),
    country       VARCHAR(100),
    city          VARCHAR(100),
    user_agent    TEXT,
    extra_data    JSONB,
    created_at    TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS nextris.tbexternal_api_log (
    id                    BIGSERIAL PRIMARY KEY,
    request_id            VARCHAR(50) NOT NULL DEFAULT (gen_random_uuid())::TEXT,
    endpoint              VARCHAR(200) NOT NULL,
    method                VARCHAR(10) NOT NULL,
    payload               JSONB,
    patient_guid          VARCHAR(50),
    patient_nationalcode  VARCHAR(50),
    examination_guid      VARCHAR(50),
    report_guid           VARCHAR(50),
    study_uid             VARCHAR(255),
    pacs_linked           BOOLEAN DEFAULT FALSE,
    pacs_link_error       TEXT,
    status                VARCHAR(20) NOT NULL DEFAULT 'success',
    error_message         TEXT,
    ip_address            VARCHAR(64),
    user_agent            TEXT,
    created_at            TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW()
);

-- =============================================================================
-- 10. DATOS BASE (Seed Data)
-- =============================================================================

-- Roles
INSERT INTO nextris.isrole (guid, description) VALUES
    ('role-sysadmin',       'Sysadmin'),
    ('684cc07b-2494-48ab-9fdd-d0df7ce9c86c', 'Administrador'),
    ('1bebfc4e-5ec0-46da-99db-9628a87e6848', 'Administrativo'),
    ('88e340f5-6fa5-4df1-aef6-c911625a4427', 'Medico'),
    ('58f11869-ea15-46fb-a10e-a65c35954aa0', 'Sysadmin'),
    ('b982545d-ec35-4db9-ab87-6bdbe09670e8', 'Tecnico')
ON CONFLICT (guid) DO NOTHING;

-- Modalidades DICOM
INSERT INTO nextris.ismodality (guid, externalcode, description) VALUES
    ('78696a8c-35ac-11ef-b0f7-00ffb9d5e4de', 'RX',  'RAYOS X'),
    ('793b4409-5f67-4973-97e9-edfbb49a79d6', 'CR',  'RADIOGRAFIA COMPUTADA'),
    ('e0250b6c-3419-11ef-bdff-00ffb9d5e4de', 'CT',  'TOMOGRAFIA'),
    ('6211f329-35ac-11ef-b0f7-00ffb9d5e4de', 'RMN', 'RESONANCIA'),
    ('181df076-340b-11ef-bdff-00ffb9d5e4de', 'US',  'ECOGRAFIA'),
    ('e0010ba8-df9d-435d-98e7-4ef5103b0aec', 'MG',  'MAMOGRAFIA'),
    ('1ecef35e-8737-453d-b4b9-938e1d9f03e7', 'XA',  'ANGIOGRAFIA'),
    ('dae91d46-a429-429e-92d4-1041e41de14e', 'ES',  'ENDOSCOPIA')
ON CONFLICT (guid) DO NOTHING;

-- Partes anatómicas
INSERT INTO nextris.isanatomicalpart (guid, description) VALUES
    ('27736491-9738-4a03-9c1f-1df6bdd4cc34', 'Cabeza'),
    ('4357d347-ba25-41ed-843f-a14f36c19952', 'Cráneo'),
    ('034e6922-f25d-4fb2-8bf6-35a9dbbee3d4', 'Cráneo / Senos'),
    ('f8e56776-a235-4cee-8de7-00e49bfa22ce', 'Cerebro'),
    ('e6e05a14-4abc-4c87-84b9-72a0a6c707a3', 'Maxilofacial'),
    ('be60a4e1-c768-4b3c-9625-e027495bc707', 'Cuello'),
    ('107114ac-171c-4a65-ad87-939e2567a110', 'Tórax'),
    ('8d0afbbe-38d7-11ef-b0f7-00ffb9d5e4de', 'Abdomen'),
    ('d5462e49-ef6d-45e6-aaff-95553a1ed42d', 'Pelvis'),
    ('b5287833-a669-4678-947f-2867b343c71d', 'Mama'),
    ('42edd51a-8674-44a8-8179-e25d1a4ba802', 'Sistema vascular'),
    ('001789ea-687a-45ef-8ac1-6f8b9414fd63', 'Columna vertebral'),
    ('8d0aea40-38d7-11ef-b0f7-00ffb9d5e4de', 'Extremidad superior'),
    ('8d0af2c7-38d7-11ef-b0f7-00ffb9d5e4de', 'Extremidad inferior')
ON CONFLICT (guid) DO NOTHING;

-- Módulos del sistema
INSERT INTO nextris.ismodule (guid, code, name, description) VALUES
    ('be340753-a753-416d-a998-a7ff9f737921', 'appointments',       'Citas',                   NULL),
    ('c69c50e8-c75c-4b5c-9221-746a7541d295', 'nexi',               'Nexi',                    NULL),
    ('f32e0af3-64b3-4d94-84ee-1b825a6f0a73', 'patient_portal',     'Portal de pacientes',     NULL),
    ('b6b0f62d-3b27-4fa4-b70e-491a5572e0d3', 'structured_reports', 'Reportes estructurados',  NULL)
ON CONFLICT (guid) DO NOTHING;

-- Planes
INSERT INTO nextris.isplan (guid, code, name, description) VALUES
    ('d825e306-e5e7-4634-8b9a-cb7598349026', 'free',       'Free',       NULL),
    ('f2aa9d98-2f99-4af3-8370-45be1d6f1f36', 'standard',   'Standard',   NULL),
    ('088b6098-2d80-41f2-8e60-af80f58d05c8', 'pro',        'Pro',        NULL),
    ('2a4d996c-bdd0-4c2a-92b8-48506d134953', 'enterprise', 'Enterprise', NULL)
ON CONFLICT (guid) DO NOTHING;

-- Permisos
INSERT INTO nextris.ispermission (guid, code, module, action, description) VALUES
    -- Admissions
    ('aa55e200-30f5-465e-91c9-26a812d77bf3', 'tabs.admissions.view',          'admissions', 'view',              'Ver pestaña Admisión'),
    ('29d44a85-a226-40f2-9977-7aef2f6812de', 'admissions.view',               'admissions', 'view',              'Ver admisiones'),
    ('d789936a-ec8c-445a-b89e-4b13252d4152', 'admissions.admit_appointments', 'admissions', 'admit_appointments','Admisionar citas'),
    ('3abde008-7040-4069-8016-824884238e81', 'admissions.create_spontaneous', 'admissions', 'create_spontaneous','Generar admisión espontánea'),
    -- Appointments
    ('5dea02cf-0e5c-44b1-a15f-52648e8aa2d3', 'tabs.appointments.view',        'appointments','view',             'Ver pestaña Citas'),
    ('ca240c1f-010e-447d-b533-c27fda2646ac', 'appointments.view',             'appointments','view',             'Ver citas'),
    ('6553a598-f1d1-40e6-b071-a477a9649453', 'appointments.create',           'appointments','create',           'Generar citas'),
    -- Config
    ('d4ab7c42-a814-4faf-b604-96741c74e506', 'tabs.config.view',              'config',     'view',              'Ver pestaña Configuración'),
    -- Distribution
    ('e3865cc4-00b9-4fd7-b989-abaed883f37c', 'tabs.distribution.view',        'distribution','view',             'Ver pestaña Distribución'),
    ('6a81cf24-0cc8-4caa-8cd2-e9b133074ae1', 'distribution.view',             'distribution','view',             'Ver pestaña Distribución'),
    ('75f884e2-eda9-4ffa-9280-5e212c8377a7', 'distribution.perform',          'distribution','perform',          'Hacer la distribución'),
    ('5eb6ca28-8d49-437e-bff8-39e6cb655c46', 'distribution.send_report',      'distribution','send_report',      'Enviar informe por email'),
    ('02a79628-8312-4ea6-b022-d9944de84ae7', 'distribution.send_report_whatsapp','distribution','send_report_whatsapp','Enviar informe por WhatsApp'),
    ('bc7b413f-3994-4477-8b1f-a3b12a3e6e54', 'distribution.update_email',     'distribution','update_email',     'Actualizar email para distribución'),
    -- Execution
    ('48b0012f-7e2d-42b9-b2d8-d52cfcbdac39', 'tabs.execution.view',           'execution',  'view',              'Ver pestaña Ejecución'),
    ('db18150a-4228-40e8-9865-e67f9d965af6', 'execution.view_pending',        'execution',  'view_pending',      'Ver ejecuciones pendientes'),
    ('934ba4c0-e738-4778-a9d9-0a80c2a62de9', 'execution.execute',             'execution',  'execute',           'Ejecutar'),
    -- Gestión
    ('6ee87ed5-17e9-4f1b-938e-a4ae9729bb07', 'tabs.gestion.view',             'gestion',    'view',              'Ver pestaña Gestión'),
    -- Images
    ('08398ecb-6cb3-4e27-9a0a-844f8a39398b', 'tabs.images.view',              'images',     'view',              'Ver pestaña Imágenes'),
    ('fe5a7926-afd0-4022-b704-88309724588a', 'images.view',                   'images',     'view',              'Ver imágenes DICOM'),
    ('61e199ea-89c2-4078-a9c2-a4948f17a42e', 'images.share_link',             'images',     'share_link',        'Generar enlace compartido de imágenes'),
    -- Nexi
    ('fafb190c-4310-48e3-9e81-b2b39fff3c3e', 'tabs.nexi.view',                'nexi',       'view',              'Ver pestaña Nexi'),
    -- Patients
    ('6bbc9d55-0ff9-44f5-b68c-d1d6898d0c48', 'tabs.patients.view',            'patients',   'view',              'Ver pestaña Pacientes'),
    ('095bde67-b010-4c81-8810-a18e626352e6', 'patients.view',                 'patients',   'view',              'Ver pacientes'),
    ('b18dfe0c-0bfb-44bf-9086-9d7bfcdac023', 'patients.manage',               'patients',   'manage',            'Generar nuevos pacientes / editar pacientes'),
    -- Preferences
    ('ee3d6580-f229-4346-8ccf-6a18f5457c8d', 'tabs.preferences.view',         'preferences','view',              'Ver pestaña Preferencias'),
    -- Reports
    ('5b4c2976-1807-4bfd-9720-c5faba88f488', 'tabs.reports.view',             'reports',    'view',              'Ver pestaña Redacción/Informes'),
    ('7a236659-0b6f-4991-bd01-be9cfc6ef47d', 'reports.view_reports',          'reports',    'view_reports',      'Ver reportes'),
    ('7335012c-fc59-442c-9463-04bc0764d9e7', 'reports.view_writing',          'reports',    'view_writing',      'Ver redacción'),
    ('74044e9b-cbda-4db2-bac4-9551ed1690f8', 'reports.sign',                  'reports',    'sign',              'Firmar informe'),
    ('8faa2e67-2d95-4545-bb30-fdda9e8cab0f', 'reports.unsign',                'reports',    'unsign',            'Desfirmar informe'),
    -- Structured Reports
    ('21e2711b-9a5b-4c21-92fb-cb52c1a38d73', 'tabs.structured_reports.view',  'structured_reports','view',        'Ver pestaña Reportes estructurados'),
    -- Users
    ('1e7a0bb3-5e14-46fd-9b31-ca8a39f1cdb1', 'users.manage',                  'users',      'manage',            'Gestionar usuarios'),
    ('bc469f04-8a5f-4b38-8d7d-21d824024bce', 'users.permissions.manage',      'users',      'manage_permissions','Gestionar permisos de usuarios')
ON CONFLICT (guid) DO NOTHING;

-- =============================================================================
-- 11. ÍNDICES
-- =============================================================================

-- Analytics
CREATE INDEX IF NOT EXISTS idx_analytics_created_at ON nextris.tb_analytics_events (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_analytics_user_id ON nextris.tb_analytics_events (user_id) WHERE user_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_analytics_session_id ON nextris.tb_analytics_events (session_id) WHERE session_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_analytics_event_type ON nextris.tb_analytics_events (event_type);
CREATE INDEX IF NOT EXISTS idx_analytics_ip ON nextris.tb_analytics_events (ip_address) WHERE ip_address IS NOT NULL;

-- App config
CREATE INDEX IF NOT EXISTS idx_app_config_plan ON nextris.app_config (plan_id);

-- Examinations
CREATE INDEX IF NOT EXISTS idx_tbexamination_patient ON nextris.tbexamination (idpatient);
CREATE INDEX IF NOT EXISTS idx_tbexamination_location ON nextris.tbexamination (location_id);
CREATE INDEX IF NOT EXISTS idx_tbexamination_status ON nextris.tbexamination (status);
CREATE INDEX IF NOT EXISTS idx_tbexamination_createdon ON nextris.tbexamination (createdon DESC);
CREATE INDEX IF NOT EXISTS idx_tbexamination_admisionnumber ON nextris.tbexamination (admisionnumber);

-- Reports
CREATE INDEX IF NOT EXISTS idx_tbreport_examination ON nextris.tbreport (idexamination);
CREATE INDEX IF NOT EXISTS idx_tbreport_patient ON nextris.tbreport (idpatient);

-- Patients
CREATE INDEX IF NOT EXISTS idx_datapatient_patientid ON nextris.datapatient (patientid);
CREATE INDEX IF NOT EXISTS idx_datapatient_name ON nextris.datapatient (surname, name);

-- User permissions
CREATE INDEX IF NOT EXISTS idx_rel_user_permission_user ON nextris.rel_user_permission (user_id);

-- Template predefined
CREATE INDEX IF NOT EXISTS idx_tbinfpredef_owner_id ON nextris.tbinfpredef (owner_id);
CREATE INDEX IF NOT EXISTS idx_tbinfpredef_studytype ON nextris.tbinfpredef (studytype_id);

-- PACS study link
CREATE INDEX IF NOT EXISTS idx_tbpacs_study_link_order_guid ON nextris.tbpacs_study_link (order_guid);
CREATE INDEX IF NOT EXISTS idx_tbpacs_study_link_order_study_uuid ON nextris.tbpacs_study_link (order_study_uuid);
CREATE INDEX IF NOT EXISTS idx_tbpacs_study_link_pacs_study_pk ON nextris.tbpacs_study_link (pacs_study_pk);
CREATE INDEX IF NOT EXISTS idx_tbpacs_study_link_pacs_study_iuid ON nextris.tbpacs_study_link (pacs_study_iuid);
CREATE UNIQUE INDEX IF NOT EXISTS ux_tbpacs_study_link_order_active ON nextris.tbpacs_study_link (order_guid) WHERE link_status = 'linked';
CREATE UNIQUE INDEX IF NOT EXISTS ux_tbpacs_study_link_study_pk_active ON nextris.tbpacs_study_link (pacs_study_pk) WHERE link_status = 'linked';
CREATE UNIQUE INDEX IF NOT EXISTS ux_tbpacs_study_link_study_iuid_active ON nextris.tbpacs_study_link (pacs_study_iuid) WHERE link_status = 'linked';

-- PACS location assignment
CREATE INDEX IF NOT EXISTS idx_pla_location_id ON nextris.tbpacs_location_assignment (location_id);
CREATE INDEX IF NOT EXISTS idx_pla_sending_aet ON nextris.tbpacs_location_assignment (sending_aet);

-- Viewer share links
CREATE INDEX IF NOT EXISTS idx_tbviewer_share_link_study_iuid ON nextris.tbviewer_share_link (study_iuid);
CREATE INDEX IF NOT EXISTS idx_tbviewer_share_link_expires_at ON nextris.tbviewer_share_link (expires_at);
CREATE INDEX IF NOT EXISTS idx_tbviewer_share_link_created_by ON nextris.tbviewer_share_link (created_by_user_id);
CREATE INDEX IF NOT EXISTS idx_tbviewer_share_access_share_guid ON nextris.tbviewer_share_link_access (share_guid);
CREATE INDEX IF NOT EXISTS idx_tbviewer_share_access_opened_at ON nextris.tbviewer_share_link_access (opened_at);

-- External API log
CREATE INDEX IF NOT EXISTS idx_external_log_created ON nextris.tbexternal_api_log (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_external_log_nationalcode ON nextris.tbexternal_api_log (patient_nationalcode);
CREATE INDEX IF NOT EXISTS idx_external_log_request_id ON nextris.tbexternal_api_log (request_id);
CREATE INDEX IF NOT EXISTS idx_external_log_status ON nextris.tbexternal_api_log (status);

-- Filter presets
CREATE INDEX IF NOT EXISTS idx_filter_preset_user ON nextris.tb_filter_preset (user_id);

-- =============================================================================
-- 12. TRIGGER: Asignación automática de ubicación por AET
-- =============================================================================

-- PACS trigger installation is optional; see GENERAL_EDITION.md.

COMMIT;

-- =============================================================================
-- FIN DEL SCHEMA
-- Total: 44 tablas, 50+ índices, 2 funciones, 1 trigger, datos base (roles, modalidades, permisos, etc.)
-- =============================================================================
