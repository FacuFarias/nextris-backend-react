-- =============================================================================
-- Migración: Multi-Tenant → Single-Tenant
-- Fecha: 2026-05-09
-- Descripción: Simplifica la arquitectura eliminando multi-tenancy
-- =============================================================================

BEGIN;

-- =============================================================================
-- 1. CREAR TABLA DE CONFIGURACIÓN GLOBAL (reemplaza tbfacility)
-- =============================================================================

CREATE TABLE IF NOT EXISTS nextris.app_config (
    id                      INTEGER PRIMARY KEY DEFAULT 1,
    name                    VARCHAR(255) NOT NULL DEFAULT 'NextRIS',
    code                    VARCHAR(50),
    email                   VARCHAR(150),
    contact_person          VARCHAR(150),
    description             TEXT,
    address                 VARCHAR(255),
    city                    VARCHAR(100),
    country                 VARCHAR(100),
    phone                   VARCHAR(50),
    -- Configuración SMTP
    smtp_server             VARCHAR(255),
    smtp_port               INTEGER,
    smtp_user               VARCHAR(150),
    smtp_password           VARCHAR(255),
    smtp_from               VARCHAR(150),
    smtp_from_name          VARCHAR(150),
    use_tls                 BOOLEAN DEFAULT TRUE,
    -- Configuración WhatsApp
    whatsapp_api_url            VARCHAR(500),
    whatsapp_api_token          VARCHAR(500),
    whatsapp_phone_number_id    VARCHAR(100),
    whatsapp_business_account_id VARCHAR(100),
    whatsapp_webhook_verify_token VARCHAR(255),
    whatsapp_is_active          BOOLEAN DEFAULT FALSE,
    -- Plan global
    plan_id                 VARCHAR(50),
    -- Metadatos
    created_at              TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
    updated_at              TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
    CONSTRAINT single_row CHECK (id = 1)
);

-- Migrar datos de tbfacility a app_config (si existe)
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'nextris' AND table_name = 'tbfacility') THEN
        INSERT INTO nextris.app_config (
            id, name, code, email, contact_person, description, address, city, country, phone,
            smtp_server, smtp_port, smtp_user, smtp_password, smtp_from, smtp_from_name, use_tls,
            whatsapp_api_url, whatsapp_api_token, whatsapp_phone_number_id,
            whatsapp_business_account_id, whatsapp_webhook_verify_token, whatsapp_is_active,
            plan_id
        )
        SELECT
            1, name, code, email, contact_person, description, address, city, country, phone,
            smtp_server, smtp_port, smtp_user, smtp_password, smtp_from, smtp_from_name, use_tls,
            whatsapp_api_url, whatsapp_api_token, whatsapp_phone_number_id,
            whatsapp_business_account_id, whatsapp_webhook_verify_token, whatsapp_is_active,
            plan_id
        FROM nextris.tbfacility
        LIMIT 1
        ON CONFLICT (id) DO NOTHING;
    END IF;
END $$;

-- =============================================================================
-- 2. MODIFICAR TABLA tblocation
-- =============================================================================

-- Eliminar foreign key a tbfacility si existe
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_tblocation_facility') THEN
        ALTER TABLE nextris.tblocation DROP CONSTRAINT fk_tblocation_facility;
    END IF;
END $$;

-- Eliminar columna facility_id
ALTER TABLE nextris.tblocation DROP COLUMN IF EXISTS facility_id;

-- Eliminar columna id_patientdomain
ALTER TABLE nextris.tblocation DROP COLUMN IF EXISTS id_patientdomain;

-- =============================================================================
-- 3. MODIFICAR TABLA datapatient
-- =============================================================================

-- Eliminar columna id_patientdomain
ALTER TABLE nextris.datapatient DROP COLUMN IF EXISTS id_patientdomain;

-- Eliminar índice de dominio si existe
DROP INDEX IF EXISTS nextris.idx_datapatient_domain;

-- =============================================================================
-- 4. MODIFICAR TABLA tbtags (cambiar facility_id por config global)
-- =============================================================================

-- Eliminar foreign key a tbfacility si existe
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_tbtags_facility') THEN
        ALTER TABLE nextris.tbtags DROP CONSTRAINT fk_tbtags_facility;
    END IF;
END $$;

-- Eliminar columna facility_id
ALTER TABLE nextris.tbtags DROP COLUMN IF EXISTS facility_id;

-- Eliminar índice si existe
DROP INDEX IF EXISTS nextris.idx_tbtags_facility;

-- =============================================================================
-- 5. MODIFICAR TABLA tb_analytics_events (cambiar facility_id por config global)
-- =============================================================================

ALTER TABLE nextris.tb_analytics_events DROP COLUMN IF EXISTS facility_id;
DROP INDEX IF EXISTS nextris.idx_analytics_facility;

-- =============================================================================
-- 6. ELIMINAR TABLAS OBSOLETAS
-- =============================================================================

-- Tablas de dominio de pacientes
DROP TABLE IF EXISTS nextris.rel_user_patientdomain CASCADE;
DROP TABLE IF EXISTS nextris.ispatientdomain CASCADE;

-- Tablas de auditoría de facility
DROP TABLE IF EXISTS nextris.audit_facility_module_change CASCADE;
DROP TABLE IF EXISTS nextris.audit_facility_plan_change CASCADE;

-- Tablas de planes por facility
DROP TABLE IF EXISTS nextris.facility_plan_usage_monthly CASCADE;

-- Tablas de módulos por facility
DROP TABLE IF EXISTS nextris.rel_facility_module CASCADE;

-- Tabla de verificación de signup
DROP TABLE IF EXISTS nextris.tbfree_signup_verification CASCADE;

-- Tabla de facility (después de migrar datos)
DROP TABLE IF EXISTS nextris.tbfacility CASCADE;

-- =============================================================================
-- 7. ELIMINAR TABLAS DE CATÁLOGOS OBSOLETOS
-- =============================================================================

-- ismodule (catálogo de módulos) - verificar si se usa en otra parte primero
-- ispatientdomain ya eliminado arriba

-- =============================================================================
-- 8. MODIFICAR RELACIONES DE MÓDULOS (simplificar a global)
-- =============================================================================

-- Crear tabla de módulos globales si ismodule existe
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'nextris' AND table_name = 'ismodule') THEN
        -- Crear tabla de configuración de módulos globales
        CREATE TABLE IF NOT EXISTS nextris.app_modules (
            module_id       VARCHAR(50) PRIMARY KEY,
            is_active       BOOLEAN NOT NULL DEFAULT TRUE,
            updated_at      TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()
        );
        
        -- Migrar datos de rel_facility_module a app_modules (todos habilitados por defecto)
        INSERT INTO nextris.app_modules (module_id, is_active)
        SELECT guid, TRUE FROM nextris.ismodule
        ON CONFLICT (module_id) DO NOTHING;
    END IF;
END $$;

-- =============================================================================
-- 9. ACTUALIZAR ÍNDICES
-- =============================================================================

-- Índices para app_config
CREATE INDEX IF NOT EXISTS idx_app_config_plan ON nextris.app_config(plan_id);

-- =============================================================================
-- 10. INSERTAR CONFIGURACIÓN POR DEFECTO SI NO EXISTE
-- =============================================================================

INSERT INTO nextris.app_config (id, name, code)
VALUES (1, 'NextRIS', 'NRIS')
ON CONFLICT (id) DO NOTHING;

COMMIT;

-- =============================================================================
-- FIN DE MIGRACIÓN
-- =============================================================================
