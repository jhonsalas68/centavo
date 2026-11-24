import os
import re
import time
import uuid
import threading
from urllib.parse import quote
from fastapi import FastAPI, HTTPException, BackgroundTasks, Query
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from backend.downloader import extract_video_info, download_media, cleanup_old_files

app = FastAPI(title="Video Downloader Pro", version="2.3-progress")

# Registro en memoria de archivos listos y trabajos en curso con progreso en tiempo real
PREPARED_FILES = {}
JOBS = {}

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
    expired_jobs = [k for k, v in JOBS.items() if now - v["created"] > 900]
    for k in expired_jobs:
        JOBS.pop(k, None)

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

def _run_prepare_job(job_id: str, url: str, format_id: str, is_audio: bool):
    def on_progress(status, percent=None, eta=None, speed="", message=""):
        job = JOBS.get(job_id)
        if not job:
            return
        job["status"] = status
        if percent is not None:
            job["percent"] = max(job["percent"], min(99, int(percent)))
        job["eta"] = eta
        if speed:
            job["speed"] = speed
        if message:
            job["message"] = message

    try:
        file_path, clean_filename = download_media(
            url,
            format_id,
            is_audio,
            progress_callback=on_progress,
        )
        safe_name = make_safe_filename(clean_filename, is_audio)
        media_type = "audio/mpeg" if is_audio else "video/mp4"
        token = uuid.uuid4().hex
        PREPARED_FILES[token] = {
            "path": file_path,
            "filename": safe_name,
            "media_type": media_type,
            "created": time.time(),
        }
        job = JOBS.get(job_id)
        if job:
            job.update({
                "status": "ready",
                "percent": 100,
                "eta": 0,
                "message": "¡Archivo listo para guardar!",
                "download_url": f"/api/file/{token}",
                "filename": safe_name,
            })
    except Exception as e:
        job = JOBS.get(job_id)
        if job:
            job.update({
                "status": "error",
                "error": str(e),
                "message": str(e),
            })

@app.post("/api/prepare")
async def prepare_download(req: PrepareRequest):
    """Inicia la preparación en segundo plano y devuelve job_id para consultar % real y ETA."""
    if not req.url or not req.url.strip():
        raise HTTPException(status_code=400, detail="URL inválida.")
    purge_expired_prepared()
    job_id = uuid.uuid4().hex
    JOBS[job_id] = {
        "status": "starting",
        "percent": 3,
        "eta": None,
        "speed": "",
        "message": "Iniciando descarga en el servidor...",
        "download_url": None,
        "filename": None,
        "error": None,
        "created": time.time(),
    }
    t = threading.Thread(
        target=_run_prepare_job,
        args=(job_id, req.url.strip(), req.format_id, req.is_audio),
        daemon=True,
    )
    t.start()
    return {"job_id": job_id}

@app.get("/api/status/{job_id}")
async def job_status(job_id: str):
    """Devuelve porcentaje real, velocidad, ETA y enlace final del trabajo."""
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Trabajo de descarga no encontrado o expirado.")
    return {
        "status": job["status"],
        "percent": job["percent"],
        "eta": job["eta"],
        "speed": job["speed"],
        "message": job["message"],
        "download_url": job["download_url"],
        "filename": job["filename"],
        "error": job["error"],
    }

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
