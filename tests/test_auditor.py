"""
Suite de tests unitarios para src/auditor.py.

Cubre:
  1. Caso feliz (Markdown bien cerrado, timestamps ordenados y válidos).
  2. Bloque de código desbalanceado (número impar de ```).
  3. Etiquetas <details> sin cerrar.
  4. Timestamps desordenados.
  5. Timestamp que excede la duración máxima permitida.
  6. Cálculo de cobertura de términos clave (ok y por debajo del umbral).
"""
from __future__ import annotations

import pytest
from src.auditor import auditar_apuntes, ResultadoAuditoria


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

APUNTES_OK = """\
# Tema 1: Introducción a las Bases de Datos

[00:01:30] Se presenta el concepto de **base de datos**.

## ¿Qué es una base de datos?

Un sistema organizado para almacenar y recuperar información.

```sql
SELECT * FROM usuarios WHERE activo = 1;
```

[00:05:00] Se introduce el modelo relacional.

<details>
<summary>Autoevaluación</summary>

¿Cuántos tipos de bases de datos existen?

</details>

[00:10:00] Resumen de conceptos clave.
"""


# ---------------------------------------------------------------------------
# Test 1: Caso feliz
# ---------------------------------------------------------------------------

def test_caso_feliz():
    """Apuntes correctos → es_valido=True, sin errores, 3 timestamps."""
    resultado = auditar_apuntes(
        APUNTES_OK,
        duracion_maxima_segundos=3600,
        terminos_esperados=["base de datos", "relacional", "sql"],
    )

    assert isinstance(resultado, ResultadoAuditoria)
    assert resultado.es_valido is True
    assert resultado.errores == []
    assert resultado.timestamps_detectados == 3
    assert resultado.cobertura_terminos == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# Test 2: Bloque de código desbalanceado (``` impar)
# ---------------------------------------------------------------------------

def test_bloque_codigo_desbalanceado():
    """Un ``` sin cerrar → error en errores, es_valido=False."""
    apuntes_mal = """\
# Clase 2

[00:02:00] Ejemplo de código:

```python
def hola():
    print("Hola")

Sin cerrar el bloque anterior.
"""
    resultado = auditar_apuntes(apuntes_mal)

    assert resultado.es_valido is False
    assert any("```" in e for e in resultado.errores), (
        f"Se esperaba error de backticks, obtenido: {resultado.errores}"
    )


# ---------------------------------------------------------------------------
# Test 3: Etiqueta <details> sin cerrar
# ---------------------------------------------------------------------------

def test_details_sin_cerrar():
    """<details> sin </details> → error detectado, es_valido=False."""
    apuntes_mal = """\
[00:03:00] Autoevaluación:

<details>
<summary>Pregunta</summary>
Respuesta aquí.
"""
    resultado = auditar_apuntes(apuntes_mal)

    assert resultado.es_valido is False
    assert any("details" in e.lower() for e in resultado.errores), (
        f"Se esperaba error de <details>, obtenido: {resultado.errores}"
    )


# ---------------------------------------------------------------------------
# Test 4: Timestamps desordenados
# ---------------------------------------------------------------------------

def test_timestamps_desordenados():
    """Timestamps que retroceden en el tiempo → error cronológico."""
    apuntes_mal = """\
[00:05:00] Primer punto.
[00:10:00] Segundo punto.
[00:08:00] ← Este timestamp retrocede en el tiempo.
[00:15:00] Cuarto punto.
"""
    resultado = auditar_apuntes(apuntes_mal)

    assert resultado.es_valido is False
    assert any("orden" in e.lower() or "cronológico" in e.lower() for e in resultado.errores), (
        f"Se esperaba error de orden cronológico, obtenido: {resultado.errores}"
    )
    assert resultado.timestamps_detectados == 4


# ---------------------------------------------------------------------------
# Test 5: Timestamp fuera de rango (excede duración máxima)
# ---------------------------------------------------------------------------

def test_timestamp_fuera_de_rango():
    """Timestamp que excede duracion_maxima_segundos → error de rango."""
    apuntes_mal = """\
[00:01:00] Inicio de clase.
[01:30:00] Este timestamp excede la duración de 60 minutos.
"""
    # Duración máxima: 60 minutos = 3600 s
    resultado = auditar_apuntes(apuntes_mal, duracion_maxima_segundos=3600)

    assert resultado.es_valido is False
    assert any("excede" in e.lower() or "duración" in e.lower() for e in resultado.errores), (
        f"Se esperaba error de duración, obtenido: {resultado.errores}"
    )


# ---------------------------------------------------------------------------
# Test 6a: Cobertura de términos suficiente (≥ 60 %)
# ---------------------------------------------------------------------------

def test_cobertura_terminos_suficiente():
    """Cuando se cubren todos los términos, no debe haber advertencias de cobertura."""
    apuntes = "[00:01:00] Se explica la herencia, el polimorfismo y la encapsulación en POO."
    resultado = auditar_apuntes(
        apuntes,
        terminos_esperados=["herencia", "polimorfismo", "encapsulación"],
    )

    assert resultado.cobertura_terminos == pytest.approx(1.0)
    assert not any("cobertura" in a.lower() for a in resultado.advertencias)


# ---------------------------------------------------------------------------
# Test 6b: Cobertura de términos insuficiente (< 60 %)
# ---------------------------------------------------------------------------

def test_cobertura_terminos_insuficiente():
    """Cuando faltan términos clave, se emite una advertencia de cobertura."""
    apuntes = "[00:01:00] Solo se menciona la herencia en esta clase."
    resultado = auditar_apuntes(
        apuntes,
        terminos_esperados=["herencia", "polimorfismo", "encapsulación", "interfaz", "abstracción"],
    )

    # 1 de 5 términos → 20 % < 60 %
    assert resultado.cobertura_terminos == pytest.approx(1 / 5)
    assert any("cobertura" in a.lower() for a in resultado.advertencias), (
        f"Se esperaba advertencia de cobertura, obtenidas: {resultado.advertencias}"
    )


# ---------------------------------------------------------------------------
# Test 7: Sin timestamps → advertencia pero no error
# ---------------------------------------------------------------------------

def test_sin_timestamps_advertencia():
    """Sin timestamps se genera una advertencia (no error) y es_valido puede ser True."""
    apuntes = "# Clase sin timestamps\n\nContenido sin marcas temporales.\n"
    resultado = auditar_apuntes(apuntes)

    assert resultado.timestamps_detectados == 0
    assert any("timestamp" in a.lower() for a in resultado.advertencias)
    # Si no hay otros errores, es_valido debe ser True
    assert resultado.es_valido is True
