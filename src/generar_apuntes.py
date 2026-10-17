"""
Generador de GUÍAS DE ESTUDIO DAW a partir de transcripciones (Qwen 2.5 7B vía Ollama).

Arquitectura en dos pasadas:
  1. EXTRACCIÓN (LLM, por fragmento, salida JSON validada con evidencia).
     El modelo solo extrae hechos que el texto dice; no redacta el apunte.
  2. COMPOSICIÓN (código Python, sin LLM): agrupa, deduplica, ordena y rellena
     una plantilla FIJA. Los timestamps van a un índice aparte.

Antes de extraer, la fuente se prepara por código:
  - Detecta si es una CLASE grabada o un DOCUMENTO leído por lector de pantalla
    y limpia sus etiquetas ("Empezar nivel del encabezado...", "Elemento 1 de 3").
  - Filtra alucinaciones de Whisper (líneas vacías/repetidas, frases de cierre).
  - Corta todo lo posterior a la despedida del docente (charla de alumnos).
  - Corrige términos mal transcritos con un glosario controlado.

Mantiene: backup preventivo, descarga determinista de VRAM (keep_alive), banco de
preguntas (generar_preguntas_clase) y la API pública previa.
"""
from __future__ import annotations

import difflib
import hashlib
import json
import os
import random
import re
import shutil
import sys
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import ollama

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

MODEL = "qwen2.5:7b"
MODELO_LLM = MODEL

# ---------------------------------------------------------------------------
# 0. Configuración
# ---------------------------------------------------------------------------
CHARS_POR_TOKEN_APROX = 3.5  # Estimación conservadora para texto en español
CTX_HEADROOM = 0.75          # Usar máximo el 75 % del contexto disponible

OPTIONS_EXTRACCION = {"temperature": 0.1, "num_ctx": 16384, "num_predict": 3072}
OPTIONS_AUTOEVAL = {"temperature": 0.2, "num_ctx": 8192, "num_predict": 2048}
OPTIONS_QUIZ = {"temperature": 0.3, "num_ctx": 12288, "num_predict": 2048}

# Cabecera "Registro de clase": ponla a False si tu exportador a Notion ya
# añade su propio encabezado (si no, el apunte sale con la cabecera duplicada).
CABECERA_REGISTRO = True
# Título H1 al inicio del apunte (por defecto no, para conservar la salida previa).
INCLUIR_H1 = False
# Auditoría con LLM (la determinista siempre se ejecuta). Actívala con =1.
AUDITORIA_LLM = os.environ.get("LECTUREFLOW_AUDITORIA_LLM", "0") == "1"

# Solo se conservan URLs de estos dominios; las demás se sustituyen y se avisa.
DOMINIOS_PERMITIDOS = (
    "netbeans.apache.org", "apache.org", "github.com", "nodejs.org",
    "code.visualstudio.com", "oracle.com", "openjdk.org", "adoptium.net",
    "developer.mozilla.org",
)

SECCIONES = [
    ("1", "Lo Esencial"),
    ("2", "Conceptos Clave"),
    ("3", "Procedimientos Paso a Paso"),
    ("4", "Errores Comunes y Solución"),
    ("5", "Comparativas"),
    ("6", "Glosario"),
    ("7", "Autoevaluación"),
    ("8", "Pendiente de Revisar"),
]

MARCADOR_SECCION = "=== SECCIÓN:"
MARCA_ENLACE_ROTO = "[ENLACE NO TRANSCRITO CORRECTAMENTE]"

# Esquema JSON estricto para extracción de preguntas de evaluación activa
SCHEMA_PREGUNTAS: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "preguntas": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "tipo": {
                        "type": "string",
                        "description": "Tipo de pregunta: conceptual, codigo o analisis",
                    },
                    "pregunta": {
                        "type": "string",
                        "description": "Enunciado riguroso de la pregunta de evaluación",
                    },
                    "codigo": {
                        "type": "string",
                        "description": "Fragmento de código relevante o cadena vacía si no aplica",
                    },
                    "opciones": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Exactamente 4 opciones de respuesta posibles",
                    },
                    "correcta": {
                        "type": "integer",
                        "description": "Índice (0 a 3) de la opción correcta en la lista 'opciones'",
                    },
                    "explicacion": {
                        "type": "string",
                        "description": "Justificación pedagógica detallada de la respuesta correcta",
                    },
                },
                "required": ["tipo", "pregunta", "codigo", "opciones", "correcta", "explicacion"],
            },
        }
    },
    "required": ["preguntas"],
}


def _obj(props: Dict[str, Any]) -> Dict[str, Any]:
    return {"type": "object", "properties": props, "required": list(props)}


def _arr(item: Dict[str, Any]) -> Dict[str, Any]:
    return {"type": "array", "items": item}


_STR = {"type": "string"}

CATEGORIAS = ("ideas_clave", "conceptos", "procedimientos", "errores",
              "comparativas", "ejercicios", "dudas")

SCHEMA_EXTRACCION: Dict[str, Any] = _obj({
    "ideas_clave": _arr(_obj({"texto": _STR, "evidencia": _STR})),
    "conceptos": _arr(_obj({"termino": _STR, "definicion": _STR, "ejemplo": _STR, "evidencia": _STR})),
    "procedimientos": _arr(_obj({"titulo": _STR, "pasos": _arr(_STR), "evidencia": _STR})),
    "errores": _arr(_obj({"sintoma": _STR, "causa": _STR, "solucion": _STR, "evidencia": _STR})),
    "comparativas": _arr(_obj({"titulo": _STR, "columnas": _arr(_STR),
                               "filas": _arr(_arr(_STR)), "evidencia": _STR})),
    "ejercicios": _arr(_obj({"enunciado": _STR, "evidencia": _STR})),
    "dudas": _arr(_obj({"texto": _STR, "evidencia": _STR})),
})

SCHEMA_AUTOEVAL: Dict[str, Any] = _obj({
    "preguntas": _arr(_obj({
        "tipo": {"type": "string", "enum": ["recuerdo", "aplicacion"]},
        "pregunta": _STR, "respuesta": _STR, "explicacion": _STR,
    }))
})

SYSTEM_PROMPT = (
    "Actúa como un tutor académico de informática para ciclos DAM/DAW. "
    "Eres riguroso: no afirmas nada que no esté respaldado por el material."
)

SYSTEM_PROMPT_EXTRACCION = (
    "Eres un ayudante de estudio para un alumno de DAW. Extraes hechos de material "
    "de clase con rigor: solo lo que el texto dice, sin inventar ni completar con "
    "conocimiento propio. Respondes únicamente con JSON válido."
)


class TruncationError(Exception):
    """El modelo cortó la generación por agotar tokens/contexto."""


# ---------------------------------------------------------------------------
# 1. Utilidades de texto
# ---------------------------------------------------------------------------
RE_TS_LINEA = re.compile(r"^\[(\d{1,2}:\d{2}:\d{2})\]\s?(.*)$")
RE_TS_ANY = re.compile(r"(\d{1,2}):(\d{2}):(\d{2})")
RE_TS_CUERPO = re.compile(
    r"[ \t]*(?:🕒\s*)?\[\d{1,2}:\d{2}:\d{2}(?:\s*[-–]\s*\d{1,2}:\d{2}:\d{2})?\]"
)


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFD", str(s).lower())
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


def _claves_palabras(texto: str) -> set:
    """Claves (prefijo de 5 letras) de las palabras de contenido; tolera plurales/conjugaciones."""
    return {w[:5] for w in re.findall(r"[a-z0-9]{5,}", _norm(texto))}


def _fundamentado(texto: str, base: set, umbral: float = 0.5) -> bool:
    """True si al menos `umbral` de las palabras de contenido de `texto` aparecen en la fuente."""
    claves = _claves_palabras(texto)
    if len(claves) < 3:
        return True  # muy corto para juzgar (p. ej. un comando o un valor)
    return len(claves & base) / len(claves) >= umbral


def _s(x: Any) -> str:
    return re.sub(r"\s+", " ", str(x if x is not None else "")).strip()


def _split_ts(linea: str) -> Tuple[Optional[str], str]:
    m = RE_TS_LINEA.match(linea.rstrip("\r"))
    if m:
        return m.group(1), m.group(2)
    return None, linea


def _seg(ts: Optional[str]) -> Optional[int]:
    if not ts:
        return None
    h, m, s = ts.split(":")
    return int(h) * 3600 + int(m) * 60 + int(s)


def _fmt_ts(segundos: int) -> str:
    return f"{segundos // 3600:02d}:{(segundos % 3600) // 60:02d}:{segundos % 60:02d}"


def _rango_ts(fragmento: str) -> Optional[Tuple[int, int]]:
    segs = [_seg(_split_ts(l)[0]) for l in fragmento.splitlines()]
    segs = [s for s in segs if s is not None]
    return (min(segs), max(segs)) if segs else None


# ---------------------------------------------------------------------------
# 2. Glosario controlado (corrige términos mal transcritos por código)
# ---------------------------------------------------------------------------
GLOSARIO_BASE: Dict[str, Dict[str, Any]] = {
    "IDE": {"definicion": "Entorno de desarrollo integrado: programa que reúne editor, compilador, depurador y otras herramientas para programar.",
            "alias": {"SIDES": "IDEs"}},
    "NetBeans": {"definicion": "IDE de código abierto de Apache para crear, compilar, ejecutar y depurar proyectos Java.",
                 "alias": {"Apache Nervians": "Apache NetBeans", "Nervians": "NetBeans", "el Beans": "NetBeans"}},
    "JDK": {"definicion": "Java Development Kit: conjunto de herramientas para desarrollar en Java (incluye el compilador javac y la JVM).", "alias": {}},
    "JVM": {"definicion": "Java Virtual Machine: máquina virtual que recibe el bytecode y lo ejecuta en la CPU (interpretándolo o compilándolo JIT).", "alias": {}},
    "bytecode": {"definicion": "Código intermedio (archivos .class) que genera el compilador de Java y que ejecuta la JVM.",
                 "alias": {"Vitecode": "bytecode"}},
    "Javadoc": {"definicion": "Herramienta y formato de comentarios /** ... */ para documentar código Java.",
                "alias": {"Java Doc": "Javadoc"}},
    "Swagger": {"definicion": "Herramienta para documentar y probar APIs.", "alias": {"swag": "Swagger"}},
    "UML": {"definicion": "Lenguaje unificado de modelado: notación estándar para diagramas (clases, etc.).",
            "alias": {"WML": "UML"}},
    "npm run dev": {"definicion": "Comando que arranca un proyecto Node en modo desarrollo.",
                    "alias": {"npm run def": "npm run dev"}},
    "main.jsx": {"definicion": "Fichero de entrada de un proyecto React.", "alias": {"MainJSX": "main.jsx"}},
    "app.jsx": {"definicion": "Componente principal de un proyecto React.", "alias": {"AppJSX": "app.jsx"}},
    "React.js": {"definicion": "Biblioteca de JavaScript para construir interfaces de usuario.",
                 "alias": {"READJS": "React.js"}},
    "DAW": {"definicion": "Ciclo formativo de Desarrollo de Aplicaciones Web.", "alias": {"DAM y DAO": "DAM y DAW"}},
    "SMR": {"definicion": "Ciclo formativo de grado medio Sistemas Microinformáticos y Redes.", "alias": {}},
    "localhost:5173": {"definicion": "Dirección local en la que Vite sirve el proyecto en desarrollo.",
                       "alias": {"51 73": "5173"}},
}


def _normalizar_glosario(bruto: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    res: Dict[str, Dict[str, Any]] = {}
    for termino, datos in bruto.items():
        if isinstance(datos, str):
            datos = {"definicion": datos, "alias": {}}
        alias = datos.get("alias", {})
        if isinstance(alias, list):
            alias = {a: termino for a in alias}
        res[termino] = {"definicion": _s(datos.get("definicion", "")), "alias": dict(alias)}
    return res


def cargar_glosario(ruta: Optional[Union[str, Path]] = None) -> Dict[str, Dict[str, Any]]:
    """GLOSARIO_BASE + config/glosario.json (si existe). El JSON puede ser
    {"termino": {"definicion": "...", "alias": {"mal": "bien"} | ["mal", ...]}}."""
    glosario = _normalizar_glosario(GLOSARIO_BASE)
    candidatas: List[Optional[Union[str, Path]]] = [
        ruta,
        os.environ.get("LECTUREFLOW_GLOSARIO"),
        Path.cwd() / "config" / "glosario.json",
        Path(__file__).resolve().parent.parent / "config" / "glosario.json",
        Path(__file__).resolve().parent / "config" / "glosario.json",
    ]
    for c in candidatas:
        if c and Path(c).is_file():
            try:
                with open(c, "r", encoding="utf-8") as f:
                    bruto = json.load(f)
                bruto = bruto.get("terminos", bruto) if isinstance(bruto, dict) else {}
                glosario.update(_normalizar_glosario(bruto))
            except (OSError, ValueError) as exc:
                print(f"[AVISO] No se pudo leer el glosario '{c}': {exc}")
            break
    return glosario


def _patron_literal(texto: str, plural: bool = False) -> "re.Pattern[str]":
    partes = [re.escape(p) for p in texto.split()]
    cuerpo = r"\s+".join(partes) + (r"s?" if plural else "")
    return re.compile(r"(?<!\w)" + cuerpo + r"(?!\w)", re.IGNORECASE)


def aplicar_glosario(texto: str, glosario: Optional[Dict[str, Dict[str, Any]]] = None) -> Tuple[str, int]:
    """Sustituye alias mal transcritos por su forma correcta. Devuelve (texto, nº de correcciones)."""
    glosario = glosario if glosario is not None else cargar_glosario()
    pares: List[Tuple[str, str]] = []
    for datos in glosario.values():
        pares.extend(datos.get("alias", {}).items())
    pares.sort(key=lambda p: len(p[0]), reverse=True)  # primero los alias más largos
    total = 0
    for alias, correcto in pares:
        texto, n = _patron_literal(alias).subn(lambda _m, c=correcto: c, texto)
        total += n
    return texto, total


def terminos_presentes(texto: str, glosario: Optional[Dict[str, Dict[str, Any]]] = None) -> Dict[str, str]:
    """Términos del glosario que aparecen en el texto (ya corregido) -> definición."""
    glosario = glosario if glosario is not None else cargar_glosario()
    return {t: d["definicion"] for t, d in glosario.items()
            if d.get("definicion") and _patron_literal(t, plural=True).search(texto)}


# ---------------------------------------------------------------------------
# 3. Preparación de la fuente (tipo, limpieza, antialucinación, despedida)
# ---------------------------------------------------------------------------
RE_ETIQUETA_DOC = re.compile(
    r"Empezar (?:nivel del encabezado|texto del p[aá]rrafo|lista)|Elemento \d+ de \d+|Imagen sin descripci[oó]n",
    re.IGNORECASE,
)
RE_IMG = re.compile(r"^Imagen sin descripci[oó]n alternativa\.?$", re.IGNORECASE)
RE_ENC = re.compile(r"^Empezar nivel del encabezado\s*(\d)\s*[,.]?\s*(.*)$", re.IGNORECASE)
RE_PARR = re.compile(r"^Empezar texto del p[aá]rrafo\s*[,.]?\s*", re.IGNORECASE)
RE_LISTA = re.compile(r"^Empezar lista[^.]*\.\s*", re.IGNORECASE)
RE_ELEM_INC = re.compile(r"^Elemento\s+\d+\s+de\s+un incluido[^.]*\.\s*", re.IGNORECASE)
RE_ELEM = re.compile(r"^Elemento\s+\d+\s+de\s+\d+\s*[,.]?\s*", re.IGNORECASE)
RE_ENLACE = re.compile(r"empezar enlace,?.*$", re.IGNORECASE)

RE_CIERRE_ALUC = re.compile(
    r"subt[ií]tulos?\s+(?:realizados|por|de)|amara\.org|suscr[ií]bete|gracias por ver", re.IGNORECASE)

RE_DESPEDIDA = re.compile(
    r"\bos dejo\b|\bque teng[aá]is\b|\badi[oó]s\b|\bhasta (?:luego|el (?:lunes|martes|mi[eé]rcoles|jueves|viernes)|ma[ñn]ana|pronto)\b"
    r"|\bnos vemos\b|\bbuena(?:s)? (?:tarde|noche)s?\b|\bque vaya bien\b",
    re.IGNORECASE,
)


def detectar_tipo_fuente(texto: str) -> str:
    """'documento' si parece un lector de pantalla leyendo un documento; si no, 'clase'."""
    lineas = [l for l in texto.splitlines() if l.strip()]
    if not lineas:
        return "clase"
    hits = sum(1 for l in lineas if RE_ETIQUETA_DOC.search(l))
    return "documento" if hits >= 6 and hits / len(lineas) >= 0.01 else "clase"


def limpiar_fuente_documento(texto: str) -> Tuple[str, int, List[str]]:
    """Quita las etiquetas del lector de pantalla y reconstruye la estructura.
    Devuelve (texto_limpio, nº de imágenes sin descripción, títulos de sección)."""
    salida: List[str] = []
    secciones: List[str] = []
    imagenes = 0
    pendiente: Optional[str] = None  # encabezado cuyo texto llega en la línea siguiente
    hay_pendiente = False

    def emitir(ts: Optional[str], contenido: str) -> None:
        salida.append(f"[{ts}] {contenido}" if ts else contenido)

    for linea in texto.splitlines():
        ts, txt = _split_ts(linea)
        txt = txt.strip()
        if not txt:
            continue
        if RE_IMG.match(txt):
            imagenes += 1
            continue
        m = RE_ENC.match(txt)
        if m:
            resto = m.group(2).strip(" .,")
            if resto:
                secciones.append(resto)
                emitir(ts, f"{MARCADOR_SECCION} {resto} ===")
                hay_pendiente = False
            else:
                hay_pendiente, pendiente = True, ts
            continue
        if hay_pendiente:
            titulo = txt.strip(" .,")
            secciones.append(titulo)
            emitir(ts or pendiente, f"{MARCADOR_SECCION} {titulo} ===")
            hay_pendiente = False
            continue
        txt = RE_PARR.sub("", txt)
        txt = RE_LISTA.sub("", txt)
        txt = RE_ELEM_INC.sub("", txt)
        es_elemento = False
        if RE_ELEM.match(txt):
            txt = RE_ELEM.sub("", txt)
            es_elemento = True
        txt = RE_ENLACE.sub(MARCA_ENLACE_ROTO, txt).strip()
        if not txt:
            continue
        emitir(ts, ("- " if es_elemento else "") + txt)
    return "\n".join(salida), imagenes, secciones


def filtrar_alucinaciones(texto: str, max_repeticiones: int = 3) -> Tuple[str, int]:
    """Elimina segmentos vacíos, repeticiones consecutivas (>max) y frases de cierre típicas de Whisper."""
    salida: List[str] = []
    previo: Optional[str] = None
    rep = 0
    eliminadas = 0
    for linea in texto.splitlines():
        ts, txt = _split_ts(linea)
        t = txt.strip()
        if not t:
            if ts is not None:
                eliminadas += 1
                continue
            salida.append(linea)
            continue
        if RE_CIERRE_ALUC.search(t):
            eliminadas += 1
            continue
        clave = _norm(t)
        if clave == previo:
            rep += 1
        else:
            previo, rep = clave, 1
        if rep > max_repeticiones:
            eliminadas += 1
            continue
        salida.append(linea)
    return "\n".join(salida), eliminadas


def cortar_por_despedida(texto: str) -> Tuple[str, Optional[str]]:
    """Descarta lo posterior a la despedida del docente (charla de alumnos, etc.).
    Conservador: solo busca en el último 40 % de la grabación, exige varias
    marcas de despedida seguidas (racimo) (o una en el último 15 %) y nunca descarta más de la mitad."""
    lineas = texto.splitlines()
    parsed = [_seg(_split_ts(l)[0]) for l in lineas]
    segs = [s for s in parsed if s is not None]
    if len(segs) < 10:
        return texto, None
    ini, fin = min(segs), max(segs)
    span = fin - ini
    if span <= 0:
        return texto, None
    umbral = ini + 0.6 * span
    hits = [i for i, l in enumerate(lineas)
            if parsed[i] is not None and parsed[i] >= umbral and RE_DESPEDIDA.search(_split_ts(l)[1])]
    if not hits:
        print("[AVISO] No se detectó despedida del docente: se procesa toda la grabación.")
        return texto, None
    s0 = parsed[hits[0]]
    ventana = [hits[0]]  # racimo de marcas de despedida (cada una a <=30 s de la anterior)
    for i in hits[1:]:
        if parsed[i] - parsed[ventana[-1]] <= 30:
            ventana.append(i)
        else:
            break
    if len(ventana) < 2 and s0 < ini + 0.85 * span:
        print("[AVISO] Despedida dudosa (una sola marca): no se corta.")
        return texto, None
    corte = ventana[-1] + 1
    if corte >= len(lineas):
        return texto, None
    if corte / len(lineas) < 0.5:
        print("[AVISO] El corte por despedida descartaría más de la mitad del texto: no se aplica.")
        return texto, None
    ts_corte = _fmt_ts(parsed[ventana[-1]])
    print(f"[CORTE] Despedida detectada a las {ts_corte}: se descartan {len(lineas) - corte} líneas posteriores.")
    return "\n".join(lineas[:corte]), ts_corte


def preparar_fuente(texto: str, glosario: Optional[Dict[str, Dict[str, Any]]] = None) -> Dict[str, Any]:
    """Pipeline determinista previo al LLM. Devuelve el texto limpio y metadatos de lo que se hizo."""
    glosario = glosario if glosario is not None else cargar_glosario()
    info: Dict[str, Any] = {"tipo": detectar_tipo_fuente(texto), "imagenes": 0, "secciones": [],
                            "lineas_filtradas": 0, "corte": None, "correcciones": 0}
    if info["tipo"] == "documento":
        texto, info["imagenes"], info["secciones"] = limpiar_fuente_documento(texto)
    texto, info["lineas_filtradas"] = filtrar_alucinaciones(texto)
    if info["tipo"] == "clase":
        texto, info["corte"] = cortar_por_despedida(texto)
    texto, info["correcciones"] = aplicar_glosario(texto, glosario)
    info["texto"] = texto
    return info


def dividir_transcripcion(texto: str, max_chars: int = 9000, marcador_seccion: Optional[str] = None) -> List[str]:
    """Trocea por líneas hasta ~max_chars. Con marcador_seccion prefiere cortar antes de un apartado."""
    bloques: List[str] = []
    actual: List[str] = []
    tam = 0
    for linea in texto.splitlines():
        l = len(linea) + 1
        en_seccion = bool(marcador_seccion and marcador_seccion in linea)
        if actual and (tam + l > max_chars or (en_seccion and tam > 0.6 * max_chars)):
            bloques.append("\n".join(actual))
            actual, tam = [], 0
        actual.append(linea)
        tam += l
    if actual:
        bloques.append("\n".join(actual))
    return bloques


# ---------------------------------------------------------------------------
# 4. Llamadas a Ollama
# ---------------------------------------------------------------------------
def _leer_respuesta(respuesta: Any) -> Tuple[str, Optional[str]]:
    done_reason = respuesta.get("done_reason") if isinstance(respuesta, dict) else getattr(respuesta, "done_reason", None)
    mensaje = respuesta.get("message") if isinstance(respuesta, dict) else getattr(respuesta, "message", None)
    if mensaje is None:
        raise RuntimeError("La respuesta del modelo no contiene la estructura esperada ('message' no encontrado). "
                           "Posible fallo de conexión o caída de Ollama.")
    contenido = mensaje.get("content") if isinstance(mensaje, dict) else getattr(mensaje, "content", None)
    if not contenido or not contenido.strip():
        raise RuntimeError("El modelo devolvió una respuesta vacía o nula. "
                           "Posible truncamiento severo o fallo interno en la inferencia.")
    return contenido, done_reason


def llamar_modelo_seguro(prompt_usuario: str, options: dict, keep_alive: Union[str, int] = "5m",
                         system: str = SYSTEM_PROMPT) -> str:
    print("  [Síntesis] Procesando con {} en local...".format(MODEL), end="", flush=True)
    respuesta = ollama.chat(
        model=MODEL, options=options, keep_alive=keep_alive,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": prompt_usuario}],
    )
    print(" completado.")
    contenido, done_reason = _leer_respuesta(respuesta)
    if done_reason == "length":
        raise TruncationError("La generación fue cortada abruptamente al agotarse el límite de tokens/contexto.")
    return contenido


def llamar_modelo_json(prompt_usuario: str, schema: Dict[str, Any], options: dict,
                       keep_alive: Union[str, int] = "5m", system: str = SYSTEM_PROMPT_EXTRACCION) -> Any:
    """Llamada con salida estructurada (JSON Schema en 'format'). Lanza ValueError si el JSON no es válido."""
    print("  [Extracción] Procesando con {} en local...".format(MODEL), end="", flush=True)
    respuesta = ollama.chat(
        model=MODEL, format=schema, options=options, keep_alive=keep_alive,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": prompt_usuario}],
    )
    print(" completado.")
    contenido, done_reason = _leer_respuesta(respuesta)
    if done_reason == "length":
        raise TruncationError("La salida JSON se cortó por límite de tokens/contexto.")
    limpio = re.sub(r"^```(?:json)?\s*|\s*```\$", "", contenido.strip())
    return json.loads(limpio)


def descargar_modelo_ollama(modelo: str = MODEL) -> bool:
    """Solicita a Ollama descargar inmediatamente el modelo de la VRAM
    enviando keep_alive=0. Desaloja los ~6.5 GB de VRAM evitando colisiones OOM con Whisper.
    """
    print(f"\n[VRAM] Desalojando modelo '{modelo}' de la memoria...", end="", flush=True)
    try:
        ollama.generate(model=modelo, prompt="", keep_alive=0)
        print(" descargado con éxito.", flush=True)
        return True
    except Exception as exc:
        try:
            import urllib.request
            req = urllib.request.Request(
                "http://localhost:11434/api/generate",
                data=json.dumps({"model": modelo, "keep_alive": 0}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                if resp.status == 200:
                    print(" descargado con éxito (HTTP fallback).", flush=True)
                    return True
        except Exception:
            pass
        print(f" no se pudo desalojar automáticamente: {exc}", flush=True)
        return False


# ---------------------------------------------------------------------------
# 5. Pasada 1: extracción de hechos (prompt + validación)
# ---------------------------------------------------------------------------
DESCRIPCION_FUENTE = {
    "clase": ("TRANSCRIPCIÓN de una clase grabada. Habla el docente; puede haber intervenciones de alumnos "
              "y charla informal."),
    "documento": ("DOCUMENTO oficial de la unidad leído por un lector de pantalla. Todo el texto es material "
                  "didáctico del docente. Las líneas '=== SECCIÓN: X ===' marcan los apartados. "
                  "Las imágenes (tablas, código) no están en el texto."),
}


def construir_prompt_extraccion(fragmento: str, num: int, total: int, tipo_fuente: str,
                                glosario_relevante: Dict[str, str]) -> str:
    partes: List[str] = [
        f"FUENTE: {DESCRIPCION_FUENTE.get(tipo_fuente, DESCRIPCION_FUENTE['clase'])}",
        f"Este es el fragmento {num} de {total}. Cada línea empieza con su timestamp [HH:MM:SS].",
    ]
    if glosario_relevante:
        partes.append("GLOSARIO (términos correctos presentes en el fragmento):")
        partes.extend(f"- {t}: {d}" for t, d in glosario_relevante.items())
    reglas = [
        "Extrae SOLO lo que el texto explica o confirma. Si algo no está en el fragmento, no lo incluyas.",
        "NO uses conocimiento propio para completar, ampliar ni corregir. Nada de ejemplos, errores ni diferencias "
        "que el texto no mencione expresamente.",
        "Definiciones: copia o parafrasea de cerca lo que dice el texto. Si un término no se explica en el "
        "fragmento ni en el glosario, no lo definas.",
        "'evidencia': copia EXACTAMENTE un timestamp [HH:MM:SS] de una línea del fragmento donde aparece el hecho.",
        "'conceptos': un término por entrada, definición de una frase. 'ejemplo' solo si el texto lo da; si no, \"\".",
        "'procedimientos': pasos reproducibles en orden (instalar, configurar, ejecutar). Comandos y código entre "
        "comillas invertidas (`así`).",
        "'errores': SOLO si el texto menciona un fallo, una advertencia o un problema y su solución. Si no, lista vacía.",
        "'comparativas': solo cuando el texto contrasta dos o más cosas (p. ej. dos métodos, dos tipos). "
        "'columnas' (≥2) y 'filas' con el mismo número de celdas que columnas.",
        "'ideas_clave': como máximo 2 frases con lo más importante de este fragmento.",
        "'ejercicios': actividades o ejercicios propuestos, con el enunciado tal como aparece. No inventes ejercicios.",
        "'dudas': contradicciones, términos que no se entienden, fragmentos confusos o enlaces ilegibles.",
        "Si hay una contradicción, quédate con la aclaración posterior del docente o envíala a 'dudas'.",
        "No incluyas URLs. No uses nombres de personas.",
        "Si el fragmento no tiene contenido didáctico, devuelve todas las listas vacías.",
    ]
    if tipo_fuente == "clase":
        reglas.append("Ignora saludos, logística, charla informal e intervenciones de alumnos, salvo que el "
                      "docente las corrija o confirme: una respuesta de alumno nunca es un hecho.")
    else:
        reglas.append("Extrae TODO el contenido didáctico de cada apartado, sin omitir listas de reglas, tipos, "
                      "operadores ni actividades.")
    partes.append("REGLAS:")
    partes.extend(f"{i}. {r}" for i, r in enumerate(reglas, 1))
    partes.append("Responde únicamente con JSON conforme al esquema. Listas vacías si no hay contenido.")
    partes.append("---\nFRAGMENTO:\n" + fragmento)
    return "\n".join(partes)


def _normalizar_evidencia(ev: Any, rango: Optional[Tuple[int, int]]) -> Optional[str]:
    """Con timestamps en la fuente, la evidencia es obligatoria y debe caer dentro del fragmento.
    Devuelve el texto normalizado, '' (sin timestamps en la fuente) o None (inválida)."""
    tss = [(int(h) * 3600 + int(m) * 60 + int(s), f"{int(h):02d}:{m}:{s}") for h, m, s in RE_TS_ANY.findall(str(ev or ""))]
    if rango is None:
        return tss[0][1] if tss else ""
    validos = [t for t in tss if rango[0] - 5 <= t[0] <= rango[1] + 5]
    if not validos:
        return None
    return validos[0][1] if len(validos) == 1 else f"{validos[0][1]}-{validos[-1][1]}"


def validar_extraccion(datos: Any, fragmento: str, base_extra: str = "") -> Tuple[Dict[str, list], int]:
    """Valida y filtra la salida del LLM. Descarta hechos sin evidencia válida y manda a 'dudas'
    los que no se pueden contrastar con la fuente. Devuelve (hechos, nº de descartados)."""
    if not isinstance(datos, dict):
        raise ValueError("La extracción no es un objeto JSON.")
    rango = _rango_ts(fragmento)
    base = _claves_palabras(fragmento + " " + base_extra)
    out: Dict[str, list] = {c: [] for c in CATEGORIAS}
    descartes = 0

    def lista(cat: str) -> list:
        v = datos.get(cat, [])
        return v if isinstance(v, list) else []

    def duda(texto: str, ev: str) -> None:
        out["dudas"].append({"texto": texto, "evidencia": ev})

    for it in lista("ideas_clave"):
        if not isinstance(it, dict):
            continue
        texto, ev = _s(it.get("texto")), _normalizar_evidencia(it.get("evidencia"), rango)
        if not texto or ev is None or not _fundamentado(texto, base, 0.4):
            descartes += 1
            continue
        out["ideas_clave"].append({"texto": texto, "evidencia": ev})

    for it in lista("conceptos"):
        if not isinstance(it, dict):
            continue
        termino, definicion = _s(it.get("termino")), _s(it.get("definicion"))
        ev = _normalizar_evidencia(it.get("evidencia"), rango)
        if not termino or not definicion or ev is None:
            descartes += 1
            continue
        if not _fundamentado(definicion, base, 0.5):
            duda(f"No se pudo contrastar con la fuente la definición de «{termino}»; revísala.", ev)
            descartes += 1
            continue
        ejemplo = _s(it.get("ejemplo"))
        if ejemplo and not _fundamentado(ejemplo, base, 0.5):
            ejemplo = ""
        out["conceptos"].append({"termino": termino, "definicion": definicion, "ejemplo": ejemplo, "evidencia": ev})

    for it in lista("procedimientos"):
        if not isinstance(it, dict):
            continue
        titulo = _s(it.get("titulo"))
        pasos_raw = it.get("pasos", [])
        pasos = [_s(p) for p in pasos_raw if _s(p)] if isinstance(pasos_raw, list) else []
        ev = _normalizar_evidencia(it.get("evidencia"), rango)
        if not titulo or not pasos or ev is None:
            descartes += 1
            continue
        if not _fundamentado(titulo + " " + " ".join(pasos), base, 0.4):
            duda(f"No se pudo contrastar con la fuente el procedimiento «{titulo}»; revísala.", ev)
            descartes += 1
            continue
        out["procedimientos"].append({"titulo": titulo, "pasos": pasos, "evidencia": ev})

    for it in lista("errores"):
        if not isinstance(it, dict):
            continue
        sintoma, causa, solucion = _s(it.get("sintoma")), _s(it.get("causa")), _s(it.get("solucion"))
        ev = _normalizar_evidencia(it.get("evidencia"), rango)
        if not sintoma or not solucion or ev is None:
            descartes += 1
            continue
        if not _fundamentado(f"{sintoma} {causa} {solucion}", base, 0.45):
            duda(f"No se pudo contrastar con la fuente el error «{sintoma}»; revísala.", ev)
            descartes += 1
            continue
        out["errores"].append({"sintoma": sintoma, "causa": causa or "No indicada en la fuente",
                               "solucion": solucion, "evidencia": ev})

    for it in lista("comparativas"):
        if not isinstance(it, dict):
            continue
        titulo = _s(it.get("titulo"))
        cols_raw = it.get("columnas", [])
        columnas = [_s(c) for c in cols_raw] if isinstance(cols_raw, list) else []
        filas = []
        for fila in (it.get("filas", []) if isinstance(it.get("filas", []), list) else []):
            if isinstance(fila, list) and len(fila) == len(columnas):
                filas.append([_s(c) for c in fila])
        ev = _normalizar_evidencia(it.get("evidencia"), rango)
        if not titulo or len(columnas) < 2 or not filas or ev is None:
            descartes += 1
            continue
        if not _fundamentado(titulo + " " + " ".join(" ".join(f) for f in filas), base, 0.4):
            duda(f"No se pudo contrastar con la fuente la comparativa «{titulo}»; revísala.", ev)
            descartes += 1
            continue
        out["comparativas"].append({"titulo": titulo, "columnas": columnas, "filas": filas, "evidencia": ev})

    for it in lista("ejercicios"):
        if not isinstance(it, dict):
            continue
        enunciado, ev = _s(it.get("enunciado")), _normalizar_evidencia(it.get("evidencia"), rango)
        if not enunciado or ev is None:
            descartes += 1
            continue
        if not _fundamentado(enunciado, base, 0.6):
            duda("Un ejercicio propuesto no coincide con la fuente y se descartó: "
                 f"«{enunciado[:80]}». Revisa el documento original.", ev)
            descartes += 1
            continue
        out["ejercicios"].append({"enunciado": enunciado, "evidencia": ev})

    for it in lista("dudas"):
        if isinstance(it, dict) and _s(it.get("texto")):
            ev = _normalizar_evidencia(it.get("evidencia"), rango)
            duda(_s(it.get("texto")), ev or "")
    return out, descartes


# ---------------------------------------------------------------------------
# 6. Pasada 2: fusión y composición por código (sin LLM)
# ---------------------------------------------------------------------------
def _similares(a: str, b: str, umbral: float = 0.85) -> bool:
    return difflib.SequenceMatcher(None, _norm(a), _norm(b)).ratio() >= umbral


def _dedup(items: List[dict], clave, elegir, umbral: float = 0.85) -> List[dict]:
    res: List[dict] = []
    for it in items:
        for i, previo in enumerate(res):
            if _similares(clave(it), clave(previo), umbral):
                res[i] = elegir(previo, it)
                break
        else:
            res.append(it)
    return res


def _elegir_mejor(campo, previo: dict, nuevo: dict) -> dict:
    ganador = dict(nuevo if campo(nuevo) > campo(previo) else previo)
    ganador["evidencia"] = previo.get("evidencia") or nuevo.get("evidencia", "")
    if "ejemplo" in ganador and not ganador["ejemplo"]:
        ganador["ejemplo"] = previo.get("ejemplo") or nuevo.get("ejemplo", "")
    return ganador


def fusionar_hechos(lista_hechos: List[Dict[str, list]]) -> Dict[str, list]:
    todo: Dict[str, list] = {c: [] for c in CATEGORIAS}
    for h in lista_hechos:
        for c in CATEGORIAS:
            todo[c].extend(h.get(c, []))
    todo["ideas_clave"] = _dedup(todo["ideas_clave"], lambda x: x["texto"], lambda p, n: p, 0.8)
    todo["conceptos"] = _dedup(todo["conceptos"], lambda x: x["termino"],
                               lambda p, n: _elegir_mejor(lambda d: len(d["definicion"]), p, n))
    todo["procedimientos"] = _dedup(todo["procedimientos"], lambda x: x["titulo"],
                                    lambda p, n: _elegir_mejor(lambda d: len(d["pasos"]), p, n))
    todo["errores"] = _dedup(todo["errores"], lambda x: x["sintoma"],
                             lambda p, n: _elegir_mejor(lambda d: len(d["solucion"]), p, n))
    todo["comparativas"] = _dedup(todo["comparativas"], lambda x: x["titulo"],
                                  lambda p, n: _elegir_mejor(lambda d: len(d["filas"]), p, n))
    todo["ejercicios"] = _dedup(todo["ejercicios"], lambda x: x["enunciado"], lambda p, n: p, 0.9)
    todo["dudas"] = _dedup(todo["dudas"], lambda x: x["texto"], lambda p, n: p, 0.9)
    return todo


def _espaciar(items: list, n: int) -> list:
    if len(items) <= n:
        return items
    paso = len(items) / n
    return [items[int(i * paso)] for i in range(n)]


def _celda(x: str) -> str:
    return _s(x).replace("|", "\\|")


def _quitar_numeracion(paso: str) -> str:
    return re.sub(r"^\s*(?:\d+[.)]|[-*•])\s+", "", paso)


def _texto_plano_hechos(hechos: Dict[str, list]) -> str:
    trozos: List[str] = []
    for c in CATEGORIAS:
        for it in hechos.get(c, []):
            for v in it.values():
                trozos.append(" ".join(map(str, v)) if isinstance(v, list) else str(v))
    return " ".join(trozos)


def componer_apuntes(hechos: Dict[str, list], autoeval: List[dict], pendientes: List[str],
                     glosario_lineas: List[str], titulo: Optional[str] = None) -> str:
    """Rellena la plantilla fija. No llama al LLM y no escribe timestamps en el cuerpo."""
    L: List[str] = []
    if titulo:
        L += [f"# {titulo}", ""]

    L += ["## 1. Lo Esencial", ""]
    ideas = _espaciar(hechos["ideas_clave"], 5)
    if ideas:
        L += [f"- {_s(i['texto'])}" for i in ideas]
    elif hechos["conceptos"]:
        L.append("- Conceptos tratados: " + ", ".join(c["termino"] for c in hechos["conceptos"][:8]) + ".")
    else:
        L.append("- Sin ideas clave extraídas.")

    L += ["", "## 2. Conceptos Clave", ""]
    if hechos["conceptos"]:
        for c in hechos["conceptos"]:
            linea = f"- **{c['termino']}**: {c['definicion']}"
            if c.get("ejemplo"):
                linea += f" *Ejemplo:* {c['ejemplo']}"
            L.append(linea)
    else:
        L.append("Sin conceptos extraídos.")

    L += ["", "## 3. Procedimientos Paso a Paso", ""]
    if hechos["procedimientos"]:
        for n, p in enumerate(hechos["procedimientos"], 1):
            L += [f"**{n}. {p['titulo']}**", ""]
            L += [f"{k}. {_quitar_numeracion(paso)}" for k, paso in enumerate(p["pasos"], 1)]
            L.append("")
        L.pop()
    else:
        L.append("Sin procedimientos en la fuente.")

    L += ["", "## 4. Errores Comunes y Solución", ""]
    if hechos["errores"]:
        for e in hechos["errores"]:
            L += [f"- **Síntoma**: {e['sintoma']}",
                  f"  - *Causa*: {e['causa']}",
                  f"  - *Solución*: {e['solucion']}"]
    else:
        L.append("La fuente no menciona errores comunes.")

    L += ["", "## 5. Comparativas", ""]
    if hechos["comparativas"]:
        for comp in hechos["comparativas"]:
            L += [f"**{comp['titulo']}**", "",
                  "| " + " | ".join(_celda(c) for c in comp["columnas"]) + " |",
                  "| " + " | ".join("---" for _ in comp["columnas"]) + " |"]
            L += ["| " + " | ".join(_celda(c) for c in fila) + " |" for fila in comp["filas"]]
            L.append("")
        L.pop()
    else:
        L.append("La fuente no contrasta conceptos de forma explícita.")

    L += ["", "## 6. Glosario", ""]
    L += glosario_lineas if glosario_lineas else ["Sin términos adicionales a los de la sección 2."]

    L += ["", "## 7. Autoevaluación", ""]
    if autoeval:
        L += ["**Preguntas de repaso**", ""]
        for n, q in enumerate(autoeval, 1):
            L += [f"{n}. **Pregunta**: {q['pregunta']}",
                  f"   - **Respuesta**: {q['respuesta']}",
                  f"   - **Explicación**: {q['explicacion']}"]
    else:
        L.append("No se generaron preguntas de repaso.")
    if hechos["ejercicios"]:
        L += ["", "**Ejercicios propuestos en clase**", ""]
        L += [f"{n}. {e['enunciado']}" for n, e in enumerate(hechos["ejercicios"], 1)]

    L += ["", "## 8. Pendiente de Revisar", ""]
    L += [f"- {p}" for p in pendientes] if pendientes else ["Sin puntos pendientes."]
    return "\n".join(L).rstrip() + "\n"


def lineas_glosario(presentes: Dict[str, str], conceptos: List[dict]) -> List[str]:
    """Términos del glosario controlado que aparecen en la fuente y no están ya en 'Conceptos Clave'."""
    en_conceptos = " ".join(_norm(c["termino"]) for c in conceptos)
    return [f"- **{t}**: {d}" for t, d in presentes.items() if _norm(t) not in en_conceptos]


def generar_indice_evidencias(hechos: Dict[str, list]) -> str:
    nombres = {"conceptos": "Concepto", "procedimientos": "Procedimiento", "errores": "Error",
               "comparativas": "Comparativa", "ejercicios": "Ejercicio", "ideas_clave": "Idea clave",
               "dudas": "Duda"}
    clave = {"conceptos": "termino", "procedimientos": "titulo", "errores": "sintoma",
             "comparativas": "titulo", "ejercicios": "enunciado", "ideas_clave": "texto", "dudas": "texto"}
    L = ["# Índice de evidencias", "",
         "Cada hecho de los apuntes y el momento de la fuente del que sale.", ""]
    for cat in ("conceptos", "procedimientos", "errores", "comparativas", "ejercicios", "ideas_clave", "dudas"):
        for it in hechos[cat]:
            L.append(f"- [{it.get('evidencia') or 's/t'}] {nombres[cat]}: {_s(it[clave[cat]])[:90]}")
    return "\n".join(L) + "\n"


# ---------------------------------------------------------------------------
# 7. Autoevaluación (una sola llamada, solo desde hechos verificados)
# ---------------------------------------------------------------------------
def _hechos_para_autoevaluacion(hechos: Dict[str, list], max_chars: int = 14000) -> str:
    datos = {
        "conceptos": [{"termino": c["termino"], "definicion": c["definicion"], "ejemplo": c.get("ejemplo", "")}
                      for c in hechos["conceptos"]],
        "procedimientos": [{"titulo": p["titulo"], "pasos": p["pasos"]} for p in hechos["procedimientos"]],
        "errores": [{k: e[k] for k in ("sintoma", "causa", "solucion")} for e in hechos["errores"]],
        "comparativas": [{k: c[k] for k in ("titulo", "columnas", "filas")} for c in hechos["comparativas"]],
    }
    texto = json.dumps(datos, ensure_ascii=False)
    while len(texto) > max_chars:
        mayor = max(datos, key=lambda k: len(datos[k]))
        if not datos[mayor]:
            break
        datos[mayor].pop()
        texto = json.dumps(datos, ensure_ascii=False)
    return texto


def generar_autoevaluacion(hechos: Dict[str, list], keep_alive: Union[str, int] = "5m") -> List[dict]:
    total = sum(len(hechos[c]) for c in ("conceptos", "procedimientos", "errores", "comparativas"))
    if total < 3:
        print("  [Autoevaluación] Pocos hechos: se omite.")
        return []
    n_obj = min(10, max(3, total // 2))
    min_aplic = -(-n_obj // 3)  # ceil(n/3)
    hechos_json = _hechos_para_autoevaluacion(hechos)
    base = _claves_palabras(hechos_json)
    refuerzo = ""
    ultimo: List[dict] = []
    for intento in (1, 2):
        prompt = (
            f"Crea hasta {n_obj} preguntas de repaso para estudiar, usando SOLO estos hechos verificados "
            "de la clase (no uses nada más).\n"
            f"- tipo 'recuerdo': pregunta directa sobre un concepto.\n"
            f"- tipo 'aplicacion': el alumno debe aplicar lo aprendido (qué imprime un código, qué diferencia hay entre "
            f"dos cosas, cuál es el fallo, qué paso va después). Al menos {min_aplic} deben ser de aplicación.\n"
            "- La respuesta NO puede ser una copia literal de la definición: reformúlala brevemente.\n"
            "- 'explicacion': por qué es correcta y qué error común evita.\n"
            "- No inventes datos ni uses nombres de personas. Si los hechos no dan para tantas preguntas, genera menos.\n"
            f"{refuerzo}\nHECHOS (JSON):\n{hechos_json}"
        )
        try:
            datos = llamar_modelo_json(prompt, SCHEMA_AUTOEVAL, OPTIONS_AUTOEVAL, keep_alive=keep_alive, system=SYSTEM_PROMPT)
        except (TruncationError, ValueError, RuntimeError) as exc:
            print(f"  [Autoevaluación] intento {intento} fallido: {exc}")
            continue
        brutas = datos.get("preguntas", []) if isinstance(datos, dict) else []
        validas: List[dict] = []
        for q in brutas:
            if not isinstance(q, dict):
                continue
            preg, resp, expl = _s(q.get("pregunta")), _s(q.get("respuesta")), _s(q.get("explicacion"))
            tipo = q.get("tipo") if q.get("tipo") in ("recuerdo", "aplicacion") else "recuerdo"
            if not preg or not resp or not expl or _norm(resp) == _norm(preg):
                continue
            if not _fundamentado(resp + " " + expl, base, 0.4):
                continue
            validas.append({"tipo": tipo, "pregunta": preg, "respuesta": resp, "explicacion": expl})
        ultimo = validas[:n_obj]
        if sum(1 for q in ultimo if q["tipo"] == "aplicacion") >= min_aplic or intento == 2:
            break
        refuerzo = (f"IMPORTANTE: la versión anterior tenía pocas preguntas de aplicación. "
                    f"Incluye al menos {min_aplic} de tipo 'aplicacion'.\n")
    return ultimo


# ---------------------------------------------------------------------------
# 8. Limpieza y validación previa al guardado
# ---------------------------------------------------------------------------
def limpiar_apuntes_previo_guardado(texto: str) -> str:
    """Filtros previos al guardado:
    - Elimina marcas '(Verificar...)', timestamps [HH:MM:SS] y 🕒 del cuerpo.
    - Retira pies de página y líneas meta de cierre.
    - Normaliza espacios SIN tocar la indentación ni el contenido de los bloques de código.
    """
    texto = re.sub(r"\((?:Verificar\vert{}verificar)[^\)]*\)", "", texto)
    texto = RE_TS_CUERPO.sub("", texto)

    lineas_limpias: List[str] = []
    for linea in texto.splitlines():
        if re.match(r"^\s*\[\^[^\]]+\]:\s*", linea):
            continue
        if re.search(
            r"^\s*(?:---\s*)?(?:Documento generado|Fin de los apuntes|Apuntes generados automáticamente|"
            r"Nota de unificación|Generado por|Este documento (?:es una unificaci|unificado|proporciona|ha sido))",
            linea, re.IGNORECASE,
        ):
            continue
        lineas_limpias.append(linea)

    salida: List[str] = []
    en_codigo = False
    for linea in lineas_limpias:
        if linea.lstrip().startswith("```"):
            en_codigo = not en_codigo
            salida.append(linea.rstrip())
        elif en_codigo:
            salida.append(linea.rstrip())
        else:
            sangria = len(linea) - len(linea.lstrip(" "))
            cuerpo = re.sub(r"(?<=\S)[ \t]{2,}", " ", linea.lstrip(" "))
            salida.append(" " * sangria + cuerpo.rstrip())
    texto_limpio = "\n".join(salida)
    return re.sub(r"\n{3,}", "\n\n", texto_limpio).strip()


RE_URL = re.compile(r"https?://[^\s)>\]]+", re.IGNORECASE)


def sanear_urls(texto: str) -> Tuple[str, int]:
    """Sustituye URLs de dominios no permitidos (suelen ser basura de transcripción)."""
    n = 0

    def _r(m: "re.Match[str]") -> str:
        nonlocal n
        host = re.sub(r"^https?://", "", m.group(0), flags=re.IGNORECASE).split("/")[0].split(":")[0].lower()
        if any(host == d or host.endswith("." + d) for d in DOMINIOS_PERMITIDOS):
            return m.group(0)
        n += 1
        return "[enlace no verificado]"

    return RE_URL.sub(_r, texto), n


def validar_timestamps(contenido: str) -> str:
    hay_reloj = bool(re.search(r"🕒\s*\[\d{2}:\d{2}:\d{2}", contenido))
    hay_timestamps = bool(re.search(r"\[\d{2}:\d{2}:\d{2}\]", contenido))
    if hay_reloj or hay_timestamps:
        print("\n[AVISO] Se detectaron timestamps residuales en el documento (deben omitirse según las reglas).")
    else:
        print("\n[OK] Documento verificado sin timestamps en el cuerpo.")
    return contenido


def secciones_que_faltan(texto: str) -> List[str]:
    """Secciones obligatorias ausentes o fuera de orden."""
    faltan = []
    pos = -1
    for num, nombre in SECCIONES:
        m = re.search(rf"^## {num}\. {re.escape(nombre)}\s*$", texto, re.MULTILINE)
        if not m or m.start() < pos:
            faltan.append(f"{num}. {nombre}")
        else:
            pos = m.start()
    return faltan


# ---------------------------------------------------------------------------
# 9. Auditoría (determinista siempre; con LLM opcional)
# ---------------------------------------------------------------------------
def cobertura_secciones(secciones: List[str], texto_hechos: str) -> List[str]:
    """Apartados de la fuente cuyas palabras apenas aparecen en lo extraído."""
    base = _claves_palabras(texto_hechos)
    sin_cobertura = []
    for titulo in secciones:
        if _norm(titulo).startswith("actividad"):
            continue
        claves = _claves_palabras(titulo)
        if claves and len(claves & base) / len(claves) < 0.5:
            sin_cobertura.append(titulo)
    return list(dict.fromkeys(sin_cobertura))


def auditar_apuntes(texto_transcripcion: str, apuntes_generados: str, ruta_auditoria: str = "auditoria.md",
                    info_fuente: Optional[Dict[str, Any]] = None):
    print("\n--- Ejecutando auditoría de los apuntes ---")
    problemas: List[str] = []
    if re.search(r"\[\d{2}:\d{2}:\d{2}\]|🕒", apuntes_generados):
        problemas.append("Hay timestamps en el cuerpo de los apuntes.")
    if re.search(r"\(\s*verificar", apuntes_generados, re.IGNORECASE):
        problemas.append("Quedan marcas '(Verificar)' en el cuerpo.")
    if re.search(r"Este documento (?:es|unifica|proporciona)", apuntes_generados, re.IGNORECASE):
        problemas.append("Hay texto meta del modelo.")
    faltan = secciones_que_faltan(apuntes_generados.split("\n\n", 1)[-1] if apuntes_generados.startswith("> ") else apuntes_generados)
    if faltan:
        problemas.append("Faltan secciones obligatorias: " + ", ".join(faltan) + ".")
    for url in RE_URL.findall(apuntes_generados):
        problemas.append(f"URL en los apuntes (verifícala): {url}")
    if info_fuente:
        if info_fuente.get("imagenes"):
            problemas.append(f"La fuente tenía {info_fuente['imagenes']} imagen(es) sin descripción: su contenido no está en los apuntes.")
        for s in info_fuente.get("sin_cobertura", []):
            problemas.append(f"Apartado de la fuente sin cobertura aparente: «{s}».")
    informe = ["# Informe de auditoría", ""]
    informe += [f"- 🚩 {p}" for p in problemas] if problemas else ["- ✅ Sin problemas estructurales detectados."]

    if AUDITORIA_LLM:
        presupuesto = int(OPTIONS_EXTRACCION["num_ctx"] * CTX_HEADROOM * CHARS_POR_TOKEN_APROX)
        if len(texto_transcripcion) + len(apuntes_generados) <= presupuesto - 2000:
            prompt = (
                "Compara la FUENTE con los APUNTES y señala con '🚩 DISCREPANCIA TÉCNICA: [sección]' cualquier "
                "afirmación, código, operador o dato de los apuntes que NO aparezca en la fuente. No reescribas nada. "
                "Si no hay discrepancias, responde solo: ✅ Sin discrepancias detectadas.\n\n"
                f"FUENTE:\n{texto_transcripcion}\n\n---\nAPUNTES:\n{apuntes_generados}"
            )
            try:
                reporte = llamar_modelo_seguro(prompt, {"temperature": 0.05, "num_ctx": 16384, "num_predict": 2048})
                informe += ["", "## Auditoría con LLM", "", reporte]
            except Exception as exc:
                informe += ["", f"(La auditoría con LLM falló: {exc})"]
        else:
            informe += ["", "(Auditoría con LLM omitida: fuente demasiado larga para el contexto.)"]

    with open(ruta_auditoria, "w", encoding="utf-8") as f:
        f.write("\n".join(informe) + "\n")
    print(f"[{'AVISO' if problemas else 'OK'}] Informe de auditoría: {ruta_auditoria} ({len(problemas)} aviso(s))")


# ---------------------------------------------------------------------------
# 10. Banco de preguntas (quiz) desde los apuntes
# ---------------------------------------------------------------------------
def _texto_para_quiz(texto_apuntes: str) -> str:
    """Quita secciones que no deben generar preguntas (glosario, pendiente de revisar)."""
    out: List[str] = []
    saltando = False
    for linea in texto_apuntes.splitlines():
        if linea.startswith("## "):
            saltando = bool(re.match(r"## (?:6\. Glosario|8\. Pendiente)", linea))
        if not saltando:
            out.append(linea)
    return "\n".join(out)


def generar_preguntas_clase(texto_apuntes: str, materia: str, clase: str) -> list[dict]:
    """Genera hasta 5 preguntas tipo test a partir de los apuntes Markdown.

    Valida cada pregunta (4 opciones distintas, 'correcta' en rango) y descarta las inválidas
    en lugar de rellenarlas. Baraja las opciones por código (determinista por id) y recalcula
    'correcta'. Descarga el modelo de la VRAM al terminar (keep_alive=0).
    """
    if not texto_apuntes or not texto_apuntes.strip():
        print("[QUIZ] Advertencia: texto de apuntes vacío, no se pueden generar preguntas.")
        return []

    texto_quiz = _texto_para_quiz(texto_apuntes)[:24000]
    print(f"\n--- [QUIZ] Generando evaluación activa para '{clase}' ({materia}) ---")

    prompt_sistema = (
        "Eres un profesor técnico y pedagógico de ciclos formativos de DAW. Diseña preguntas formativas "
        "rigurosas basadas ESTRICTAMENTE en los apuntes proporcionados.\n\n"
        "DIRECTIVAS:\n"
        "- Genera hasta 5 preguntas tipo test. Si los apuntes no dan para 5 buenas, genera menos: NO rellenes.\n"
        "- Cada pregunta tiene exactamente 4 opciones DISTINTAS en 'opciones'.\n"
        "- 'correcta' es el índice entero (0-3) de la opción correcta.\n"
        "- 'tipo': 'conceptual', 'codigo' o 'analisis'. Si evalúa código, ponlo en 'codigo'; si no, \"\".\n"
        "- 'explicacion': por qué la correcta lo es y qué error común evitan los distractores.\n"
        "- PROHIBIDO inventar conceptos, métodos o sintaxis que no estén en los apuntes."
    )
    prompt_usuario = (
        f"A partir de los apuntes de la materia '{materia}' y clase '{clase}', genera el banco de preguntas "
        f"en JSON conforme al esquema:\n\n---\nAPUNTES:\n{texto_quiz}"
    )

    fecha_creacion = datetime.now().isoformat()
    materia_str, clase_str = materia.strip(), clase.strip()
    finales: List[dict] = []
    vistos: set = set()
    descartadas = 0

    for intento in (1, 2):
        try:
            respuesta = ollama.chat(
                model=MODELO_LLM, format=SCHEMA_PREGUNTAS, options=OPTIONS_QUIZ,
                keep_alive=0,  # Descargar el modelo tras esta última llamada
                messages=[{"role": "system", "content": prompt_sistema},
                          {"role": "user", "content": prompt_usuario}],
            )
        except Exception as exc:
            print(f"  [QUIZ] fallo en llamada al modelo: {exc}")
            descargar_modelo_ollama(MODELO_LLM)
            raise
        try:
            contenido, _ = _leer_respuesta(respuesta)
            datos = json.loads(contenido)
        except (RuntimeError, ValueError) as err:
            descargar_modelo_ollama(MODELO_LLM)
            raise ValueError(f"Fallo al obtener/decodificar el JSON de preguntas: {err}")

        brutas = datos.get("preguntas", []) if isinstance(datos, dict) else (datos if isinstance(datos, list) else [])
        for p in brutas:
            if not isinstance(p, dict):
                continue
            pregunta = str(p.get("pregunta", "")).strip()
            explicacion = str(p.get("explicacion", "")).strip()
            opciones_raw = p.get("opciones", [])
            opciones = [str(o).strip() for o in opciones_raw] if isinstance(opciones_raw, list) else []
            try:
                correcta = int(p.get("correcta"))
            except (ValueError, TypeError):
                descartadas += 1
                continue
            if (not pregunta or not explicacion or len(opciones) != 4 or any(not o for o in opciones)
                    or len({_norm(o) for o in opciones}) != 4 or not 0 <= correcta < 4):
                descartadas += 1
                continue
            id_p = hashlib.sha1(
                f"{materia_str.lower()}/{clase_str.lower()}/{pregunta.lower()}".encode("utf-8")
            ).hexdigest()[:10]
            if id_p in vistos:
                continue
            vistos.add(id_p)
            texto_correcto = opciones[correcta]
            random.Random(id_p).shuffle(opciones)  # barajado determinista: mismo id -> mismo orden
            finales.append({
                "id": id_p, "materia": materia_str, "clase": clase_str, "fecha_creacion": fecha_creacion,
                "tipo": str(p.get("tipo", "conceptual")).strip(),
                "pregunta": pregunta,
                "codigo": str(p.get("codigo", "") or "").strip(),
                "opciones": opciones,
                "correcta": opciones.index(texto_correcto),
                "explicacion": explicacion,
            })
        if len(finales) >= 3:
            break
        if intento == 1:
            print(f"  [QUIZ] Solo {len(finales)} pregunta(s) válida(s); reintentando una vez.")

    finales = finales[:5]
    print(f"  [QUIZ] {len(finales)} pregunta(s) válida(s) ({descartadas} descartada(s) por esquema).")
    return finales


# ---------------------------------------------------------------------------
# 11. Pipeline principal
# ---------------------------------------------------------------------------
def asegurar_meta(ruta_salida: Path, tipo_fuente: str, contenido: str = "") -> None:
    """meta.json por clase. Conserva las claves ajenas y el estado 'revisada' mientras el apunte no cambie.

    Si el apunte regenerado difiere del que se revisó (hash distinto), 'revisada' vuelve a False: el
    contenido nuevo no está revisado y no debe alimentar la práctica diaria. Con el mismo contenido
    (reprocesado idempotente) el estado se conserva. Un meta.json previo sin hash se respeta."""
    ruta_meta = ruta_salida.parent / "meta.json"
    existente: Dict[str, Any] = {}
    if ruta_meta.exists():
        try:
            with open(ruta_meta, "r", encoding="utf-8") as f:
                leido = json.load(f)
            existente = leido if isinstance(leido, dict) else {}
        except (OSError, ValueError):
            existente = {}  # meta.json corrupto: se regenera
    sha = hashlib.sha1(contenido.encode("utf-8")).hexdigest()[:12] if contenido else str(existente.get("apuntes_sha1", ""))
    revisada = bool(existente.get("revisada", False))
    previo = existente.get("apuntes_sha1")
    if revisada and contenido and previo and previo != sha:
        revisada = False
        print("[META] El apunte cambió respecto al revisado: 'revisada' vuelve a False.")
    datos = dict(existente)
    datos.update({"revisada": revisada, "fuente": tipo_fuente, "apuntes_sha1": sha,
                  "generado": datetime.now().isoformat(timespec="seconds")})
    with open(ruta_meta, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=2)


def generar_material_estudio(
    ruta_transcripcion: str = "transcripcion.txt",
    ruta_salida: str = "apuntes.md",
    guardar_bloques_crudos: bool = True,
    liberar_vram: bool = True,
):
    """liberar_vram=True descarga el modelo al terminar. Pásalo a False si llamas justo después a
    generar_preguntas_clase (que ya descarga) para evitar una recarga; si hay un error se descarga siempre."""
    if not os.path.exists(ruta_transcripcion):
        print(f"Error: No se encuentra el archivo '{ruta_transcripcion}'.")
        return

    print(f"--- Leyendo transcripción: {ruta_transcripcion} ---")
    with open(ruta_transcripcion, "r", encoding="utf-8") as f:
        texto_clase = f.read()
    if not texto_clase.strip():
        print("Error: El archivo de transcripción está vacío.")
        return

    glosario = cargar_glosario()
    info = preparar_fuente(texto_clase, glosario)
    texto = info["texto"]
    print(f"--- Fuente: {info['tipo']} | {info['correcciones']} corrección(es) de glosario | "
          f"{info['lineas_filtradas']} línea(s) filtrada(s) ---")
    if not texto.strip():
        print("Error: tras limpiar la fuente no queda contenido.")
        return

    bloques = dividir_transcripcion(texto, max_chars=9000, marcador_seccion=MARCADOR_SECCION)
    total = len(bloques)
    print(f"--- Fuente estructurada en {total} bloque(s) de ~9000 caracteres ---")
    limite_chars = int(OPTIONS_EXTRACCION["num_ctx"] * CTX_HEADROOM * CHARS_POR_TOKEN_APROX)

    completado = False
    try:
        hechos_por_bloque: List[Dict[str, list]] = []
        fallidos: List[str] = []
        for i, fragmento in enumerate(bloques, start=1):
            print(f"\n[Bloque {i}/{total}]")
            if len(fragmento) + 4000 > limite_chars:
                print("[AVISO] El fragmento se acerca al límite de contexto: riesgo de truncado.")
            presentes = terminos_presentes(fragmento, glosario)
            prompt = construir_prompt_extraccion(fragmento, i, total, info["tipo"], presentes)
            base_extra = " ".join(presentes.values())
            hechos = None
            for intento in (1, 2):
                try:
                    datos = llamar_modelo_json(prompt, SCHEMA_EXTRACCION, OPTIONS_EXTRACCION)
                    hechos, descartes = validar_extraccion(datos, fragmento, base_extra)
                    n_ok = sum(len(hechos[c]) for c in CATEGORIAS if c != "dudas")
                    print(f"  -> {n_ok} hecho(s) válido(s), {descartes} descartado(s).")
                    break
                except (TruncationError, ValueError, RuntimeError) as exc:
                    print(f"  [AVISO] Bloque {i}, intento {intento} fallido: {exc}")
            if hechos is None:
                rango = _rango_ts(fragmento)
                donde = f"{_fmt_ts(rango[0])}–{_fmt_ts(rango[1])}" if rango else f"bloque {i}"
                fallidos.append(donde)
            else:
                hechos_por_bloque.append(hechos)

        if not hechos_por_bloque:
            raise RuntimeError("No se pudo extraer contenido de ningún bloque; no se sobrescriben los apuntes.")

        hechos = fusionar_hechos(hechos_por_bloque)
        if not any(hechos[c] for c in ("conceptos", "procedimientos", "errores", "comparativas", "ejercicios")):
            raise RuntimeError("La extracción no produjo hechos utilizables; no se sobrescriben los apuntes.")

        print("\n--- Generando autoevaluación a partir de los hechos verificados ---")
        autoeval = generar_autoevaluacion(hechos)

        # Pendiente de revisar (todo lo dudoso va aquí, nunca en el cuerpo)
        info["sin_cobertura"] = cobertura_secciones(info["secciones"], _texto_plano_hechos(hechos)) \
            if info["tipo"] == "documento" else []
        pendientes = [d["texto"] for d in hechos["dudas"]]
        pendientes += [f"El fragmento {r} no pudo procesarse: su contenido falta en estos apuntes." for r in fallidos]
        if info["imagenes"]:
            pendientes.append(f"La fuente tenía {info['imagenes']} imagen(es) sin descripción (tablas, esquemas o código): "
                              "su contenido NO está en estos apuntes. Consulta el documento original.")
        if info["sin_cobertura"]:
            pendientes.append("Apartados de la fuente sin cobertura aparente: " + ", ".join(info["sin_cobertura"]) + ".")
        if MARCA_ENLACE_ROTO in texto:
            pendientes.append("La fuente incluye un enlace que no se transcribió bien: búscalo en el documento original.")
        if info["corte"]:
            pendientes.append(f"Se descartó el contenido posterior a la despedida del docente (a partir de {info['corte']}).")

        p_salida = Path(ruta_salida).resolve()
        titulo = p_salida.parent.name.replace("_", " ") if INCLUIR_H1 else None
        glos = lineas_glosario(terminos_presentes(texto, glosario), hechos["conceptos"])
        contenido_final = componer_apuntes(hechos, autoeval, pendientes, glos, titulo)

        contenido_final = limpiar_apuntes_previo_guardado(contenido_final)
        contenido_final, n_urls = sanear_urls(contenido_final)
        if n_urls:
            print(f"[AVISO] Se sustituyeron {n_urls} URL(s) no verificadas.")
        contenido_final = validar_timestamps(contenido_final)
        faltan = secciones_que_faltan(contenido_final)
        if faltan:
            print("[AVISO] Faltan secciones obligatorias: " + ", ".join(faltan))

        # Salvaguarda contra sobreescritura silenciosa (I-7)
        if os.path.exists(ruta_salida):
            ruta_bak = f"{ruta_salida}.bak-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
            shutil.copy2(ruta_salida, ruta_bak)
            print(f"📦 Backup preventivo creado: '{ruta_bak}'")

        cuerpo_sin_cabecera = contenido_final
        if CABECERA_REGISTRO and not contenido_final.startswith("> 🏛️ **Registro de clase**"):
            materia_acad = "DAW"
            if len(p_salida.parts) >= 3 and p_salida.parts[-3] == "clases":
                materia_acad = p_salida.parts[-2].replace("_", " ").title()
            elif len(p_salida.parents) >= 2:
                materia_acad = p_salida.parent.parent.name.replace("_", " ").title()
            fecha_acad = datetime.now().strftime("%d/%m/%Y")
            contenido_final = f"> 🏛️ **Registro de clase** • {materia_acad} • {fecha_acad}\n\n" + contenido_final.lstrip()

        with open(ruta_salida, "w", encoding="utf-8") as f:
            f.write(contenido_final)
        print(f"\n🎉 ¡Apuntes finalizados! Guardados en: {ruta_salida}")

        base, _ = os.path.splitext(ruta_salida)
        with open(f"{base}_evidencias.md", "w", encoding="utf-8") as f:
            f.write(generar_indice_evidencias(hechos))
        if guardar_bloques_crudos:
            with open(f"{base}_hechos.json", "w", encoding="utf-8") as f:
                json.dump(hechos, f, ensure_ascii=False, indent=2)
            print(f"--- Hechos extraídos guardados en: {base}_hechos.json ---")
        asegurar_meta(p_salida, info["tipo"], cuerpo_sin_cabecera)

        auditar_apuntes(texto, cuerpo_sin_cabecera, f"{base}_auditoria.md", info)
        completado = True

    except TruncationError as e:
        print(f"\n❌ ERROR CRÍTICO: {e}")
        raise RuntimeError(f"Proceso abortado por truncamiento: {e}") from e
    finally:
        if liberar_vram or not completado:
            descargar_modelo_ollama(MODEL)


if __name__ == "__main__":
    archivo_entrada = sys.argv[1] if len(sys.argv) > 1 else "transcripcion.txt"
    archivo_salida = sys.argv[2] if len(sys.argv) > 2 else "apuntes.md"
    generar_material_estudio(archivo_entrada, archivo_salida)