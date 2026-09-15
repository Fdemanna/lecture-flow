import os
import re
import sys
import ollama

MODEL = "qwen2.5:7b"

OPTIONS_BLOQUE = {
    "temperature": 0.15,
    "num_ctx": 16384,
    "num_predict": 3072,
}

OPTIONS_UNIFICACION = {
    "temperature": 0.1,
    "num_ctx": 16384,
    "num_predict": 4096,
}

SYSTEM_PROMPT = (
    "Eres un asistente pedagógico técnico especializado en el ciclo formativo de "
    "Desarrollo de Aplicaciones Web (DAW). Tu tarea es transformar transcripciones de "
    "clases técnicas en material de estudio estructurado, riguroso y en Markdown, "
    "siguiendo con precisión milimétrica las directivas de fidelidad a la fuente, "
    "timestamps y delimitación de ejemplos."
)

REGLAS_MAESTRAS = """
INSTRUCCIONES Y REGLAS ESTRICTAS:

1. **Fuente única de verdad**: Usa exclusivamente la información contenida en la transcripción. No inventes ni completes con conocimiento externo salvo nota aclaratoria explícita. Si falta información o se corta, usa "❓ Contenido incompleto en este fragmento".
2. **Estructura**: Usa encabezados (##, ###), listas, tablas o esquemas para ordenar el contenido.
3. **Ejemplos del profesor**: Conserva casos concretos (valores específicos, nombres reales, ejercicios) en bloques individuales:
   > 📌 **Ejemplo del profesor** [HH:MM:SS–HH:MM:SS]:
   NO marques como ejemplo meras repeticiones teóricas. Conserva los datos tal cual los dio.
4. **Consejos y advertencias**: Destaca trampas, buenas prácticas o errores en bloques individuales:
   > ⚠️ **Consejos del profesor** [HH:MM:SS–HH:MM:SS]: [explicación]
5. **PROHIBIDO INVENTAR CÓDIGO O SINTAXIS**: Si el profesor usa una herramienta visual (como Raptor, Scratch, diagramas de flujo) y NO escribe código textual, NO lo traduzcas a Python, JS ni otro lenguaje. Describe el procedimiento tal cual (símbolos, clics, campos 'Set'/'To'). No inventes operadores ni sintaxis (como ':=') que no aparezcan literalmente.
6. **UN EJEMPLO = UN BLOQUE**: Cada ejemplo o consejo debe tener su propio bloque '📌' o '⚠️' individual con su timestamp específico y ajustado al momento exacto en que ocurre. No agrupes ideas distintas bajo rangos de tiempo inflados.
7. **Sin relleno duplicado**: Prohibido repetir la misma idea como alternativas distintas en listas o pasos. Cada punto debe aportar un dato nuevo.
8. **Glosario con definiciones reales**: Todo término técnico listado debe incluir una definición concisa basada en lo explicado, nunca el término suelto.
"""

class TruncationError(Exception):
    pass

def dividir_transcripcion(texto: str, max_chars: int = 9000) -> list[str]:
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

def construir_prompt_bloque(fragmento: str, num_bloque: int, total_bloques: int) -> str:
    return f"""
Transforma el siguiente fragmento ({num_bloque} de {total_bloques}) de clase técnica en apuntes rigurosos.

{REGLAS_MAESTRAS}

Al final de este fragmento, añade una sección:
### Términos clave (Bloque {num_bloque})
(Término: definición breve explicada por el profesor).

---
FRAGMENTO DE TRANSCRIPCIÓN:
{fragmento}
"""

def construir_prompt_clase_unica(transcripcion: str) -> str:
    return f"""
Transforma la transcripción de esta clase técnica en un documento de estudio exhaustivo y profesional en Markdown.

{REGLAS_MAESTRAS}

ESTRUCTURA OBLIGATORIA DEL DOCUMENTO:
# 📖 Apuntes: [Título deducido de la clase]
## 📑 Índice de Contenidos
## 🧩 Desarrollo de Bloques Temáticos (con subtítulos ###, tablas y citas puntuales)
## 🔑 Glosario de Términos Clave (con definiciones reales de una frase)
## 🧠 Preguntas de Repaso (3 a 5 preguntas de evaluación basadas solo en la clase, con respuestas explicadas al final)

---
TRANSCRIPCIÓN COMPLETA:
{transcripcion}
"""

def construir_prompt_unificacion(apuntes_por_bloque: list[str]) -> str:
    apuntes_concatenados = "\n\n---SIGUIENTE SECCIÓN---\n\n".join(apuntes_por_bloque)

    return f"""
A continuación tienes los apuntes generados a partir de fragmentos consecutivos de UNA MISMA clase de DAW. 
Únelos en un único documento definitivo y coherente.

REGLAS DE UNIFICACIÓN:
1. Crea un Título representativo y un Índice general numerado.
2. Une el desarrollo temático eliminando redundancias, pero MANTÉN INTACTOS todos los bloques '> 📌 **Ejemplo del profesor**' y '> ⚠️ **Consejos del profesor**' con sus timestamps exactos. Prohibido resumirlos o eliminarlos.
3. Respeta la regla de NO inventar código textual si la herramienta era visual (Raptor, diagramas).
4. Consolida un único '## 🔑 Glosario Unificado de Términos Clave' asegurando que cada término tenga su definición clara.
5. Genera al final una sección '## 🧠 Preguntas de Repaso' (4-5 preguntas tipo test y cortas) con soluciones justificadas.

---
APUNTES A UNIFICAR:
{apuntes_concatenados}
"""

def llamar_modelo_seguro(prompt_usuario: str, options: dict) -> str:
    print("  [LLM] Procesando con Qwen 2.5 en local...", end="", flush=True)
    respuesta = ollama.chat(
        model=MODEL,
        options=options,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt_usuario},
        ],
    )
    print(" completado.")

    done_reason = respuesta.get("done_reason") or getattr(respuesta, "done_reason", None)
    contenido = respuesta["message"]["content"]

    if done_reason == "length":
        raise TruncationError("La generación fue cortada abruptamente al agotarse el límite de tokens/contexto.")

    lineas = contenido.strip().split("\n")
    if lineas:
        ultima_linea = lineas[-1]
        if ultima_linea.startswith("###") and not ultima_linea.endswith((".", ":", "]", ")")):
            print(f"\n⚠️ Aviso: posible corte estructural al final detectado: '{ultima_linea}'")

    return contenido

def validar_timestamps(contenido: str) -> str:
    lineas = contenido.split("\n")
    marcadores = ("📌", "⚠️")
    sin_timestamp = []

    for i, linea in enumerate(lineas, start=1):
        if any(m in linea for m in marcadores):
            if not re.search(r"\[\d{2}:\d{2}:\d{2}", linea):
                sin_timestamp.append((i, linea.strip()))

    if sin_timestamp:
        print(f"\n⚠️ Aviso: {len(sin_timestamp)} bloque(s) sin timestamp detectado(s):")
        for num_linea, texto in sin_timestamp[:5]:
            print(f"   - Línea {num_linea}: {texto[:70]}...")
    else:
        print("\n✅ Validación sintáctica: todas las citas incluyen marca de tiempo.")

    return contenido

def auditar_apuntes(texto_transcripcion: str, apuntes_generados: str, ruta_auditoria: str = "auditoria.md"):
    print("\n--- Ejecutando auditoría de alucinaciones y fidelidad técnica ---")
    
    prompt_auditoria = f"""
Aquí tienes la transcripción ORIGINAL de la clase y unos apuntes generados a partir de ella.
Compara ambos minuciosamente y señala CUALQUIER afirmación, sintaxis de código, operador (ej. :=, let, var),
símbolo o dato concreto en los apuntes que NO aparezca de forma explícita o equivalente en la transcripción.

REGLAS DE REVISIÓN:
- Marca cada problema con "🚩 POSIBLE ALUCINACIÓN: [línea o sección]" seguido de una justificación breve.
- Presta especial atención a si se inventó código escrito cuando el profesor usaba herramientas visuales (como diagramas de flujo o Raptor).
- Revisa si hay timestamps con rangos de tiempo inventados.
- Si no encuentras inconsistencias o datos inventados, responde únicamente: "✅ Sin alucinaciones detectadas. El documento es 100% fiel a la transcripción."
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
        
        if "🚩 POSIBLE ALUCINACIÓN" in reporte:
            print(f"⚠️ Se detectaron discrepancias. Revisa el informe en: {ruta_auditoria}")
        else:
            print(f"✅ Auditoría limpia. Informe guardado en: {ruta_auditoria}")
            
    except Exception as e:
        print(f"Error durante la fase de auditoría: {e}")

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

    try:
        if total_bloques == 1:
            print("-> Procesando clase completa en bloque único...")
            prompt = construir_prompt_clase_unica(bloques_transcripcion[0])
            contenido_final = llamar_modelo_seguro(prompt, OPTIONS_UNIFICACION)
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
            prompt_unificacion = construir_prompt_unificacion(apuntes_por_bloque)
            try:
                contenido_final = llamar_modelo_seguro(prompt_unificacion, OPTIONS_UNIFICACION)
            except Exception as e:
                print(f"Aviso en unificación: {e}. Se mantendrán los bloques concatenados.")
                contenido_final = "\n\n---\n\n".join(apuntes_por_bloque)

        contenido_final = validar_timestamps(contenido_final)

        with open(ruta_salida, "w", encoding="utf-8") as f:
            f.write(contenido_final)

        print(f"\n🎉 ¡Apuntes finalizados! Guardados en: {ruta_salida}")

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
        
        print(f"\n❌ ERROR CRÍTICO: {e}")
        print(f"📁 El material parcial generado se ha preservado en: {ruta_incompleta}")
        sys.exit(1)

if __name__ == "__main__":
    archivo_entrada = sys.argv[1] if len(sys.argv) > 1 else "transcripcion.txt"
    archivo_salida = sys.argv[2] if len(sys.argv) > 2 else "apuntes.md"
    generar_material_estudio(archivo_entrada, archivo_salida)