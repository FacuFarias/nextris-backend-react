FROM python:3.12-slim

# Crear directorio de la app
WORKDIR /app

# Instalar dependencias del sistema para psycopg2/psycopg2-binary
RUN apt-get update \
    && apt-get install -y gcc libpq-dev build-essential \
    && rm -rf /var/lib/apt/lists/*
    
# Copiar dependencias
COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# Copiar código de la aplicación
COPY . .

# Exponer el puerto Flask/Gunicorn
EXPOSE 8000

# Lanzar Gunicorn
CMD ["gunicorn", "-c", "gunicorn-cfg.py", "run:app"]
