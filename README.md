# NextRIS Backend

API Flask/PostgreSQL para imágenes médicas, configurada para **una institución**.
La rama `main` funciona junto con la rama `ui2` del frontend.

[Instalación, actualización, migraciones y contratos](docs/GENERAL_EDITION.md).

```bash
python3.12 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Completar la configuración y aplicar las migraciones según la guía.
python run.py
```

La API escucha en `5001`, con rutas bajo `/api` y autenticación JWT. No hay cuentas
ni credenciales iniciales incluidas. El PACS y el visor se configuran por entorno.
Los servicios de imágenes se activan separadamente; iniciar la API no los arranca.
