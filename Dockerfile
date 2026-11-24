FROM denoland/deno:bin AS deno

FROM python:3.11-slim

# Instalar FFmpeg y certificados SSL
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copiar binario oficial de Deno (runtime JS oficial de yt-dlp para resolver YouTube)
COPY --from=deno /deno /usr/local/bin/deno

WORKDIR /app

# Instalar librerías de Python (siempre la última versión de yt-dlp)
COPY backend/requirements.txt requirements.txt
RUN pip install --no-cache-dir --upgrade -r requirements.txt

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
