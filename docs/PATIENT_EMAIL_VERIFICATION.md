# Validación de email del paciente

La validación está deshabilitada por defecto (`PATIENT_EMAIL_VERIFICATION_ENABLED=false`). El paciente puede guardar un email válido y luego cambiar su contraseña; no se muestran controles de verificación ni se permite enviar o confirmar códigos por API. No se marca el email como validado por guardarlo.

Para habilitarla más adelante, configurar Resend y establecer `PATIENT_EMAIL_VERIFICATION_ENABLED=true` en el backend, reiniciar el backend y refrescar Mis Datos. La pantalla usa la configuración del servidor.

Con validación habilitada: en Mis Datos, editar y guardar el email, pulsar **Validar email**, ingresar el código recibido y confirmar. El cambio de contraseña queda bloqueado en el frontend y en las tres rutas de contraseña (portal JWT, primer ingreso JWT y sesión legacy) hasta verificar el email actual.

Los códigos tienen seis dígitos, vencen a los 30 minutos, admiten cinco intentos y se pueden reenviar cada 60 segundos. Se guarda solamente su hash. Al confirmar se consume el código. El trigger de base invalida la verificación si cualquier integración o usuario cambia el email, incluso si luego vuelve a la dirección anterior.

Migración: `deployment/migrations/20261023_patient_email_verification.sql`. Aplicarla antes de cargar el código nuevo del backend.

## Correo

Se reutiliza el envío de códigos de autenticación. Admite:

- `RESEND_API_KEY` junto con `RESEND_FROM_EMAIL` (o `SMTP_FROM` por compatibilidad), o
- `SMTP_SERVER`, `SMTP_PORT` (587), `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`, `SMTP_FROM_NAME`, o
- los campos SMTP globales de `nextris.app_config` (incluido `use_tls`).

No se envían códigos si falta configuración o falla el proveedor. La transacción se revierte y la API devuelve 503. No se marca el email como validado hasta confirmar un código correcto.

## Validación

Desde backend: `venv/bin/python tests/test_patient_email_verification.py` (requiere BD y migración). Usa pacientes sintéticos dentro de transacciones que se revierten y un emisor simulado; no envía emails.

Desde frontend: `node tests/patient-email-ui.cjs` (requiere Vite en 5173 y Chromium de Playwright con sus bibliotecas). Intercepta todas las APIs y prueba el flujo en escritorio y móvil sin usar pacientes reales.
