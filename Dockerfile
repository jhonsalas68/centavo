FROM python:3.11-slim

# Instalar FFmpeg en el sistema Linux del contenedor
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Instalar librerías de Python
COPY backend/requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el código de la aplicación
COPY backend/ backend/
COPY frontend/ frontend/

# Crear carpeta para almacenar descargas temporales
RUN mkdir -p downloads

# Puerto por defecto para plataformas Cloud
EXPOSE 8000
ENV PORT=8000

# Arrancar la aplicación usando la variable PORT de la plataforma
CMD uvicorn backend.app:app --host 0.0.0.0 --port ${PORT:-8000}
