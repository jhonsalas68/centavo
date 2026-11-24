import os
import re
import time
import uuid
from urllib.parse import quote
from fastapi import FastAPI, HTTPException, BackgroundTasks, Query
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from backend.downloader import extract_video_info, download_media, cleanup_old_files

app = FastAPI(title="Video Downloader Pro", version="2.2-ios")

# Registro en memoria de archivos ya listos para descarga instantánea (ideal para iOS Safari)
PREPARED_FILES = {}

def purge_expired_prepared():
    now = time.time()
    expired = [k for k, v in PREPARED_FILES.items() if now - v["created"] > 900]
    for k in expired:
        info = PREPARED_FILES.pop(k, None)
        if info and os.path.exists(info["path"]):
            try:
                os.remove(info["path"])
            except Exception:
                pass

def make_safe_filename(clean_filename: str, is_audio: bool) -> str:
    target_ext = ".mp3" if is_audio else ".mp4"
    raw_base = os.path.splitext(clean_filename)[0]
    safe_base = re.sub(r'[^a-zA-Z0-9_\- ]', '_', raw_base).strip()[:50] or ("audio" if is_audio else "video")
    return f"{safe_base}{target_ext}"

# Permitir CORS para desarrollo
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class InfoRequest(BaseModel):
    url: str

class PrepareRequest(BaseModel):
    url: str
    format_id: str = "best"
    is_audio: bool = False

@app.post("/api/info")
async def get_info(req: InfoRequest):
    """Obtiene detalles del video y resoluciones disponibles."""
    if not req.url or not req.url.strip():
        raise HTTPException(status_code=400, detail="Debes proporcionar una URL válida.")
    
    try:
        data = await run_in_threadpool(extract_video_info, req.url.strip())
        return data
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/prepare")
async def prepare_download(req: PrepareRequest):
    """Prepara el archivo en el servidor y devuelve un enlace directo instantáneo (100% compatible con iOS Safari)."""
    if not req.url or not req.url.strip():
        raise HTTPException(status_code=400, detail="URL inválida.")
    purge_expired_prepared()
    try:
        file_path, clean_filename = await run_in_threadpool(
            download_media,
            req.url.strip(),
            req.format_id,
            req.is_audio,
        )
        safe_name = make_safe_filename(clean_filename, req.is_audio)
        media_type = "audio/mpeg" if req.is_audio else "video/mp4"
        token = uuid.uuid4().hex
        PREPARED_FILES[token] = {
            "path": file_path,
            "filename": safe_name,
            "media_type": media_type,
            "created": time.time(),
        }
        return {
            "download_url": f"/api/file/{token}",
            "filename": safe_name,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/file/{token}")
async def serve_prepared_file(token: str):
    """Entrega instantáneamente un archivo ya preparado con cabeceras nativas de iOS Safari."""
    purge_expired_prepared()
    item = PREPARED_FILES.get(token)
    if not item or not os.path.exists(item["path"]):
        raise HTTPException(status_code=404, detail="El enlace de descarga ha expirado. Vuelve a generarlo.")
    return FileResponse(
        path=item["path"],
        media_type=item["media_type"],
        filename=item["filename"],
        headers={
            "Content-Disposition": f'attachment; filename="{item["filename"]}"',
            "Cache-Control": "no-store",
        },
    )

def remove_file(path: str):
    """Elimina el archivo tras completarse la descarga."""
    try:
        if os.path.exists(path):
            os.remove(path)
    except Exception:
        pass

@app.get("/api/download")
async def download_endpoint(
    background_tasks: BackgroundTasks,
    url: str = Query(..., description="URL del video"),
    format_id: str = Query("best", description="ID del formato"),
    is_audio: bool = Query(False, description="¿Convertir a MP3?")
):
    """Descarga el video o audio y lo envía al usuario."""
    try:
        file_path, clean_filename = download_media(
            url=url,
            format_id=format_id,
            is_audio=is_audio
        )
        # Programar eliminación para ahorrar espacio en disco
        background_tasks.add_task(remove_file, file_path)

        media_type = "audio/mpeg" if is_audio else "video/mp4"
        
        # Sanitizar nombre para cabeceras HTTP garantizando compatibilidad 100% con iOS Safari
        target_ext = ".mp3" if is_audio else ".mp4"
        raw_base = os.path.splitext(clean_filename)[0]
        safe_base = re.sub(r'[^a-zA-Z0-9_\- ]', '_', raw_base).strip()[:50] or "video"
        safe_ascii_name = f"{safe_base}{target_ext}"
        encoded_filename = quote(f"{raw_base[:60]}{target_ext}")

        headers = {
            "Content-Disposition": f'attachment; filename="{safe_ascii_name}"; filename*=UTF-8\'\'{encoded_filename}'
        }

        return FileResponse(
            path=file_path,
            media_type=media_type,
            headers=headers
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/health")
async def health():
    import shutil
    from backend.downloader import get_cookie_file
    return {
        "status": "ok",
        "service": "Video Downloader API",
        "version": "2.1-deno",
        "has_deno": bool(shutil.which("deno")),
        "has_cookies": bool(get_cookie_file()),
    }

# Servir archivos estáticos del frontend
FRONTEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend"))
if os.path.exists(FRONTEND_DIR):
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")

if __name__ == "__main__":
    import uvicorn
    cleanup_old_files()
    uvicorn.run("backend.app:app", host="127.0.0.1", port=8000, reload=True)
