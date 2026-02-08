-- Migración: Agregar columnas de configuración a tbfacility
-- Fecha: 2026-01-08
-- Descripción: Agrega columnas para configuración SMTP, Backend y WhatsApp a la tabla tbfacility

-- ====================================================================
-- COLUMNAS DE CONFIGURACIÓN SMTP
-- ====================================================================
ALTER TABLE nextris.tbfacility 
ADD COLUMN IF NOT EXISTS smtp_server character varying(255),
ADD COLUMN IF NOT EXISTS smtp_port integer DEFAULT 587,
ADD COLUMN IF NOT EXISTS smtp_user character varying(255),
ADD COLUMN IF NOT EXISTS smtp_password character varying(255),
ADD COLUMN IF NOT EXISTS smtp_from character varying(255),
ADD COLUMN IF NOT EXISTS smtp_from_name character varying(255),
ADD COLUMN IF NOT EXISTS use_tls boolean DEFAULT true;

-- ====================================================================
-- COLUMNAS DE CONFIGURACIÓN BACKEND
-- ====================================================================
ALTER TABLE nextris.tbfacility 
ADD COLUMN IF NOT EXISTS db_user character varying(100),
ADD COLUMN IF NOT EXISTS db_password character varying(255),
ADD COLUMN IF NOT EXISTS db_host character varying(255),
ADD COLUMN IF NOT EXISTS db_port integer DEFAULT 5432,
ADD COLUMN IF NOT EXISTS db_name character varying(100),
ADD COLUMN IF NOT EXISTS base_folder character varying(500),
ADD COLUMN IF NOT EXISTS ipserver character varying(100);

-- ====================================================================
-- COLUMNAS DE CONFIGURACIÓN WHATSAPP API
-- ====================================================================
ALTER TABLE nextris.tbfacility 
ADD COLUMN IF NOT EXISTS whatsapp_api_url character varying(500),
ADD COLUMN IF NOT EXISTS whatsapp_api_token character varying(500),
ADD COLUMN IF NOT EXISTS whatsapp_phone_number_id character varying(100),
ADD COLUMN IF NOT EXISTS whatsapp_business_account_id character varying(100),
ADD COLUMN IF NOT EXISTS whatsapp_webhook_verify_token character varying(255),
ADD COLUMN IF NOT EXISTS whatsapp_is_active boolean DEFAULT false;

-- Comentarios en las columnas
COMMENT ON COLUMN nextris.tbfacility.smtp_server IS 'Servidor SMTP para envío de correos';
COMMENT ON COLUMN nextris.tbfacility.smtp_port IS 'Puerto del servidor SMTP';
COMMENT ON COLUMN nextris.tbfacility.smtp_user IS 'Usuario para autenticación SMTP';
COMMENT ON COLUMN nextris.tbfacility.smtp_password IS 'Contraseña para autenticación SMTP';
COMMENT ON COLUMN nextris.tbfacility.smtp_from IS 'Dirección de correo remitente';
COMMENT ON COLUMN nextris.tbfacility.smtp_from_name IS 'Nombre del remitente';
COMMENT ON COLUMN nextris.tbfacility.use_tls IS 'Indica si se usa TLS/SSL para SMTP';

COMMENT ON COLUMN nextris.tbfacility.db_user IS 'Usuario de base de datos para esta facility';
COMMENT ON COLUMN nextris.tbfacility.db_password IS 'Contraseña de base de datos';
COMMENT ON COLUMN nextris.tbfacility.db_host IS 'Host del servidor de base de datos';
COMMENT ON COLUMN nextris.tbfacility.db_port IS 'Puerto de conexión a la base de datos';
COMMENT ON COLUMN nextris.tbfacility.db_name IS 'Nombre de la base de datos';
COMMENT ON COLUMN nextris.tbfacility.base_folder IS 'Carpeta base para almacenamiento de archivos';
COMMENT ON COLUMN nextris.tbfacility.ipserver IS 'Dirección IP del servidor backend';

COMMENT ON COLUMN nextris.tbfacility.whatsapp_api_url IS 'URL de la API de WhatsApp Business';
COMMENT ON COLUMN nextris.tbfacility.whatsapp_api_token IS 'Token de autenticación para API de WhatsApp';
COMMENT ON COLUMN nextris.tbfacility.whatsapp_phone_number_id IS 'ID del número de teléfono de WhatsApp Business';
COMMENT ON COLUMN nextris.tbfacility.whatsapp_business_account_id IS 'ID de la cuenta de negocio de WhatsApp';
COMMENT ON COLUMN nextris.tbfacility.whatsapp_webhook_verify_token IS 'Token de verificación para webhook de WhatsApp';
COMMENT ON COLUMN nextris.tbfacility.whatsapp_is_active IS 'Indica si la integración de WhatsApp está activa';

-- Mensaje de confirmación
SELECT 'Columnas de configuración agregadas exitosamente a nextris.tbfacility' AS resultado;
