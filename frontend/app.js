document.addEventListener('DOMContentLoaded', () => {
  const form = document.getElementById('downloadForm');
  const urlInput = document.getElementById('urlInput');
  const pasteBtn = document.getElementById('pasteBtn');
  const fetchBtn = document.getElementById('fetchBtn');
  const btnText = document.getElementById('btnText');
  const alertBox = document.getElementById('alertBox');

  const resultCard = document.getElementById('resultCard');
  const videoThumb = document.getElementById('videoThumb');
  const videoTitle = document.getElementById('videoTitle');
  const videoAuthor = document.getElementById('videoAuthor').querySelector('span');
  const videoDuration = document.getElementById('videoDuration');
  const videoPlatform = document.getElementById('videoPlatform');

  const tabVideo = document.getElementById('tabVideo');
  const tabAudio = document.getElementById('tabAudio');
  const videoFormatsList = document.getElementById('videoFormatsList');
  const audioFormatsList = document.getElementById('audioFormatsList');

  const downloadModal = document.getElementById('downloadModal');
  const closeDownloadModalBtn = document.getElementById('closeDownloadModalBtn');
  const modalPreparingState = document.getElementById('modalPreparingState');
  const modalReadyState = document.getElementById('modalReadyState');
  const readyFileName = document.getElementById('readyFileName');
  const finalDownloadLink = document.getElementById('finalDownloadLink');
  const modalProgressBar = document.getElementById('modalProgressBar');

  if (closeDownloadModalBtn && downloadModal) {
    closeDownloadModalBtn.addEventListener('click', () => downloadModal.classList.add('hidden'));
  }

  const adGuideBtn = document.getElementById('adGuideBtn');
  const adGuideModal = document.getElementById('adGuideModal');
  const closeAdGuideBtn = document.getElementById('closeAdGuideBtn');
  const closeAdGuideBtn2 = document.getElementById('closeAdGuideBtn2');

  let currentVideoData = null;

  // Botón pegar del portapapeles
  pasteBtn.addEventListener('click', async () => {
    try {
      const text = await navigator.clipboard.readText();
      if (text) {
        urlInput.value = text.trim();
        urlInput.focus();
      }
    } catch (err) {
      showAlert('No se pudo acceder al portapapeles. Pega el enlace manualmente.', 'error');
    }
  });

  // Alternar pestañas Video / Audio
  tabVideo.addEventListener('click', () => {
    tabVideo.classList.add('active', 'border-indigo-500', 'text-indigo-400');
    tabVideo.classList.remove('border-transparent', 'text-slate-400');
    tabAudio.classList.remove('active', 'border-indigo-500', 'text-indigo-400');
    tabAudio.classList.add('border-transparent', 'text-slate-400');

    videoFormatsList.classList.remove('hidden');
    audioFormatsList.classList.add('hidden');
  });

  tabAudio.addEventListener('click', () => {
    tabAudio.classList.add('active', 'border-indigo-500', 'text-indigo-400');
    tabAudio.classList.remove('border-transparent', 'text-slate-400');
    tabVideo.classList.remove('active', 'border-indigo-500', 'text-indigo-400');
    tabVideo.classList.add('border-transparent', 'text-slate-400');

    audioFormatsList.classList.remove('hidden');
    videoFormatsList.classList.add('hidden');
  });

  // Modales de guía de anuncios (si existen en el DOM)
  if (adGuideBtn && adGuideModal) {
    adGuideBtn.addEventListener('click', () => adGuideModal.classList.remove('hidden'));
  }
  if (closeAdGuideBtn && adGuideModal) {
    closeAdGuideBtn.addEventListener('click', () => adGuideModal.classList.add('hidden'));
  }
  if (closeAdGuideBtn2 && adGuideModal) {
    closeAdGuideBtn2.addEventListener('click', () => adGuideModal.classList.add('hidden'));
  }

  // Manejar envío del formulario (Buscar video)
  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const url = urlInput.value.trim();
    if (!url) return;

    hideAlert();
    setLoading(true);
    resultCard.classList.add('hidden');

    try {
      const res = await fetch('/api/info', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url })
      });

      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || 'Error al procesar el enlace.');
      }

      currentVideoData = data;
      renderResult(data);
    } catch (err) {
      showAlert(err.message || 'Error de conexión con el servidor.', 'error');
    } finally {
      setLoading(false);
    }
  });

  function renderResult(data) {
    videoThumb.src = data.thumbnail || 'https://via.placeholder.com/640x360?text=Sin+Miniatura';
    videoTitle.textContent = data.title;
    videoAuthor.textContent = data.uploader;
    videoDuration.textContent = data.duration;
    videoPlatform.textContent = data.platform;

    // Render formatos de video
    videoFormatsList.innerHTML = '';
    if (data.video_formats && data.video_formats.length > 0) {
      data.video_formats.forEach(f => {
        const item = document.createElement('div');
        item.className = 'flex items-center justify-between gap-2 p-2.5 sm:p-3 bg-slate-950/70 border border-slate-800 rounded-xl hover:border-indigo-500/50 transition-colors';
        item.innerHTML = `
          <div class="flex items-center gap-2 sm:gap-3 min-w-0">
            <span class="w-7 h-7 sm:w-8 sm:h-8 flex-shrink-0 rounded-lg bg-indigo-600/10 text-indigo-400 flex items-center justify-center font-bold text-xs">
              <i class="fa-solid fa-play text-[9px] sm:text-[10px]"></i>
            </span>
            <div class="min-w-0">
              <div class="font-bold text-xs sm:text-sm text-slate-100 flex items-center gap-1.5 truncate">
                ${f.label}
                <span class="text-[9px] px-1 py-0.2 bg-slate-800 text-slate-400 rounded uppercase font-normal">${f.ext}</span>
              </div>
              <div class="text-[10px] sm:text-[11px] text-slate-400 truncate">Tamaño: <span class="font-medium text-slate-300">${f.size}</span></div>
            </div>
          </div>
          <button 
            onclick="triggerDownload('${encodeURIComponent(data.url)}', '${f.format_id}', false)"
            class="flex-shrink-0 px-3 sm:px-4 py-2 bg-indigo-600 hover:bg-indigo-500 active:bg-indigo-700 text-white rounded-lg text-xs font-bold transition flex items-center gap-1 shadow-md shadow-indigo-600/20 active:scale-95"
          >
            <i class="fa-solid fa-download"></i> <span>Descargar</span>
          </button>
        `;
        videoFormatsList.appendChild(item);
      });
    } else {
      videoFormatsList.innerHTML = '<p class="text-xs text-slate-500 p-2">No se encontraron formatos de video independientes.</p>';
    }

    // Render formatos de audio
    audioFormatsList.innerHTML = '';
    if (data.audio_formats && data.audio_formats.length > 0) {
      data.audio_formats.forEach(a => {
        const item = document.createElement('div');
        item.className = 'flex items-center justify-between gap-2 p-2.5 sm:p-3 bg-slate-950/70 border border-slate-800 rounded-xl hover:border-rose-500/50 transition-colors';
        item.innerHTML = `
          <div class="flex items-center gap-2 sm:gap-3 min-w-0">
            <span class="w-7 h-7 sm:w-8 sm:h-8 flex-shrink-0 rounded-lg bg-rose-600/10 text-rose-400 flex items-center justify-center font-bold text-xs">
              <i class="fa-solid fa-music text-[9px] sm:text-[10px]"></i>
            </span>
            <div class="min-w-0">
              <div class="font-bold text-xs sm:text-sm text-slate-100 truncate">${a.label}</div>
              <div class="text-[10px] sm:text-[11px] text-slate-400 truncate">Calidad: <span class="font-medium text-slate-300">${a.quality}</span></div>
            </div>
          </div>
          <button 
            onclick="triggerDownload('${encodeURIComponent(data.url)}', '${a.format_id}', true)"
            class="flex-shrink-0 px-3 sm:px-4 py-2 bg-rose-600 hover:bg-rose-500 active:bg-rose-700 text-white rounded-lg text-xs font-bold transition flex items-center gap-1 shadow-md shadow-rose-600/20 active:scale-95"
          >
            <i class="fa-solid fa-download"></i> <span>Descargar MP3</span>
          </button>
        `;
        audioFormatsList.appendChild(item);
      });
    }

    resultCard.classList.remove('hidden');
    resultCard.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }

  // Preparar archivo en servidor y mostrar botón nativo directo (100% compatible con iOS Safari)
  window.triggerDownload = async (encodedUrl, formatId, isAudio) => {
    const url = decodeURIComponent(encodedUrl);
    hideAlert();

    modalPreparingState.classList.remove('hidden');
    modalReadyState.classList.add('hidden');
    downloadModal.classList.remove('hidden');

    try {
      const res = await fetch('/api/prepare', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url, format_id: formatId, is_audio: isAudio })
      });

      const contentType = (res.headers.get('content-type') || '').toLowerCase();
      if (!res.ok || !contentType.includes('application/json')) {
        let msg = 'El servidor está ocupado o reiniciándose. Intenta de nuevo en unos segundos.';
        if (contentType.includes('application/json')) {
          const errData = await res.json().catch(() => null);
          if (errData && errData.detail) msg = errData.detail;
        }
        downloadModal.classList.add('hidden');
        showAlert(msg, 'error');
        return;
      }

      const data = await res.json();
      readyFileName.textContent = data.filename;
      finalDownloadLink.href = data.download_url;
      finalDownloadLink.setAttribute('download', data.filename);

      modalPreparingState.classList.add('hidden');
      modalReadyState.classList.remove('hidden');

      // En PC y Android iniciar automáticamente; en iOS el usuario pulsa el botón verde (requisito nativo de Safari)
      const isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent) ||
        (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
      if (!isIOS) {
        finalDownloadLink.click();
      }
    } catch (err) {
      downloadModal.classList.add('hidden');
      showAlert('Error de conexión al preparar la descarga. Intenta de nuevo.', 'error');
    }
  };

  function setLoading(isLoading) {
    if (isLoading) {
      fetchBtn.disabled = true;
      btnText.textContent = 'Analizando...';
      fetchBtn.querySelector('i').className = 'fa-solid fa-circle-notch fa-spin text-sm';
    } else {
      fetchBtn.disabled = false;
      btnText.textContent = 'Obtener Enlaces';
      fetchBtn.querySelector('i').className = 'fa-solid fa-arrow-right text-sm';
    }
  }

  function showAlert(msg, type = 'error') {
    alertBox.textContent = msg;
    alertBox.className = type === 'error'
      ? 'mt-3 p-3 rounded-xl text-xs sm:text-sm font-medium border bg-rose-500/10 border-rose-500/30 text-rose-300'
      : 'mt-3 p-3 rounded-xl text-xs sm:text-sm font-medium border bg-emerald-500/10 border-emerald-500/30 text-emerald-300';
    alertBox.classList.remove('hidden');
  }

  function hideAlert() {
    alertBox.classList.add('hidden');
  }
});
