"""Módulo de descarga de audio remoto usando yt-dlp.

Compatible con cualquier plataforma soportada por yt-dlp (YouTube, Blackboard
Collaborate, Panopto, Vimeo, Twitch, streams directos, etc.).
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Callable, Optional

try:
    import yt_dlp  # type: ignore
    YT_DLP_DISPONIBLE = True
except ImportError:
    YT_DLP_DISPONIBLE = False

ProgresoCallback = Callable[[str, int, str], None]

# Extensión de salida de audio normalizada
EXT_AUDIO_SALIDA = "m4a"

# Patrones de URL válidas
_RE_URL = re.compile(r"^https?://", re.IGNORECASE)


def es_url_remota(valor: str) -> bool:
    """Devuelve True si 'valor' es una URL HTTP/HTTPS."""
    return bool(_RE_URL.match(str(valor).strip()))


def descargar_audio(
    url: str,
    directorio_destino: Path,
    nombre_base: str = "audio_original",
    callback_progreso: Optional[ProgresoCallback] = None,
) -> Path:
    """Descarga exclusivamente la pista de audio desde 'url' y la guarda en
    'directorio_destino / f"{nombre_base}.m4a"'.

    Parámetros
    ----------
    url:
        Enlace remoto compatible con yt-dlp (YouTube, Blackboard, Panopto…).
    directorio_destino:
        Carpeta de destino donde se guardará el archivo de audio. Se crea
        automáticamente si no existe.
    nombre_base:
        Nombre del archivo de salida sin extensión (por defecto 'audio_original').
    callback_progreso:
        Función opcional ``(fase: str, porcentaje: int, mensaje: str) -> None``
        que recibe actualizaciones de progreso durante la descarga.

    Retorna
    -------
    Path
        Ruta absoluta al archivo .m4a descargado.

    Lanza
    -----
    ImportError
        Si yt-dlp no está instalado en el entorno.
    RuntimeError
        Si la URL falla, es inaccesible o el archivo no se generó tras la descarga.
    """
    if not YT_DLP_DISPONIBLE:
        raise ImportError(
            "yt-dlp no está disponible en el entorno. "
            "Instálalo con: pip install yt-dlp"
        )

    if not es_url_remota(url):
        raise ValueError(f"La URL proporcionada no parece válida o no comienza por http(s): {url!r}")

    directorio_destino = Path(directorio_destino)
    directorio_destino.mkdir(parents=True, exist_ok=True)
    ruta_salida = directorio_destino / f"{nombre_base}.{EXT_AUDIO_SALIDA}"

    # Si ya existe un archivo descargado previo, devolverlo sin re-descargar
    if ruta_salida.exists() and ruta_salida.stat().st_size > 0:
        if callback_progreso:
            callback_progreso("descarga", 100, f"Audio ya descargado: {ruta_salida.name}")
        return ruta_salida

    def _progress_hook(d: dict) -> None:
        """Hook interno de yt-dlp para reportar progreso."""
        if callback_progreso is None:
            return
        status = d.get("status", "")
        if status == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            descargado = d.get("downloaded_bytes", 0)
            if total > 0:
                pct = int(min(descargado / total * 95, 95))  # Reservar 5 % para postproceso
            else:
                pct = 10
            velocidad = d.get("_speed_str", "").strip() or "—"
            eta = d.get("_eta_str", "").strip() or "—"
            callback_progreso("descarga", pct, f"Descargando audio… {pct}% · {velocidad} · ETA {eta}")
        elif status == "finished":
            if callback_progreso:
                callback_progreso("descarga", 96, "Descarga completada. Extrayendo audio (ffmpeg)…")
        elif status == "error":
            if callback_progreso:
                callback_progreso("descarga", 0, "Error reportado por yt-dlp durante la descarga.")

    ydl_opts = {
        # Descargar EXCLUSIVAMENTE la mejor pista de audio disponible
        "format": "bestaudio/best",
        # Plantilla de nombre de salida (sin extensión; el postprocesador añade .m4a)
        "outtmpl": str(directorio_destino / f"{nombre_base}.%(ext)s"),
        # Postprocesador: extraer audio y convertir a M4A (AAC)
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "m4a",
                "preferredquality": "0",  # Calidad máxima VBR
            }
        ],
        # No mostrar salida de yt-dlp en terminal (se gestiona con el hook)
        "quiet": True,
        "no_warnings": False,
        # Hook de progreso personalizado
        "progress_hooks": [_progress_hook],
        # Reintentos en caso de error temporal de red
        "retries": 3,
        "fragment_retries": 3,
        # No sobreescribir si ya existe
        "nooverwrites": True,
    }

    try:
        if callback_progreso:
            callback_progreso("descarga", 2, f"Conectando con la fuente remota: {url[:60]}…")

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

    except yt_dlp.utils.DownloadError as exc:
        raise RuntimeError(
            f"Error al descargar el audio desde '{url}'.\n"
            f"Detalle: {exc}"
        ) from exc
    except Exception as exc:
        raise RuntimeError(
            f"Error inesperado durante la descarga de '{url}'.\n"
            f"Detalle: {exc}"
        ) from exc

    # Verificar que el archivo se generó correctamente
    if not ruta_salida.exists() or ruta_salida.stat().st_size == 0:
        # yt-dlp puede haber guardado con otra extensión en casos extremos; buscar alternativa
        candidatos = list(directorio_destino.glob(f"{nombre_base}.*"))
        candidatos = [c for c in candidatos if c.suffix.lower() in {".m4a", ".aac", ".mp3", ".opus", ".ogg", ".webm"}]
        if candidatos:
            return candidatos[0]
        raise RuntimeError(
            f"La descarga de '{url}' completó sin errores aparentes, pero no se "
            f"encontró el archivo de audio en: {ruta_salida}"
        )

    if callback_progreso:
        callback_progreso("descarga", 100, f"Audio listo: {ruta_salida.name} ({ruta_salida.stat().st_size // 1024} KB)")

    return ruta_salida
