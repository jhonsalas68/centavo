# OmniDownloader - Web de Descarga de Videos & Monetización

Una plataforma web completa, rápida y moderna para descargar videos y música de múltiples redes sociales (YouTube, TikTok, Instagram, Twitter/X, Facebook y +1000 sitios) con arquitectura lista para monetizar mediante anuncios.

---

## 🚀 Cómo Iniciar la Web

Simplemente haz doble clic en el archivo:
👉 **`iniciar_servidor.bat`**

O desde la terminal:
```bash
.\venv\Scripts\python.exe -m uvicorn backend.app:app --host 127.0.0.1 --port 8000 --reload
```
Luego abre tu navegador en: **`http://localhost:8000`**

---

## 💰 Guía de Monetización con Anuncios

### ¿Por qué NO usar Google AdSense?
Google AdSense tiene políticas estrictas contra webs que descargan contenido con copyright o de YouTube. Rechazarán el sitio o inhabilitarán la cuenta.

### Redes Publicitarias que SÍ Aceptan este Sitio:
1. **[Monetag](https://monetag.com/) (Antigua PropellerAds):**
   - La red más recomendada para sitios de descarga.
   - Formatos ideales: **OnClick (Popunder)**, **Push Notifications**, y **Vignette Banner**.
   - Pagos por PayPal, transferencia o cripto.

2. **[Adsterra](https://adsterra.com/):**
   - Aprobación casi instantánea (no requiere meses de antigüedad).
   - Formatos ideales: **Social Bar** (banners flotantes con altísimo CTR), **Banners 728x90 y 300x250**, y **Direct Link**.

3. **[PopAds](https://www.popads.net/):**
   - Especialistas en ventanas emergentes por detrás (popunders), pagan por cada 1.000 impresiones con tasas altas.

---

## 🎯 Ubicaciones de los Anuncios en el Código

En el archivo `frontend/index.html` ya tienes los contenedores preparados con comentarios para pegar tus etiquetas de script:

1. **Espacio #1 (Header Leaderboard - 728x90 / 320x50):**
   - Ubicación: Parte superior del sitio, debajo de la barra de navegación.
   - Ideal para: Banners visuales tradicionales.

2. **Espacio #2 (In-Feed / 300x250 o Social Bar):**
   - Ubicación: Justo debajo de las opciones de calidad del video.
   - Muy alto CTR porque el usuario ya tiene la atención fija en esa zona antes de descargar.

3. **Espacio #3 (Modal con Cuenta Regresiva de 3 Segundos):**
   - Ubicación: En el modal que se abre cuando el usuario presiona "Descargar".
   - Genera impresiones garantizadas y da tiempo al usuario para ver el anuncio antes de comenzar la descarga.

4. **Popunder / OnClick:**
   - Para añadir un popunder de Monetag o Adsterra, pega el `<script>` que te proporcione la red publicitaria justo antes de la etiqueta de cierre `</body>` en `frontend/index.html`.

---

## 🛠️ Tecnologías Utilizadas
- **Backend:** Python 3.11 + FastAPI + Uvicorn
- **Descargas:** `yt-dlp` (motor de extracción actualizado) + `imageio-ffmpeg` (procesamiento y unión de audio/video)
- **Frontend:** HTML5 + Tailwind CSS (Diseño oscuro moderno y responsivo) + FontAwesome 6
