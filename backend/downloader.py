import os
import glob
import time
import uuid
import re
import yt_dlp
import imageio_ffmpeg

# Directorio de descargas
DOWNLOADS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "downloads"))
os.makedirs(DOWNLOADS_DIR, exist_ok=True)

def get_ffmpeg_path():
    """Obtiene la ruta binaria ejecutable de FFmpeg incluida con imageio-ffmpeg."""
    try:
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"

def format_duration(seconds):
    """Convierte segundos a formato MM:SS o HH:MM:SS."""
    if not seconds:
        return "Desconocido"
    seconds = int(seconds)
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"

def format_size(bytes_size):
    """Convierte bytes a formato legible (MB, GB)."""
    if not bytes_size:
        return "~"
    mb = bytes_size / (1024 * 1024)
    if mb > 1024:
        return f"{mb / 1024:.1f} GB"
    return f"{mb:.1f} MB"

def sanitize_filename(name):
    """Limpia el nombre del archivo para evitar caracteres no válidos en Windows/Linux."""
    return re.sub(r'[\\/*?:"<>|]', "", name).strip()

def extract_video_info(url: str):
    """Extrae metadatos y opciones de calidad de la URL sin descargar."""
    ffmpeg_exe = get_ffmpeg_path()

    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'skip_download': True,
        'ffmpeg_location': ffmpeg_exe,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(url, download=False)
        except Exception as e:
            raise ValueError(f"No se pudo procesar el enlace: {str(e)}")

    if not info:
        raise ValueError("No se obtuvo información del video.")

    title = info.get('title', 'Video sin título')
    thumbnail = info.get('thumbnail')
    duration = format_duration(info.get('duration'))
    uploader = info.get('uploader', info.get('channel', 'Desconocido'))
    platform = info.get('extractor_key', 'Web')

    raw_formats = info.get('formats', [])
    video_options = []
    seen_resolutions = set()

    # Identificar las mejores opciones de video (1080p, 720p, 480p, 360p, etc.)
    # Ordenar por resolución descendente
    sorted_formats = sorted(
        [f for f in raw_formats if f.get('vcodec') != 'none'],
        key=lambda x: (x.get('height') or 0, x.get('tbr') or 0),
        reverse=True
    )

    for f in sorted_formats:
        height = f.get('height')
        if not height:
            continue
        
        # Agrupar por resolución común
        res_label = f"{height}p"
        if height >= 2160:
            res_label = "4K (2160p)"
        elif height >= 1440:
            res_label = "2K (1440p)"
        elif height >= 1080:
            res_label = "1080p Full HD"
        elif height >= 720:
            res_label = "720p HD"
        elif height >= 480:
            res_label = "480p SD"
        elif height >= 360:
            res_label = "360p"

        if res_label in seen_resolutions:
            continue
        seen_resolutions.add(res_label)

        size_bytes = f.get('filesize') or f.get('filesize_approx')
        
        video_options.append({
            "format_id": f.get('format_id'),
            "label": res_label,
            "ext": "mp4",
            "height": height,
            "size": format_size(size_bytes),
            "quality": "Alta" if height >= 720 else "Estándar"
        })

    # Si no se detectaron resoluciones específicas, ofrecer la mejor combinación general
    if not video_options:
        video_options.append({
            "format_id": "bestvideo+bestaudio/best",
            "label": "Mejor calidad disponible",
            "ext": "mp4",
            "height": 720,
            "size": "Auto",
            "quality": "Alta"
        })

    # Opción de Audio MP3
    audio_options = [
        {
            "format_id": "bestaudio/best",
            "label": "Audio MP3 (Máxima Calidad)",
            "ext": "mp3",
            "size": "Variable",
            "quality": "320 kbps / Best"
        }
    ]

    return {
        "title": title,
        "thumbnail": thumbnail,
        "duration": duration,
        "uploader": uploader,
        "platform": platform,
        "url": url,
        "video_formats": video_options,
        "audio_formats": audio_options
    }

def download_media(url: str, format_id: str, is_audio: bool = False, custom_title: str = None):
    """Descarga el video o audio especificado y devuelve la ruta local del archivo."""
    cleanup_old_files()
    ffmpeg_exe = get_ffmpeg_path()
    file_id = str(uuid.uuid4())[:8]

    if is_audio:
        out_template = os.path.join(DOWNLOADS_DIR, f"{file_id}_%(title).50s.%(ext)s")
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': out_template,
            'ffmpeg_location': ffmpeg_exe,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'quiet': True,
            'no_warnings': True
        }
    else:
        # Si se seleccionó un formato de video específico, unirlo con el mejor audio disponible
        if format_id and format_id != "bestvideo+bestaudio/best":
            selected_format = f"{format_id}+bestaudio/bestvideo+bestaudio/{format_id}/best"
        else:
            selected_format = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best[ext=mp4]/best"

        out_template = os.path.join(DOWNLOADS_DIR, f"{file_id}_%(title).50s.%(ext)s")
        ydl_opts = {
            'format': selected_format,
            'outtmpl': out_template,
            'ffmpeg_location': ffmpeg_exe,
            'merge_output_format': 'mp4',
            'quiet': True,
            'no_warnings': True
        }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(url, download=True)
        except Exception as e:
            raise ValueError(f"Error al descargar el archivo: {str(e)}")

    # Encontrar el archivo descargado
    matching_files = glob.glob(os.path.join(DOWNLOADS_DIR, f"{file_id}_*"))
    if not matching_files:
        raise FileNotFoundError("El archivo descargado no se pudo encontrar en el servidor.")

    file_path = matching_files[0]
    filename = os.path.basename(file_path)
    # Limpiar el prefijo de id para el nombre que ve el usuario
    clean_name = filename[9:] if len(filename) > 9 else filename

    return file_path, clean_name

def cleanup_old_files(max_age_seconds: int = 1800):
    """Elimina archivos en descargas con más de 30 minutos de antigüedad."""
    now = time.time()
    for f in glob.glob(os.path.join(DOWNLOADS_DIR, "*")):
        try:
            if os.path.isfile(f) and (now - os.path.getmtime(f) > max_age_seconds):
                os.remove(f)
        except Exception:
            pass
