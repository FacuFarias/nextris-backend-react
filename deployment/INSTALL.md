# 🚀 Instalación del Servidor de Desarrollo

## Configuración
- **Servidor:** Ubuntu 24.04
- **IP:** 148.230.72.8
- **Puerto:** 5000
- **URL:** http://148.230.72.8:5000

---

## 📋 Pasos de Instalación

### 1. Conectar a la VPS

```bash
ssh root@148.230.72.8
```

### 2. Ejecutar instalación automática

```bash
# Opción A: Instalación directa desde GitHub
curl -o quick-install.sh https://raw.githubusercontent.com/FacuFarias/Multitenant-NextRIS/feature/1/deployment/quick-install.sh
chmod +x quick-install.sh
bash quick-install.sh
```

**O si prefieres clonar primero:**

```bash
# Opción B: Clonar y ejecutar
git clone --recurse-submodules -b feature/1 https://github.com/FacuFarias/Multitenant-NextRIS.git /tmp/nextris-setup
cd /tmp/nextris-setup/deployment
chmod +x quick-install.sh
bash quick-install.sh
```

### 3. Verificar instalación

```bash
# Ver estado del servicio
systemctl status nextris-dev

# Ver logs
journalctl -u nextris-dev -f
```

### 4. Acceder desde el navegador

Abre: **http://148.230.72.8:5000**

---

## 🔄 Actualizar cuando el Frontend cambie

Cuando el programador frontend haga push de cambios:

```bash
ssh root@148.230.72.8
cd /var/www/nextris-dev/deployment
bash update-dev-server.sh
```

---

## 🛠️ Comandos Útiles

```bash
# Ver estado
systemctl status nextris-dev

# Reiniciar servidor
systemctl restart nextris-dev

# Detener servidor
systemctl stop nextris-dev

# Iniciar servidor
systemctl start nextris-dev

# Ver logs en tiempo real
journalctl -u nextris-dev -f

# Ver últimos 50 logs
journalctl -u nextris-dev -n 50

# Probar desde el servidor
curl http://localhost:5000
```

---

## 📁 Ubicaciones Importantes

```bash
/var/www/nextris-dev/          # Directorio principal
/var/www/nextris-dev/.env      # Variables de entorno
/var/www/nextris-dev/frontend/ # Submódulo del frontend
/var/www/nextris-dev/apps/     # Código de la aplicación
```

---

## 🐛 Solución de Problemas

### El servicio no inicia

```bash
# Ver logs de error
journalctl -u nextris-dev -n 50 --no-pager

# Probar manualmente
cd /var/www/nextris-dev
sudo -u nextris venv/bin/python run.py
```

### Puerto bloqueado

```bash
# Verificar firewall
ufw status

# Abrir puerto si es necesario
ufw allow 5000/tcp

# Ver qué está usando el puerto
netstat -tlnp | grep 5000
```

### Error de permisos

```bash
# Corregir permisos
chown -R nextris:nextris /var/www/nextris-dev
```

### Error de base de datos

Editar credenciales:
```bash
nano /var/www/nextris-dev/.env
# Ajustar DB_USER, DB_PASS, DB_HOST, etc.

# Reiniciar
systemctl restart nextris-dev
```

---

## 🔐 Seguridad

El archivo `.env` contiene credenciales sensibles. Asegúrate de que:
- Solo el usuario `nextris` tenga acceso
- No esté accesible desde web
- Firewall solo permita puertos necesarios

---

## ✅ Checklist Post-Instalación

- [ ] Servicio `nextris-dev` está activo
- [ ] Puerto 5000 está abierto en firewall
- [ ] Puedes acceder a http://148.230.72.8:5000
- [ ] Las credenciales de DB son correctas
- [ ] El frontend se ve correctamente
- [ ] Logs no muestran errores críticos

---

**¿Todo listo? ¡A desarrollar! 🎉**
