"""
Módulo de notificaciones por Telegram para LectureFlow.

Lee TELEGRAM_BOT_TOKEN y TELEGRAM_CHAT_ID desde variables de entorno.
Si alguna variable falta o la petición falla, imprime una advertencia
discreta y devuelve False sin interrumpir la aplicación.

No añade dependencias externas: usa únicamente urllib.request de la
biblioteca estándar. Si el paquete 'requests' ya está disponible en el
entorno, se preferirá por legibilidad, pero el módulo funciona sin él.

Uso básico
----------
    from src.notificador import notificar_clase_completada, notificar_error

    notificar_clase_completada("Tema_01_SQL", "23m 14s", url_notion="https://...")
    notificar_error("Transcripción", "CUDA out of memory")
"""

import html
import json
import os
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Carga de variables de entorno
# ---------------------------------------------------------------------------
# Intentar cargar .env automáticamente si python-dotenv está disponible.
try:
    from dotenv import load_dotenv as _load_dotenv
    _load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=False)
except ImportError:
    # Sin python-dotenv las variables deben estar ya en el entorno del proceso
    pass


def _token() -> str:
    return os.getenv("TELEGRAM_BOT_TOKEN", "").strip()


def _chat_id() -> str:
    return os.getenv("TELEGRAM_CHAT_ID", "").strip()


def _credenciales_ok() -> bool:
    return bool(_token()) and bool(_chat_id())


def telegram_configurado() -> bool:
    """Comprueba si el bot y chat id de Telegram están configurados."""
    return _credenciales_ok()


# ---------------------------------------------------------------------------
# Función base de envío
# ---------------------------------------------------------------------------

def enviar_mensaje(texto: str) -> bool:
    """Envía un mensaje de texto al chat de Telegram configurado.

    Parámetros
    ----------
    texto:
        Contenido del mensaje. Acepta etiquetas HTML básicas
        (<b>, <i>, <code>, <pre>).

    Devuelve
    --------
    bool
        True si la API respondió con ok=true, False en cualquier otro caso.
    """
    if not _credenciales_ok():
        print(
            "[NOTIFICADOR] TELEGRAM_BOT_TOKEN o TELEGRAM_CHAT_ID no configurados. "
            "Las notificaciones están deshabilitadas.",
            flush=True,
        )
        return False

    url = f"https://api.telegram.org/bot{_token()}/sendMessage"
    payload = json.dumps({
        "chat_id": _chat_id(),
        "text": texto,
        "parse_mode": "HTML",
    }).encode("utf-8")

    # Intentar primero con requests (ya puede estar en el entorno), luego
    # caer a urllib para no añadir dependencias obligatorias.
    try:
        import requests as _req
        resp = _req.post(url, data=payload, headers={"Content-Type": "application/json"}, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        return bool(data.get("ok"))
    except ImportError:
        pass  # requests no disponible → usar urllib
    except Exception as exc:
        print(f"[NOTIFICADOR] Error al enviar notificación (requests): {exc}", flush=True)
        return False

    # Fallback: urllib.request (stdlib)
    try:
        import urllib.request as _urllib_req
        req = _urllib_req.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with _urllib_req.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return bool(data.get("ok"))
    except Exception as exc:
        print(f"[NOTIFICADOR] Error al enviar notificación (urllib): {exc}", flush=True)
        return False


# ---------------------------------------------------------------------------
# Funciones auxiliares con mensajes formateados
# ---------------------------------------------------------------------------

def notificar_clase_completada(
    nombre_clase: str,
    duracion: str,
    url_notion: Optional[str] = None,
) -> bool:
    """Notifica que una clase individual ha sido procesada con éxito.

    Parámetros
    ----------
    nombre_clase:
        Nombre o tema de la clase procesada.
    duracion:
        Cadena de texto con la duración del procesamiento (ej. "23m 14s").
    url_notion:
        URL de la página exportada a Notion, opcional.
    """
    nombre_legible = nombre_clase.replace("_", " ")
    nombre_escapado = html.escape(nombre_legible)
    lineas = [
        "✅ <b>LectureFlow — Clase completada</b>",
        "",
        f"📖 <b>Clase:</b> {nombre_escapado}",
        f"⏱ <b>Duración:</b> {html.escape(str(duracion))}",
    ]
    if url_notion and url_notion.strip():
        lineas.append(f'🔗 <a href="{html.escape(url_notion.strip(), quote=True)}">Abrir en Notion</a>')

    return enviar_mensaje("\n".join(lineas))


def notificar_lote_completado(
    total: int,
    exitosos: int,
    errores: int,
) -> bool:
    """Notifica el resumen final de un procesamiento por lotes.

    Parámetros
    ----------
    total:
        Número total de trabajos procesados en este ciclo.
    exitosos:
        Número de trabajos que finalizaron sin error.
    errores:
        Número de trabajos que terminaron con error.
    """
    icono = "✅" if errores == 0 else "⚠️"
    lineas = [
        f"{icono} <b>LectureFlow — Cola de lotes finalizada</b>",
        "",
        f"📦 <b>Total procesados:</b> {total}",
        f"✔ <b>Exitosos:</b> {exitosos}",
        f"✖ <b>Con errores:</b> {errores}",
    ]
    if errores > 0:
        lineas.append("\nRevisa la interfaz para reintentar los trabajos fallidos.")

    return enviar_mensaje("\n".join(lineas))


def notificar_error(
    contexto: str,
    detalle: str,
) -> bool:
    """Notifica un error crítico no recuperado durante el procesamiento.

    Parámetros
    ----------
    contexto:
        Descripción breve del paso donde ocurrió el error
        (ej. "Transcripción", "Síntesis LLM").
    detalle:
        Mensaje de error o traza abreviada.
    """
    # Truncar el detalle para no saturar el mensaje
    detalle_corto = detalle[:300] + ("…" if len(detalle) > 300 else "")
    lineas = [
        "❌ <b>LectureFlow — Error crítico</b>",
        "",
        f"⚙️ <b>Contexto:</b> {contexto}",
        f"<pre>{detalle_corto}</pre>",
    ]
    return enviar_mensaje("\n".join(lineas))
