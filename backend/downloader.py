import os
import glob
import time
import uuid
import re
import shutil
import subprocess
import tempfile
import yt_dlp
import imageio_ffmpeg

# Directorio de descargas
DOWNLOADS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "downloads"))
os.makedirs(DOWNLOADS_DIR, exist_ok=True)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)

def get_ffmpeg_path():
    """Obtiene la ruta binaria ejecutable de FFmpeg (sistema en Linux o imageio-ffmpeg en Windows)."""
    if os.name != "nt":
        return "ffmpeg"
    try:
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"

def get_cookie_file():
    """Copia las cookies a /tmp (escribible) desde Render Secret Files (/etc/secrets/cookies.txt) o YOUTUBE_COOKIES."""
    cookie_path = os.path.join(tempfile.gettempdir(), "yt_cookies.txt")
    secret_path = "/etc/secrets/cookies.txt"
    if os.path.exists(secret_path) and os.path.getsize(secret_path) > 0:
        if not os.path.exists(cookie_path) or os.path.getsize(cookie_path) == 0:
            shutil.copyfile(secret_path, cookie_path)
        return cookie_path
    cookies_env = os.environ.get("YOUTUBE_COOKIES", "").strip()
    if not cookies_env:
        return None
    if not os.path.exists(cookie_path) or os.path.getsize(cookie_path) == 0:
        with open(cookie_path, "w", encoding="utf-8") as f:
            f.write(cookies_env)
    return cookie_path

def is_youtube_url(url: str) -> bool:
    return bool(re.search(r"(youtube\.com|youtu\.be)", url, re.IGNORECASE))

def get_client_strategies(url: str):
    """Devuelve estrategias de clientes de yt-dlp para evitar bloqueos de bot en servidores cloud."""
    if is_youtube_url(url):
        if get_cookie_file():
            # Con cookies + JS runtime (node), el cliente por defecto de yt-dlp es el mejor
            return [
                None,
                {'youtube': {'player_client': ['web', 'mweb']}},
                {'youtube': {'player_client': ['tv_embedded', 'android_vr']}},
            ]
        return [
            None,
            {'youtube': {'player_client': ['tv_embedded', 'android_vr']}},
            {'youtube': {'player_client': ['android', 'mweb']}},
        ]
    return [None]

def build_base_opts(extra_opts=None, extractor_args=None):
    opts = {
        'quiet': True,
        'no_warnings': True,
        'noplaylist': True,
        'geo_bypass': True,
        'source_address': '0.0.0.0',  # Forzar IPv4 para evitar bloqueos IPv6 en cloud
        'ffmpeg_location': get_ffmpeg_path(),
        'js_runtimes': {'node': {}, 'deno': {}},
        'remote_components': ['ejs:github'],
        'http_headers': {
            'User-Agent': USER_AGENT,
            'Accept-Language': 'es-ES,es;q=0.9,en;q=0.8',
        },
        'socket_timeout': 20,
        'retries': 3,
    }
    cookie_file = get_cookie_file()
    if cookie_file:
        opts['cookiefile'] = cookie_file
    if extractor_args:
        opts['extractor_args'] = extractor_args
    if extra_opts:
        opts.update(extra_opts)
    return opts

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

def friendly_error(err_str: str) -> str:
    lower = err_str.lower()
    if "sign in to confirm" in lower or "not a bot" in lower:
        return "YouTube bloqueó temporalmente esta solicitud desde el servidor. Verifica tus cookies.txt en Render o intenta con otro enlace."
    if "private video" in lower or "login required" in lower or "only works when logged-in" in lower:
        return "Este video es privado o requiere iniciar sesión para verlo."
    if "video unavailable" in lower or "this video is not available" in lower:
        return "El video no está disponible o fue eliminado."
    if "unsupported url" in lower:
        return "El enlace no es válido o la plataforma no es compatible."
    return f"No se pudo procesar el enlace: {err_str[:220]}"

def extract_video_info(url: str):
    """Extrae metadatos y opciones de calidad de la URL sin descargar."""
    info = None
    last_error = None

    for strategy in get_client_strategies(url):
        ydl_opts = build_base_opts({'skip_download': True}, extractor_args=strategy)
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
            if info:
                break
        except Exception as e:
            last_error = str(e)
            continue

    if not info:
        raise ValueError(friendly_error(last_error or "No se obtuvo información del video."))

    # Si es una playlist o galería, tomar la primera entrada válida
    if 'entries' in info and info['entries']:
        entries = [e for e in info['entries'] if e]
        if entries:
            info = entries[0]

    title = info.get('title', 'Video sin título')
    thumbnail = info.get('thumbnail')
    duration = format_duration(info.get('duration'))
    uploader = info.get('uploader', info.get('channel', 'Desconocido'))
    platform = info.get('extractor_key', 'Web')

    raw_formats = info.get('formats') or ([info] if info.get('url') else [])
    video_options = []
    seen_resolutions = set()

    # Priorizar formatos directos HTTPS + H.264 (avc1) + MP4 sobre HLS (m3u8) o VP9/AV1
    # Esto evita descargas corruptas/lentas en HLS y garantiza reproducción 100% en iOS/Android/PC
    def format_sort_key(f):
        height = f.get('height') or 0
        fid = str(f.get('format_id', '')).lower()
        if not height:
            if 'hd' in fid:
                height = 720
            elif 'sd' in fid:
                height = 480
        proto = str(f.get('protocol', '')).lower()
        is_direct_http = 1 if proto in ('https', 'http') else 0
        is_h264 = 1 if str(f.get('vcodec', '')).startswith('avc') else 0
        is_mp4 = 1 if f.get('ext') == 'mp4' else 0
        has_audio = 1 if (f.get('acodec') and f.get('acodec') != 'none') else 0
        tbr = f.get('tbr') or 0
        return (height, is_direct_http, is_h264, is_mp4, has_audio, tbr)

    video_candidates = [
        f for f in raw_formats
        if f.get('vcodec') != 'none' and f.get('protocol') not in ('mhtml',)
    ]
    sorted_formats = sorted(video_candidates, key=format_sort_key, reverse=True)

    for f in sorted_formats:
        height = f.get('height')
        fid = str(f.get('format_id', '')).lower()
        if not height:
            if 'hd' in fid:
                height = 720
            elif 'sd' in fid:
                height = 480
            else:
                continue

        res_label = f"{height}p"
        if height >= 2160:
            res_label = "4K (2160p)"
        elif height >= 1440:
            res_label = "2K (1440p)"
        elif height >= 1080:
            res_label = "1080p Full HD"
        elif height >= 720:
            res_label = "720p HD (Rápido)" if (f.get('acodec') and f.get('acodec') != 'none') else "720p HD"
        elif height >= 480:
            res_label = "480p SD"
        elif height >= 360:
            res_label = "360p"

        if res_label in seen_resolutions:
            continue
        seen_resolutions.add(res_label)

        size_bytes = f.get('filesize') or f.get('filesize_approx')

        video_options.append({
            "format_id": f.get('format_id') or "best",
            "label": res_label,
            "ext": "mp4",
            "height": height,
            "size": format_size(size_bytes),
            "quality": "Alta" if height >= 720 else "Estándar"
        })

    if not video_options:
        video_options.append({
            "format_id": "best",
            "label": "Mejor calidad disponible",
            "ext": "mp4",
            "height": 720,
            "size": "Auto",
            "quality": "Alta"
        })

    audio_options = [
        {
            "format_id": "bestaudio/best",
            "label": "Audio MP3 (Máxima Calidad)",
            "ext": "mp3",
            "size": "Variable",
            "quality": "192 kbps / Best"
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
    file_id = str(uuid.uuid4())[:8]
    out_template = os.path.join(DOWNLOADS_DIR, f"{file_id}_%(title).50s.%(ext)s")

    if is_audio:
        extra_opts = {
            'format': 'bestaudio/best',
            'outtmpl': out_template,
            'concurrent_fragment_downloads': 8,
            'buffersize': 1024 * 1024,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
        }
    else:
        if format_id and format_id not in ("best", "bestvideo+bestaudio/best"):
            selected_format = (
                f"{format_id}[acodec!=none]/"
                f"{format_id}+bestaudio[protocol^=http][ext=m4a]/"
                f"{format_id}+bestaudio[ext=m4a]/"
                f"{format_id}+bestaudio/"
                f"best[ext=mp4]/best"
            )
        else:
            selected_format = (
                "best[protocol^=http][ext=mp4][acodec!=none]/"
                "bestvideo[protocol^=http][vcodec^=avc][ext=mp4]+bestaudio[protocol^=http][ext=m4a]/"
                "bestvideo[ext=mp4]+bestaudio[ext=m4a]/"
                "bestvideo+bestaudio/best"
            )

        extra_opts = {
            'format': selected_format,
            'outtmpl': out_template,
            'merge_output_format': 'mp4',
            'concurrent_fragment_downloads': 4,
            'buffersize': 1024 * 1024,
            'postprocessor_args': {
                'Merger': ['-c:v', 'copy', '-c:a', 'aac', '-movflags', '+faststart'],
            },
        }

    downloaded = False
    last_error = None
    for strategy in get_client_strategies(url):
        ydl_opts = build_base_opts(extra_opts, extractor_args=strategy)
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.extract_info(url, download=True)
            downloaded = True
            break
        except Exception as e:
            last_error = str(e)
            continue

    if not downloaded:
        raise ValueError(friendly_error(last_error or "Error al descargar el archivo."))

    matching_files = glob.glob(os.path.join(DOWNLOADS_DIR, f"{file_id}_*"))
    if not matching_files:
        raise FileNotFoundError("El archivo descargado no se pudo encontrar en el servidor.")

    file_path = matching_files[0]
    orig_filename = os.path.basename(file_path)

    # Verificar que el archivo sea un MP4 real (cabecera 'ftyp') y no un MPEG-TS de HLS renombrado
    if not is_audio:
        try:
            with open(file_path, "rb") as f:
                header = f.read(12)
            if len(header) >= 8 and header[4:8] != b"ftyp":
                fixed_path = os.path.join(DOWNLOADS_DIR, f"{file_id}_fixed.mp4")
                ffmpeg_exe = get_ffmpeg_path()
                res = subprocess.run(
                    [
                        ffmpeg_exe, "-y", "-i", file_path,
                        "-c:v", "copy", "-c:a", "aac",
                        "-movflags", "+faststart",
                        fixed_path
                    ],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=120
                )
                if res.returncode == 0 and os.path.exists(fixed_path) and os.path.getsize(fixed_path) > 0:
                    try:
                        os.remove(file_path)
                    except Exception:
                        pass
                    file_path = fixed_path
        except Exception:
            pass

    clean_name = orig_filename[9:] if len(orig_filename) > 9 else orig_filename

    expected_ext = ".mp3" if is_audio else ".mp4"
    base_part, cur_ext = os.path.splitext(clean_name)
    if not cur_ext or cur_ext.lower() != expected_ext:
        clean_name = f"{base_part}{expected_ext}"

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
