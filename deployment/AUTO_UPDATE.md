# 🤖 Configuración de Auto-Actualización

Esta guía te ayudará a configurar el webhook para que el servidor de desarrollo se actualice automáticamente cuando el frontend haga push.

## 🎯 Objetivo

Cuando el programador frontend haga `git push`, el servidor dev se actualizará automáticamente en 1-2 minutos, **sin tu intervención**.

---

## 📋 Paso 1: Instalar el Webhook en la VPS

### Conectar a la VPS

```bash
ssh root@148.230.72.8
```

### Ejecutar script de instalación

```bash
cd /var/www/nextris-dev/deployment
bash setup-auto-update.sh
```

El script:
- ✓ Instalará el servidor webhook
- ✓ Configurará el servicio systemd
- ✓ Abrirá el puerto 9000 en firewall
- ✓ Iniciará el webhook

### Verificar que funciona

```bash
# Ver estado
systemctl status github-webhook

# Probar endpoint
curl http://localhost:9000/health

# Deberías ver: {"status": "ok"}
```

---

## 📋 Paso 2: Configurar Webhook en GitHub

### 1. Ir a la configuración del repositorio frontend

Abre en tu navegador:
```
https://github.com/FacuFarias/Multitenant-NextRIS-Frontend/settings/hooks
```

### 2. Click en "Add webhook"

### 3. Completar el formulario

**Payload URL:**
```
http://148.230.72.8:9000/webhook
```

**Content type:**
```
application/json
```

**Secret:**
```
nextris_webhook_secret_2025
```

**SSL verification:**
```
✓ Disable (solo para desarrollo)
```

**Which events would you like to trigger this webhook?**
```
○ Just the push event
```

**Active:**
```
☑ Active
```

### 4. Click en "Add webhook"

GitHub enviará un "ping" para probar la conexión.

### 5. Verificar que funciona

En la página de webhooks, deberías ver:
- ✓ Checkmark verde junto al webhook
- ✓ En "Recent Deliveries": ping exitoso (código 200)

---

## 🧪 Paso 3: Probar la Auto-Actualización

### En tu VPS, ver logs en tiempo real:

```bash
# Terminal 1: Ver logs del webhook
journalctl -u github-webhook -f

# Terminal 2: Ver logs del servidor dev
journalctl -u nextris-dev -f
```

### Hacer un cambio de prueba:

1. **El frontend** edita un archivo (ejemplo: README.md)
2. **El frontend** hace:
   ```bash
   git add .
   git commit -m "Test auto-update"
   git push
   ```
3. **GitHub** envía webhook a tu servidor
4. **Tu servidor** se actualiza automáticamente
5. **Frontend** refresca http://148.230.72.8:5000 y ve los cambios

Deberías ver en los logs:
```
Actualizando frontend desde commit: Test auto-update
Frontend actualizado
```

---

## 🔄 Cómo Funciona (Diagrama)

```
┌──────────────────┐
│  Frontend hace   │
│   git push       │
└────────┬─────────┘
         │
         v
┌──────────────────┐
│     GitHub       │
│  (detecta push)  │
└────────┬─────────┘
         │ webhook HTTP POST
         v
┌──────────────────┐
│  Tu VPS:9000     │
│  (github-webhook)│
└────────┬─────────┘
         │ ejecuta script
         v
┌──────────────────┐
│ update-dev-      │
│ server.sh        │
└────────┬─────────┘
         │
         v
┌──────────────────┐
│  1. git pull     │
│  2. sync files   │
│  3. restart app  │
└────────┬─────────┘
         │
         v
┌──────────────────┐
│  ✅ Servidor     │
│  actualizado     │
└──────────────────┘
```

---

## 🛠️ Comandos Útiles

### Ver estado del webhook

```bash
systemctl status github-webhook
```

### Ver logs del webhook

```bash
# En tiempo real
journalctl -u github-webhook -f

# Últimos 50 logs
journalctl -u github-webhook -n 50
```

### Reiniciar webhook

```bash
systemctl restart github-webhook
```

### Probar manualmente

```bash
# Health check
curl http://localhost:9000/health

# Desde fuera de la VPS
curl http://148.230.72.8:9000/health
```

### Ver webhooks recientes en GitHub

```
https://github.com/FacuFarias/Multitenant-NextRIS-Frontend/settings/hooks
```
Click en el webhook → "Recent Deliveries"

---

## 🐛 Solución de Problemas

### El webhook no se ejecuta

**1. Verificar que el servicio está corriendo:**
```bash
systemctl status github-webhook
```

**2. Ver logs de error:**
```bash
journalctl -u github-webhook -n 50
```

**3. Verificar el puerto:**
```bash
# Debe estar escuchando
netstat -tlnp | grep 9000

# Debe estar abierto
ufw status | grep 9000
```

**4. Probar desde fuera:**
```bash
# Desde tu PC Windows
Invoke-WebRequest -Uri "http://148.230.72.8:9000/health"
```

### GitHub muestra error 500

**Ver qué falló:**
1. GitHub → Settings → Webhooks
2. Click en el webhook
3. Recent Deliveries → Click en el delivery fallido
4. Ver "Response" y "Request"

**Revisar logs:**
```bash
journalctl -u github-webhook -n 100
```

### La actualización falla

**Ver logs del script de actualización:**
```bash
journalctl -u github-webhook -f
```

Busca líneas como:
```
Error al actualizar el submódulo
Error: [detalle del error]
```

**Probar manualmente:**
```bash
cd /var/www/nextris-dev/deployment
bash update-dev-server.sh
```

### El servidor no reinicia

**Verificar permisos:**
```bash
# El script debe poder ejecutar systemctl
ls -la /var/www/nextris-dev/deployment/update-dev-server.sh
```

**Ver logs del servicio:**
```bash
journalctl -u nextris-dev -n 50
```

---

## 🔐 Seguridad

### Cambiar el Secret

Si quieres cambiar el secret del webhook:

**1. Editar el servicio:**
```bash
nano /etc/systemd/system/github-webhook.service
```

**2. Cambiar la línea:**
```
Environment="WEBHOOK_SECRET=tu_nuevo_secret_aqui"
```

**3. Reiniciar:**
```bash
systemctl daemon-reload
systemctl restart github-webhook
```

**4. Actualizar en GitHub:**
- GitHub → Settings → Webhooks
- Edit webhook
- Cambiar Secret
- Update webhook

---

## ✅ Checklist de Verificación

- [ ] Servicio github-webhook está activo
- [ ] Puerto 9000 está abierto en firewall
- [ ] Health endpoint responde: `curl http://localhost:9000/health`
- [ ] Webhook configurado en GitHub
- [ ] Webhook muestra checkmark verde en GitHub
- [ ] Test ping fue exitoso (código 200)
- [ ] Push de prueba actualiza el servidor

---

## 🎉 ¡Todo Listo!

Ahora el flujo es:

1. **Frontend** hace cambios y push
2. **2 minutos después** → cambios visibles en http://148.230.72.8:5000
3. **Tú** no haces nada 😎

---

**¿Problemas?** Revisa los logs:
```bash
journalctl -u github-webhook -f
```
