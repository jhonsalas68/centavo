import os
import re
from urllib.parse import quote
from fastapi import FastAPI, HTTPException, BackgroundTasks, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from backend.downloader import extract_video_info, download_media, cleanup_old_files

app = FastAPI(title="Video Downloader Pro", version="1.0.0")

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

@app.post("/api/info")
async def get_info(req: InfoRequest):
    """Obtiene detalles del video y resoluciones disponibles."""
    if not req.url or not req.url.strip():
        raise HTTPException(status_code=400, detail="Debes proporcionar una URL válida.")
    
    try:
        data = extract_video_info(req.url.strip())
        return data
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

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
        
        # Sanitizar nombre para cabeceras HTTP (los navegadores y Uvicorn exigen ASCII en latin-1)
        # RFC 5987 / RFC 6266 permite UTF-8 seguro mediante filename*=UTF-8''...
        safe_ascii_name = re.sub(r'[^\x20-\x7E]', '_', clean_filename).strip() or "video"
        encoded_filename = quote(clean_filename)

        headers = {
            "Content-Disposition": f"attachment; filename=\"{safe_ascii_name}\"; filename*=UTF-8''{encoded_filename}"
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
    return {"status": "ok", "service": "Video Downloader API"}

# Servir archivos estáticos del frontend
FRONTEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend"))
if os.path.exists(FRONTEND_DIR):
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")

if __name__ == "__main__":
    import uvicorn
    cleanup_old_files()
    uvicorn.run("backend.app:app", host="127.0.0.1", port=8000, reload=True)
