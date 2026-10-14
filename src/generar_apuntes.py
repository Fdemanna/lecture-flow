"""
Generador de apuntes DAW a partir de transcripciones con Qwen 2.5 7B (Ollama).
Incluye:
- Troceo inteligente por caracteres (~9.000 chars) para evitar saturar memoria.
- Detección determinista de truncamiento usando 'done_reason: length'.
- Acceso seguro a la respuesta de Ollama con control de fallos (I-1).
- Backup preventivo automático antes de sobrescribir apuntes.md (I-7).
- Auditoría automática de fidelidad y discrepancias técnicas (Critic-Loop).
"""
from __future__ import annotations

from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sys
from typing import Optional, Union, Dict, Any, List
import ollama

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

MODEL = "qwen2.5:7b"
MODELO_LLM = MODEL

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


# [M-2] Constantes para estimación del presupuesto de contexto en unificación
CHARS_POR_TOKEN_APROX = 3.5  # Estimación conservadora para texto en español
CTX_HEADROOM = 0.75          # Usar máximo el 75 % del contexto disponible

OPTIONS_BLOQUE = {
    "temperature": 0.15,
    "num_ctx": 16384,
    "num_predict": 3072,
}

OPTIONS_UNIFICACION = {
    "temperature": 0.15,
    "num_ctx": 16384,
    "num_predict": 4096,
}

SYSTEM_PROMPT = (
    "Eres un profesor experto en técnicas de estudio y desarrollo de software (DAW). "
    "Tu tarea es convertir transcripciones de clase en apuntes rigurosos, esquemáticos, "
    "sin redundancias y optimizados para el estudio activo."
)

REGLAS_MAESTRAS = """
REGLAS PEDAGÓGICAS ESTRICTAS:
1. DEFINICIÓN ÚNICA: Cada concepto se define UNA sola vez, exactamente en el punto donde se desarrolla ("## 2. Conceptos Clave"). Prohibido duplicar definiciones en introducciones, resúmenes, comparativas o glosarios.
2. REGLAS NEGATIVAS CRÍTICAS:
   - PROHIBIDO incluir timestamps [HH:MM:SS] dentro del cuerpo de los apuntes.
   - PROHIBIDO incluir marcas como "(Verificar)" en el cuerpo (lo dudoso va exclusivamente a la sección "## 8. Pendiente de Revisar").
   - PROHIBIDO incluir comentarios meta ("Este documento es una unificación...", "A continuación se presentan...").
   - Prohibido inventar definiciones o código que no aparezca en la clase.
3. CONCISIÓN Y SINTAXIS: Frases cortas y directas. Prefiere esquemas, tablas de comparación y secuencias operativas antes que párrafos densos. La longitud debe ocupar como máximo un 30% del material original.
4. CÓDIGO FUNCIONAL: Fragmentos en bloques funcionales con sintaxis resaltada y comandos de terminal cuando aplique, funcionales y directamente basados en la clase.
5. PRIVACIDAD: No incluyas nombres propios de alumnos ni del profesor, ni menciones personales. Escribe "un alumno", "una alumna" o "el profesor".
"""

# Estructura de salida compartida por clase única, fusión Tree-Reduce y unificación final.
# Compatible con notion_exporter: el H1 se usa como título y el resto no pasa de H2.
ESTRUCTURA_APUNTES = """
ESTRUCTURA OBLIGATORIA DEL DOCUMENTO:
# {titulo_tema}

## 1. Lo Esencial
(Resumen conciso del núcleo de la sesión, máximo 5 líneas).

## 2. Conceptos Clave
(Definición única de cada término relevante con su aplicación técnica).

## 3. Procedimientos Paso a Paso
(Secuencias operativas, comandos de terminal o código en bloques funcionales).

## 4. Errores Comunes y Solución
- **Síntoma**: ...
  - *Causa*: ...
  - *Solución*: ...

## 5. Comparativas
(Tabla Markdown contrastando herramientas, tecnologías o métodos tratados).

## 6. Glosario
(Definiciones de una sola línea de términos técnicos que hayan aparecido).

## 7. Autoevaluación
(Preguntas de repaso con su respuesta y explicación técnica inmediata).

## 8. Pendiente de Revisar
(Aspectos que quedaron dudosos o abiertos. Si no hay ninguno: "Sin puntos pendientes.").
"""


class TruncationError(Exception):
    """Excepción lanzada cuando el modelo agota el límite de tokens o contexto."""
    pass


# ---------------------------------------------------------------------------
# 1. Troceo de la transcripción
# ---------------------------------------------------------------------------
def dividir_transcripcion(texto: str, max_chars: int = 9000) -> list[str]:
    """Trocea el texto respetando líneas completas para no quebrar timestamps."""
    lineas = texto.split("\n")
    bloques = []
    bloque_actual = []
    tamano_actual = 0

    for linea in lineas:
        if tamano_actual + len(linea) > max_chars and bloque_actual:
            bloques.append("\n".join(bloque_actual))
            bloque_actual = []
            tamano_actual = 0
        bloque_actual.append(linea)
        tamano_actual += len(linea) + 1

    if bloque_actual:
        bloques.append("\n".join(bloque_actual))

    return bloques


# ---------------------------------------------------------------------------
# 2. Prompts
# ---------------------------------------------------------------------------
def construir_prompt_bloque(fragmento: str, num_bloque: int, total_bloques: int) -> str:
    return f"""
Transforma el siguiente fragmento ({num_bloque} de {total_bloques}) de una clase técnica en apuntes parciales.
Estos apuntes se fusionarán después con los del resto de fragmentos, así que usa la misma plantilla fija de 8 secciones obligatorias
para que la consolidación sea directa. Incluye solo las secciones con contenido real en este fragmento.

REGLAS NEGATIVAS ESTRICTAS:
- PROHIBIDO incluir timestamps [HH:MM:SS] dentro del cuerpo de los apuntes.
- PROHIBIDO incluir marcas como "(Verificar)" en el cuerpo (lo dudoso va exclusivamente a la sección "## 8. Pendiente de Revisar").
- PROHIBIDO incluir comentarios meta ("Este documento es una unificación...", "A continuación se presentan...").
- Prohibido inventar definiciones o código que no aparezca en la clase.

{REGLAS_MAESTRAS}

{ESTRUCTURA_APUNTES}

---
FRAGMENTO DE TRANSCRIPCIÓN:
{fragmento}
"""


def construir_prompt_clase_unica(transcripcion: str) -> str:
    return f"""
Convierte la transcripción de esta clase técnica en apuntes de estudio en Markdown respetando estrictamente la plantilla fija de 8 secciones.

REGLAS NEGATIVAS ESTRICTAS:
- PROHIBIDO incluir timestamps [HH:MM:SS] dentro del cuerpo de los apuntes.
- PROHIBIDO incluir marcas como "(Verificar)" en el cuerpo (lo dudoso va exclusivamente a la sección "## 8. Pendiente de Revisar").
- PROHIBIDO incluir comentarios meta ("Este documento es una unificación...", "A continuación se presentan...").
- Prohibido inventar definiciones o código que no aparezca en la clase.

{REGLAS_MAESTRAS}

{ESTRUCTURA_APUNTES}

---
TRANSCRIPCIÓN COMPLETA:
{transcripcion}
"""


def construir_prompt_unificacion(apuntes_por_bloque: list[str]) -> str | None:
    apuntes_concatenados = "\n\n---SIGUIENTE SECCIÓN---\n\n".join(apuntes_por_bloque)

    # [M-2] Verificar presupuesto de contexto antes de llamar al modelo
    tokens_estimados = len(apuntes_concatenados) / CHARS_POR_TOKEN_APROX
    limite_seguro = OPTIONS_UNIFICACION["num_ctx"] * CTX_HEADROOM
    if tokens_estimados > limite_seguro:
        print(
            f"\n⚠️  [M-2] ADVERTENCIA: El prompt de unificación excede el presupuesto seguro "
            f"({tokens_estimados:.0f} tokens estimados > {limite_seguro:.0f} límite). "
            f"Se activa fallback: concatenación directa sin LLM."
        )
        return None

    return f"""
A continuación tienes los apuntes generados a partir de fragmentos consecutivos de UNA MISMA clase técnica de DAW.
Consolídalos en un único documento definitivo respetando exactamente las 8 secciones de la plantilla fija obligatoria.

REGLAS DE UNIFICACIÓN:
1. Un solo título H1 (# {{titulo_tema}}) y una sola instancia de cada una de las 8 secciones en el orden establecido.
2. PROHIBIDO incluir timestamps [HH:MM:SS] dentro del cuerpo de los apuntes.
3. PROHIBIDO incluir marcas como "(Verificar)" en el cuerpo (lo dudoso va exclusivamente a la sección "## 8. Pendiente de Revisar"). Si no hay ningún aspecto pendiente o dudoso, escribe textualmente: "Sin puntos pendientes.".
4. PROHIBIDO comentarios meta ("Este documento es una unificación...", "A continuación se presentan...").
5. Prohibido inventar definiciones o código que no aparezca en la clase.
6. En "## 4. Errores Comunes y Solución", mantén el formato:
   - **Síntoma**: ...
     - *Causa*: ...
     - *Solución*: ...
7. En "## 5. Comparativas", incluye la tabla Markdown contrastando herramientas, tecnologías o métodos tratados.
8. En "## 6. Glosario", definiciones de una sola línea de términos técnicos que hayan aparecido, sin repetir Conceptos Clave.
9. En "## 7. Autoevaluación", preguntas de repaso con su respuesta y explicación técnica inmediata.

{REGLAS_MAESTRAS}

{ESTRUCTURA_APUNTES}

---
APUNTES A UNIFICAR:
{apuntes_concatenados}
"""


# ---------------------------------------------------------------------------
# 3. Unificación Jerárquica en Árbol (Tree-Reduce)
# ---------------------------------------------------------------------------
def unificar_apuntes_jerarquico(apuntes_por_bloque: list[str]) -> str:
    """Reduce la lista de bloques en fases iterativas de pares hasta que caben
    en el presupuesto de contexto, evitando el fallback plano en clases largas."""

    # Caso trivial
    if len(apuntes_por_bloque) == 1:
        return apuntes_por_bloque[0]

    limite_seguro = OPTIONS_UNIFICACION["num_ctx"] * CTX_HEADROOM
    bloques = list(apuntes_por_bloque)
    ronda = 0

    while True:
        ronda += 1
        contenido_total = "\n\n".join(bloques)
        tokens_estimados = len(contenido_total) / CHARS_POR_TOKEN_APROX

        # Si ya cabe en el presupuesto, pasar a la unificación final
        if tokens_estimados <= limite_seguro:
            break

        print(
            f"\n  [Tree-Reduce] Ronda {ronda}: {len(bloques)} bloques, "
            f"{tokens_estimados:.0f} tokens estimados > {limite_seguro:.0f} límite. "
            f"Fusionando en parejas..."
        )

        bloques_reducidos = []
        i = 0
        while i < len(bloques):
            if i + 1 < len(bloques):
                # Sintetizar la pareja (i, i+1)
                pareja = bloques[i] + "\n\n---CONTINUACIÓN---\n\n" + bloques[i + 1]
                prompt_fusion = (
                    f"Fusiona estos dos apuntes parciales consecutivos de una clase de DAW en uno solo.\n\n"
                    f"{REGLAS_MAESTRAS}\n\n"
                    f"REGLAS DE FUSIÓN:\n"
                    f"- Respeta la estructura obligatoria de 8 secciones fijas (## 1. a ## 8.); cada sección aparece una sola vez.\n"
                    f"- PROHIBIDO incluir timestamps [HH:MM:SS] dentro del cuerpo de los apuntes.\n"
                    f"- PROHIBIDO incluir marcas como '(Verificar)' en el cuerpo (lo dudoso va exclusivamente a '## 8. Pendiente de Revisar').\n"
                    f"- PROHIBIDO comentarios meta ('Este documento es una unificación...', etc.).\n"
                    f"- Prohibido inventar definiciones o código que no aparezca en la clase.\n"
                    f"- Si un concepto aparece en ambos apuntes, déjalo en una única entrada con el dato más completo.\n"
                    f"- En '## 4. Errores Comunes y Solución', usa el formato Síntoma / Causa / Solución.\n"
                    f"- En '## 6. Glosario', definiciones de una sola línea.\n"
                    f"- En '## 8. Pendiente de Revisar', si no hay aspectos dudosos: 'Sin puntos pendientes.'.\n\n"
                    f"{ESTRUCTURA_APUNTES}\n\n"
                    f"---\n{pareja}"
                )
                try:
                    fusionado = llamar_modelo_seguro(prompt_fusion, OPTIONS_BLOQUE)
                    bloques_reducidos.append(fusionado)
                except Exception as e:
                    print(f"  [Tree-Reduce] Fallo en fusión de par ({i},{i+1}): {e}. Concatenando directo.")
                    bloques_reducidos.append(pareja)
                i += 2
            else:
                # Bloque impar al final: pasa a la siguiente ronda sin modificar
                bloques_reducidos.append(bloques[i])
                i += 1

        # Salvaguarda: si una ronda no reduce el número de bloques, salir del bucle
        if len(bloques_reducidos) >= len(bloques):
            print("  [Tree-Reduce] La reducción no progresa. Usando concatenación directa como último recurso.")
            break

        bloques = bloques_reducidos

    # Unificación final sobre los bloques reducidos
    print(f"\n  [Tree-Reduce] Unificación final sobre {len(bloques)} bloque(s) reducido(s).")
    prompt_final = construir_prompt_unificacion(bloques)
    if prompt_final is None:
        # Último recurso: concatenación directa
        return "\n\n---\n\n".join(bloques)
    try:
        return llamar_modelo_seguro(prompt_final, OPTIONS_UNIFICACION)
    except Exception as e:
        print(f"  [Tree-Reduce] Fallo en unificación final: {e}. Concatenando bloques reducidos.")
        return "\n\n---\n\n".join(bloques)


# ---------------------------------------------------------------------------
# 4. Sección de preparación para examen (Mejora 3)
# ---------------------------------------------------------------------------
def generar_seccion_examen(contenido_apuntes: str) -> str:
    """Genera una sección estructurada de preparación para examen a partir del documento final.

    OBSOLETA: ya no se invoca desde generar_material_estudio(). Su "Chuleta técnica rápida"
    duplicaba definiciones (contradice la Regla 1). Errores comunes y autoevaluación ya forman
    parte de las secciones 5 y 6 de ESTRUCTURA_APUNTES.
    """
    print("\n--- Generando sección '[EXAMEN] Preparación para Examen' ---")

    prompt_examen = f"""
A partir de este documento de apuntes de DAW, genera EXCLUSIVAMENTE la siguiente sección estandarizada en Markdown.
Básate Única y exclusivamente en el contenido del documento. No inventes requisitos externos.

## 🎯 Preparación para Examen

### ⚠️ Puntos críticos y preguntas trampa
(Mínimo 3 conceptos donde los alumnos suelen fallar según lo explicado en la clase.)

### 📝 Chuleta técnica rápida
(Esquema y conceptos clave en 5-10 viñetas de los conceptos o procedimientos esenciales.)

### ✅ Checklist de autoevaluación
(Casillas `- [ ]` con los conocimientos indispensables para considerar la sesión dominada.)

---
DOCUMENTO DE APUNTES:
{contenido_apuntes}
"""

    options_examen = {
        "temperature": 0.1,
        "num_ctx": 16384,
        "num_predict": 1536,
    }

    try:
        seccion = llamar_modelo_seguro(prompt_examen, options_examen)
        return seccion
    except Exception as e:
        print(f"[AVISO] No se pudo generar la sección de examen: {e}")
        return ""


# ---------------------------------------------------------------------------
# 3. Llamada al modelo con acceso seguro e inspección determinista (I-1)
# ---------------------------------------------------------------------------
def llamar_modelo_seguro(
    prompt_usuario: str,
    options: dict,
    keep_alive: Union[str, int] = "5m",
) -> str:
    print(f"  [Síntesis] Procesando con {MODEL} en local...", end="", flush=True)
    
    respuesta = ollama.chat(
        model=MODEL,
        options=options,
        keep_alive=keep_alive,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt_usuario},
        ],
    )
    print(" completado.")

    # Inspección de motivo de finalización
    done_reason = respuesta.get("done_reason") if isinstance(respuesta, dict) else getattr(respuesta, "done_reason", None)
    
    # Acceso seguro contra KeyError (I-1)
    mensaje = respuesta.get("message") if isinstance(respuesta, dict) else getattr(respuesta, "message", None)
    if mensaje is None:
        raise RuntimeError("La respuesta del modelo no contiene la estructura esperada ('message' no encontrado). Posible fallo de conexión o caída de Ollama.")

    contenido = mensaje.get("content") if isinstance(mensaje, dict) else getattr(mensaje, "content", None)
    if not contenido or not contenido.strip():
        raise RuntimeError("El modelo devolvió una respuesta vacía o nula. Posible truncamiento severo o fallo interno en la inferencia.")

    if done_reason == "length":
        raise TruncationError("La generación fue cortada abruptamente al agotarse el límite de tokens/contexto.")

    # Heurística secundaria por si se cortó una cabecera Markdown al final
    lineas = contenido.strip().split("\n")
    if lineas:
        ultima_linea = lineas[-1]
        if ultima_linea.startswith("###") and not ultima_linea.endswith((".", ":", "]", ")")):
            print(f"\n[AVISO] Posible corte estructural al final detectado: '{ultima_linea}'")

    return contenido


# ---------------------------------------------------------------------------
# 4. Limpieza y validación previa al guardado
# ---------------------------------------------------------------------------
def limpiar_apuntes_previo_guardado(texto: str) -> str:
    """Aplica filtros de limpieza previa al guardado en disco:
    - Elimina marcas residuales tipo '(Verificar...)' o '(verificar...)'.
    - Retira pies de página redundantes y líneas meta de cierre.
    """
    # 1. Filtro regex para eliminar marcas residuales tipo '(Verificar...)' o '(verificar...)'
    texto = re.sub(r"\((?:Verificar|verificar)[^\)]*\)", "", texto)

    # 2. Retirar pies de página redundantes y líneas meta
    lineas = texto.splitlines()
    lineas_limpias = []
    for linea in lineas:
        # Eliminar notas al pie redundantes tipo [^1]: ... o [^nota]: ...
        if re.match(r"^\s*\[\^[^\]]+\]:\s*", linea):
            continue
        # Eliminar pies de página redundantes de generación o cierre
        if re.search(
            r"^\s*(?:---\s*)?(?:Documento generado|Fin de los apuntes|Apuntes generados automáticamente|Nota de unificación|Generado por)",
            linea,
            re.IGNORECASE,
        ):
            continue
        lineas_limpias.append(linea)

    texto_limpio = "\n".join(lineas_limpias)

    # Normalizar espacios duplicados dejados por la eliminación de (Verificar...)
    texto_limpio = re.sub(r"[ \t]{2,}", " ", texto_limpio)
    # Evitar saltos de línea excesivos (> 2 consecutivos)
    texto_limpio = re.sub(r"\n{3,}", "\n\n", texto_limpio).strip()

    return texto_limpio


def validar_timestamps(contenido: str) -> str:
    hay_reloj = bool(re.search(r"🕒\s*\[\d{2}:\d{2}:\d{2}", contenido))
    hay_timestamps = bool(re.search(r"\[\d{2}:\d{2}:\d{2}\]", contenido))

    if hay_reloj or hay_timestamps:
        print("\n[AVISO] Se detectaron timestamps residuales en el documento (deben omitirse según las reglas).")
    else:
        print("\n[OK] Documento verificado sin timestamps en el cuerpo.")

    return contenido


# ---------------------------------------------------------------------------
# 5. Auditoría de fidelidad y discrepancias técnicas (Critic-Loop)
# ---------------------------------------------------------------------------
def auditar_apuntes(texto_transcripcion: str, apuntes_generados: str, ruta_auditoria: str = "auditoria.md"):
    print("\n--- Ejecutando auditoría de discrepancias y fidelidad técnica ---")

    hay_reloj = bool(re.search(r"🕒\s*\[\d{2}:\d{2}:\d{2}", apuntes_generados))
    hay_timestamps = bool(re.search(r"\[\d{2}:\d{2}:\d{2}\]", apuntes_generados))

    if hay_reloj or hay_timestamps:
        print("[AVISO AUDITORÍA] Se detectaron timestamps en los apuntes (deben omitirse según las reglas).")
    else:
        print("[OK AUDITORÍA] Apuntes libres de marcas de tiempo en el cuerpo.")

    prompt_auditoria = f"""
Aquí tienes la transcripción ORIGINAL de la clase y unos apuntes generados a partir de ella.
Compara ambos minuciosamente y señala CUALQUIER afirmación, sintaxis de código, operador (ej. :=, let, var),
símbolo o dato concreto en los apuntes que NO aparezca de forma explícita o equivalente en la transcripción.

REGLAS DE REVISIÓN:
- Marca cada problema con "🚩 DISCREPANCIA TÉCNICA: [línea o sección]" seguido de una justificación breve.
- Presta especial atención a si se inventó código escrito cuando el profesor usaba herramientas visuales (como diagramas de flujo o Raptor).
- Revisa que NO se hayan incluido timestamps [HH:MM:SS] dentro del cuerpo de los apuntes.
- Revisa que no haya marcas como "(Verificar)" en el cuerpo (lo dudoso va exclusivamente a "## 8. Pendiente de Revisar").
- Revisa que no haya comentarios meta ("Este documento es una unificación...", etc.).
- Si no encuentras inconsistencias o datos inventados, responde únicamente: "✅ Sin discrepancias detectadas. El documento es 100% fiel a la transcripción."
- No intentes reescribir ni corregir el documento; limítate a emitir el informe de auditoría.

---
TRANSCRIPCIÓN ORIGINAL:
{texto_transcripcion}

---
APUNTES GENERADOS:
{apuntes_generados}
"""

    options_auditor = {
        "temperature": 0.05,
        "num_ctx": 16384,
        "num_predict": 2048,
    }

    try:
        reporte = llamar_modelo_seguro(prompt_auditoria, options_auditor)
        with open(ruta_auditoria, "w", encoding="utf-8") as f:
            f.write(reporte)
        
        if "🚩 DISCREPANCIA TÉCNICA" in reporte or "🚩 POSIBLE ALUCINACIÓN" in reporte:
            print(f"[AVISO] Se detectaron discrepancias. Revisa el informe en: {ruta_auditoria}")
        else:
            print(f"[OK] Auditoría limpia. Informe guardado en: {ruta_auditoria}")
            
    except Exception as e:
        print(f"Error durante la fase de auditoría: {e}")


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
        # Fallback vía API REST directa de Ollama
        try:
            import urllib.request
            import json
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
# 5b. Generación desatendida de preguntas de evaluación activa (Quiz)
# ---------------------------------------------------------------------------
def generar_preguntas_clase(texto_apuntes: str, materia: str, clase: str) -> list[dict]:
    """Genera un banco de 5 preguntas tipo test a partir de los apuntes Markdown.

    Invoca a Ollama usando el schema JSON estricto SCHEMA_PREGUNTAS y descarga
    el modelo de la VRAM al terminar la llamada (keep_alive=0).
    """
    if not texto_apuntes or not texto_apuntes.strip():
        print("[QUIZ] Advertencia: texto de apuntes vacío, no se pueden generar preguntas.")
        return []

    print(f"\n--- [QUIZ] Generando evaluación activa para '{clase}' ({materia}) ---")
    print(f"  [Síntesis] Extrayendo 5 preguntas estructuradas con {MODELO_LLM}...", end="", flush=True)

    prompt_sistema = (
        "Eres un profesor técnico y pedagógico especializado en ciclos formativos de Desarrollo "
        "de Aplicaciones Web (DAW). Diseña preguntas formativas rigurosas y desafiantes basadas "
        "estrictamente en los apuntes de la clase proporcionados.\n\n"
        "DIRECTIVAS ESTRICTAS:\n"
        "- Genera exactamente 5 preguntas tipo test de opción múltiple.\n"
        "- Cada pregunta debe tener exactamente 4 opciones en el array 'opciones'.\n"
        "- El campo 'correcta' debe ser el índice entero (0, 1, 2 o 3) de la respuesta correcta.\n"
        "- El campo 'tipo' debe ser una etiqueta como 'conceptual', 'codigo' o 'analisis'.\n"
        "- Si la pregunta evalúa código, incluye el bloque en 'codigo'. Si no aplica, usa cadena vacía \"\".\n"
        "- 'explicacion' debe detallar pedagógicamente por qué la opción correcta es la adecuada y alertar sobre errores comunes.\n"
        "- PROHIBIDO inventar conceptos, métodos o sintaxis no contenidos en los apuntes."
    )

    prompt_usuario = (
        f"A partir de los siguientes apuntes de la materia '{materia}' y clase '{clase}', "
        f"genera un banco de exactamente 5 preguntas de evaluación activa en formato JSON conforme al esquema:\n\n"
        f"---\nAPUNTES:\n{texto_apuntes[:24000]}"
    )

    options_quiz = {
        "num_ctx": 8192,
        "temperature": 0.3,
    }

    try:
        respuesta = ollama.chat(
            model=MODELO_LLM,
            format=SCHEMA_PREGUNTAS,
            options=options_quiz,
            keep_alive=0,  # IMPORTANTE: Descargar modelo tras esta última llamada
            messages=[
                {"role": "system", "content": prompt_sistema},
                {"role": "user", "content": prompt_usuario},
            ],
        )
        print(" completado.")
    except Exception as exc:
        print(f" fallo en llamada al modelo: {exc}")
        descargar_modelo_ollama(MODELO_LLM)
        raise

    mensaje = respuesta.get("message") if isinstance(respuesta, dict) else getattr(respuesta, "message", None)
    if mensaje is None:
        descargar_modelo_ollama(MODELO_LLM)
        raise RuntimeError("La respuesta de Ollama no contiene el campo 'message'.")

    contenido = mensaje.get("content") if isinstance(mensaje, dict) else getattr(mensaje, "content", "")
    if not contenido or not contenido.strip():
        descargar_modelo_ollama(MODELO_LLM)
        raise RuntimeError("El modelo devolvió un contenido vacío al generar preguntas.")

    try:
        datos = json.loads(contenido)
    except json.JSONDecodeError as err:
        descargar_modelo_ollama(MODELO_LLM)
        raise ValueError(f"Fallo al decodificar el JSON de preguntas devuelto por Ollama: {err}")

    preguntas_raw = datos.get("preguntas", []) if isinstance(datos, dict) else []
    if not preguntas_raw and isinstance(datos, list):
        preguntas_raw = datos

    fecha_creacion = datetime.now().isoformat()
    materia_str = materia.strip()
    clase_str = clase.strip()

    preguntas_limpias: list[dict] = []
    for idx, p in enumerate(preguntas_raw):
        if not isinstance(p, dict):
            continue

        texto_p = str(p.get("pregunta", "")).strip().lower()
        id_estirpe = hashlib.sha1(
            f"{materia_str.lower()}/{clase_str.lower()}/{texto_p}".encode("utf-8")
        ).hexdigest()[:10]

        opciones_raw = p.get("opciones", [])
        if not isinstance(opciones_raw, list):
            opciones_raw = [str(opciones_raw)]
        opciones = [str(opt).strip() for opt in opciones_raw]

        while len(opciones) < 4:
            opciones.append("N/A")
        opciones = opciones[:4]

        try:
            correcta_val = int(p.get("correcta", 0))
            if correcta_val < 0 or correcta_val >= len(opciones):
                correcta_val = 0
        except (ValueError, TypeError):
            correcta_val = 0

        pregunta_item = {
            "id": id_estirpe,
            "materia": materia_str,
            "clase": clase_str,
            "fecha_creacion": fecha_creacion,
            "tipo": str(p.get("tipo", "conceptual")).strip(),
            "pregunta": str(p.get("pregunta", "")).strip(),
            "codigo": str(p.get("codigo", "") or "").strip(),
            "opciones": opciones,
            "correcta": correcta_val,
            "explicacion": str(p.get("explicacion", "")).strip(),
        }
        preguntas_limpias.append(pregunta_item)

    preguntas_finales = preguntas_limpias[:5]
    print(f"  [QUIZ] {len(preguntas_finales)} preguntas generadas y validadas con éxito.")
    return preguntas_finales


# ---------------------------------------------------------------------------
# 6. Pipeline principal
# ---------------------------------------------------------------------------
def generar_material_estudio(
    ruta_transcripcion: str = "transcripcion.txt",
    ruta_salida: str = "apuntes.md",
    guardar_bloques_crudos: bool = True,
):
    if not os.path.exists(ruta_transcripcion):
        print(f"Error: No se encuentra el archivo '{ruta_transcripcion}'.")
        return

    print(f"--- Leyendo transcripción: {ruta_transcripcion} ---")
    with open(ruta_transcripcion, "r", encoding="utf-8") as f:
        texto_clase = f.read()

    if not texto_clase.strip():
        print("Error: El archivo de transcripción está vacío.")
        return

    bloques_transcripcion = dividir_transcripcion(texto_clase, max_chars=9000)
    total_bloques = len(bloques_transcripcion)
    print(f"--- Transcripción estructurada en {total_bloques} bloque(s) de ~9000 caracteres ---")

    apuntes_por_bloque = []
    contenido_parcial = ""  # [M-3] Captura salida parcial del Caso A para preservarla en TruncationError

    try:
        # Caso A: Fragmentos cortos
        if total_bloques == 1:
            print("-> Procesando clase completa en bloque único...")
            prompt = construir_prompt_clase_unica(bloques_transcripcion[0])
            contenido_final = llamar_modelo_seguro(prompt, OPTIONS_UNIFICACION)
            contenido_parcial = contenido_final  # [M-3] Preservar por si el paso posterior falla

        # Caso B: Clases largas de 40 a 60 minutos (Map-Reduce)
        else:
            for i, fragmento in enumerate(bloques_transcripcion, start=1):
                print(f"\n[Bloque {i}/{total_bloques}]")
                prompt = construir_prompt_bloque(fragmento, i, total_bloques)
                resultado = llamar_modelo_seguro(prompt, OPTIONS_BLOQUE)
                apuntes_por_bloque.append(resultado)

            if guardar_bloques_crudos:
                base, _ = os.path.splitext(ruta_salida)
                ruta_crudos = f"{base}_bloques_raw.md"
                with open(ruta_crudos, "w", encoding="utf-8") as f:
                    f.write("\n\n---BLOQUE SIGUIENTE---\n\n".join(apuntes_por_bloque))
                print(f"\n--- Bloques crudos guardados en: {ruta_crudos} ---")

            print("\n--- Unificando bloques en un único documento definitivo ---")
            # [Mejora 2] Tree-Reduce jerárquico: maneja clases de hasta 2 h sin fallback plano
            contenido_final = unificar_apuntes_jerarquico(apuntes_por_bloque)

        # Limpieza previa al guardado: eliminar marcas residuales tipo (Verificar...) y pies de página redundantes
        contenido_final = limpiar_apuntes_previo_guardado(contenido_final)

        # Validación sintáctica en consola
        contenido_final = validar_timestamps(contenido_final)

        # La sección de examen (generar_seccion_examen) se ha retirado: duplicaba
        # definiciones y ya está cubierta por las secciones 5 y 6 de la estructura.

        # Salvaguarda contra sobreescritura silenciosa (I-7)
        if os.path.exists(ruta_salida):
            timestamp_bak = datetime.now().strftime("%Y%m%d-%H%M%S")
            ruta_bak = f"{ruta_salida}.bak-{timestamp_bak}"
            shutil.copy2(ruta_salida, ruta_bak)
            print(f"📦 Backup preventivo creado: '{ruta_bak}'")

        # Cabecera con formato estrictamente académico (pie de página retirado)
        p_salida = Path(ruta_salida).resolve()
        materia_acad = "DAW"
        if len(p_salida.parts) >= 3 and p_salida.parts[-3] == "clases":
            materia_acad = p_salida.parts[-2].replace("_", " ").title()
        elif len(p_salida.parents) >= 2:
            materia_acad = p_salida.parent.parent.name.replace("_", " ").title()

        fecha_acad = datetime.now().strftime("%d/%m/%Y")
        cabecera_acad = f"> 🏛️ **Registro de clase** • {materia_acad} • {fecha_acad}\n\n"

        if not contenido_final.startswith("> 🏛️ **Registro de clase**"):
            contenido_final = cabecera_acad + contenido_final.lstrip()

        # Guardado del resultado final
        with open(ruta_salida, "w", encoding="utf-8") as f:
            f.write(contenido_final)

        print(f"\n🎉 ¡Apuntes finalizados! Guardados en: {ruta_salida}")

        # Auditoría automática de fidelidad
        base, _ = os.path.splitext(ruta_salida)
        ruta_informe = f"{base}_auditoria.md"
        auditar_apuntes(texto_clase, contenido_final, ruta_informe)

    except TruncationError as e:
        base, ext = os.path.splitext(ruta_salida)
        ruta_incompleta = f"{base}_TRUNCADO{ext}"

        with open(ruta_incompleta, "w", encoding="utf-8") as f:
            f.write("# ⚠️ ARCHIVO INCOMPLETO POR LÍMITE DE TOKENS\n\n")
            if apuntes_por_bloque:
                f.write("\n\n---BLOQUE PARCIAL---\n\n".join(apuntes_por_bloque))
            elif contenido_parcial:  # [M-3] Caso A: preservar salida del bloque único si existe
                f.write(contenido_parcial)

        print(f"\n❌ ERROR CRÍTICO: {e}")
        print(f"📁 El material parcial generado se ha preservado en: {ruta_incompleta}")
        descargar_modelo_ollama(MODEL)
        sys.exit(1)
    except Exception:
        descargar_modelo_ollama(MODEL)
        raise


if __name__ == "__main__":
    archivo_entrada = sys.argv[1] if len(sys.argv) > 1 else "transcripcion.txt"
    archivo_salida = sys.argv[2] if len(sys.argv) > 2 else "apuntes.md"
    generar_material_estudio(archivo_entrada, archivo_salida)