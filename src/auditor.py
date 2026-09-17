"""
Módulo de auditoría determinista para apuntes generados por LectureFlow.

Sustituye el critic-loop del LLM por reglas duras y reproducibles:
  - Validación de bloques de código Markdown (delimitadores par).
  - Balance estricto de etiquetas <details> / </details>.
  - Orden cronológico y rango válido de timestamps [HH:MM:SS].
  - Cobertura de términos esperados.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Tipos de datos
# ---------------------------------------------------------------------------

@dataclass
class ResultadoAuditoria:
    """Resultado determinista de la auditoría de apuntes."""

    es_valido: bool
    errores: list[str]
    advertencias: list[str]
    timestamps_detectados: int
    cobertura_terminos: float


# ---------------------------------------------------------------------------
# Constantes internas
# ---------------------------------------------------------------------------

_RE_TIMESTAMP = re.compile(r"\[(\d{2}):(\d{2}):(\d{2})\]")
_UMBRAL_COBERTURA = 0.60  # Advertir si la cobertura es inferior al 60 %


# ---------------------------------------------------------------------------
# Función principal
# ---------------------------------------------------------------------------

def auditar_apuntes(
    texto_apuntes: str,
    duracion_maxima_segundos: int | None = None,
    terminos_esperados: list[str] | None = None,
) -> ResultadoAuditoria:
    """Valida de forma determinista un texto de apuntes Markdown.

    Parámetros
    ----------
    texto_apuntes:
        Texto completo de los apuntes en formato Markdown.
    duracion_maxima_segundos:
        Si se indica, cualquier timestamp que lo supere genera un error crítico.
    terminos_esperados:
        Lista de palabras clave; se advierte si la cobertura es < 60 %.

    Devuelve
    --------
    ResultadoAuditoria con el veredicto y los detalles encontrados.
    """
    errores: list[str] = []
    advertencias: list[str] = []

    # ------------------------------------------------------------------
    # A) Bloques de código Markdown: el número de ``` debe ser par
    # ------------------------------------------------------------------
    num_backticks = texto_apuntes.count("```")
    if num_backticks % 2 != 0:
        errores.append(
            f"Bloques de código desbalanceados: se detectaron {num_backticks} "
            "delimitadores '```' (se esperaba un número par)."
        )

    # ------------------------------------------------------------------
    # B) Etiquetas de autoevaluación: balance estricto <details>/<details>
    # ------------------------------------------------------------------
    num_open = len(re.findall(r"<details\b[^>]*>", texto_apuntes, re.IGNORECASE))
    num_close = len(re.findall(r"</details>", texto_apuntes, re.IGNORECASE))
    if num_open != num_close:
        errores.append(
            f"Etiquetas <details> desbalanceadas: {num_open} aperturas vs "
            f"{num_close} cierres '</details>'."
        )

    # ------------------------------------------------------------------
    # C) Timestamps: orden cronológico y rango válido
    # ------------------------------------------------------------------
    coincidencias = _RE_TIMESTAMP.findall(texto_apuntes)
    timestamps_detectados = len(coincidencias)

    if timestamps_detectados == 0:
        advertencias.append(
            "No se detectó ningún timestamp [HH:MM:SS] en los apuntes. "
            "Considera añadir marcas temporales de referencia."
        )
    else:
        # Convertir a segundos totales
        segundos: list[int] = [
            int(h) * 3600 + int(m) * 60 + int(s)
            for h, m, s in coincidencias
        ]

        # Orden no decreciente
        for i in range(1, len(segundos)):
            if segundos[i] < segundos[i - 1]:
                errores.append(
                    f"Timestamps fuera de orden cronológico: "
                    f"[{coincidencias[i-1][0]}:{coincidencias[i-1][1]}:{coincidencias[i-1][2]}] "
                    f"→ [{coincidencias[i][0]}:{coincidencias[i][1]}:{coincidencias[i][2]}] "
                    f"(posición {i})."
                )

        # Rango respecto a la duración máxima
        if duracion_maxima_segundos is not None:
            for idx, (ts_seg, ts_raw) in enumerate(zip(segundos, coincidencias)):
                if ts_seg > duracion_maxima_segundos:
                    horas = duracion_maxima_segundos // 3600
                    minutos = (duracion_maxima_segundos % 3600) // 60
                    segs = duracion_maxima_segundos % 60
                    errores.append(
                        f"Timestamp [{ts_raw[0]}:{ts_raw[1]}:{ts_raw[2]}] (posición {idx}) "
                        f"excede la duración máxima "
                        f"[{horas:02d}:{minutos:02d}:{segs:02d}]."
                    )

    # ------------------------------------------------------------------
    # D) Cobertura de términos esperados
    # ------------------------------------------------------------------
    cobertura_terminos: float = 1.0  # Por defecto, 100 % si no hay lista

    if terminos_esperados:
        texto_lower = texto_apuntes.lower()
        presentes = sum(
            1 for termino in terminos_esperados if termino.lower() in texto_lower
        )
        cobertura_terminos = presentes / len(terminos_esperados)
        if cobertura_terminos < _UMBRAL_COBERTURA:
            advertencias.append(
                f"Cobertura de términos clave insuficiente: "
                f"{cobertura_terminos:.0%} ({presentes}/{len(terminos_esperados)} términos). "
                f"Se esperaba al menos {_UMBRAL_COBERTURA:.0%}."
            )

    # ------------------------------------------------------------------
    # Veredicto final
    # ------------------------------------------------------------------
    es_valido = len(errores) == 0

    return ResultadoAuditoria(
        es_valido=es_valido,
        errores=errores,
        advertencias=advertencias,
        timestamps_detectados=timestamps_detectados,
        cobertura_terminos=cobertura_terminos,
    )
