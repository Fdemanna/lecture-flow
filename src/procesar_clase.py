"""
Orquestador de clases DAW.
Organiza la jerarquía de carpetas por materia y clase,
y encadena la transcripción (MLX/Whisper) con la generación de apuntes (Ollama).

Uso interactivo:
    python procesar_clase.py

Uso directo por argumentos:
    python procesar_clase.py "Programacion" "Clase_02_Condicionales" ruta/video.mp4

Flags opcionales (se añaden al final de los argumentos posicionales):
    --solo-apuntes          Omite Whisper y usa transcripcion.txt existente.
    --forzar-transcripcion  Sobrescribe transcripción y apuntes existentes.
"""

import os
from pathlib import Path
import sys
import shutil
import subprocess

# Importación robusta: funciona tanto cuando se invoca como módulo (from src.procesar_clase …)
# como cuando se ejecuta directamente como script (python src/procesar_clase.py).
try:
    from src.auditor import auditar_apuntes
except ModuleNotFoundError:
    _ROOT = Path(__file__).resolve().parent.parent
    if str(_ROOT) not in sys.path:
        sys.path.insert(0, str(_ROOT))
    from src.auditor import auditar_apuntes

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT_DIR = Path(__file__).resolve().parent.parent
CARPETA_BASE = str(ROOT_DIR / "clases")

def normalizar_nombre(texto: str) -> str:
    """Elimina caracteres problemáticos para carpetas del sistema."""
    caracteres_validos = "-_.() abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    limpio = "".join(c for c in texto if c in caracteres_validos)
    return limpio.strip().replace(" ", "_")


def _ejecutar_auditoria(ruta_apuntes: str) -> None:
    """Lee el archivo de apuntes y emite el resultado de la auditoría por consola."""
    print("\n" + "="*50)
    print("[FASE 3] Auditoría determinista de apuntes")
    print("="*50)

    if not os.path.exists(ruta_apuntes):
        print("[AUDITORÍA] No se encontró el archivo de apuntes para auditar.",
              file=sys.stderr)
        return

    with open(ruta_apuntes, "r", encoding="utf-8") as _f:
        _texto_apuntes = _f.read()

    _resultado = auditar_apuntes(_texto_apuntes)

    if not _resultado.es_valido:
        print("\n[AUDITORÍA] ⚠️  Se detectaron errores críticos en los apuntes:",
              file=sys.stderr)
        for _err in _resultado.errores:
            print(f"  ✗ {_err}", file=sys.stderr)
    else:
        print("[AUDITORÍA] ✔ Apuntes validados correctamente.")

    if _resultado.advertencias:
        print("\n[AUDITORÍA] 💡 Advertencias:")
        for _adv in _resultado.advertencias:
            print(f"  ⚠  {_adv}")

    print(f"[AUDITORÍA] Timestamps detectados : {_resultado.timestamps_detectados}")
    print(f"[AUDITORÍA] Cobertura de términos : {_resultado.cobertura_terminos:.0%}")


def ejecutar_pipeline(
    materia: str,
    nombre_clase: str,
    ruta_archivo_origen: str,
    solo_apuntes: bool = False,
    forzar_transcripcion: bool = False,
) -> None:
    """Orquesta el pipeline completo o parcial según las banderas indicadas.

    Parámetros
    ----------
    materia:
        Nombre de la asignatura (se normaliza automáticamente).
    nombre_clase:
        Nombre o tema de la clase.
    ruta_archivo_origen:
        Ruta al archivo multimedia de entrada.
    solo_apuntes:
        Si True, omite Whisper y reutiliza ``transcripcion.txt`` existente.
        Lanza error si el archivo de transcripción no existe.
    forzar_transcripcion:
        Si True, re-ejecuta Whisper aunque ``transcripcion.txt`` ya exista,
        sobrescribiendo tanto la transcripción como los apuntes anteriores.
    """
    # ------------------------------------------------------------------
    # 1. Preparar nombres y rutas
    # ------------------------------------------------------------------
    materia_clean = normalizar_nombre(materia)
    clase_clean = normalizar_nombre(nombre_clase)
    directorio_destino = os.path.join(CARPETA_BASE, materia_clean, clase_clean)

    # [M-4] Verificar contención estricta de la ruta destino dentro de CARPETA_BASE
    carpeta_base_real = os.path.realpath(CARPETA_BASE)
    if not os.path.realpath(directorio_destino).startswith(carpeta_base_real + os.sep):
        print("Error: Ruta de destino inválida. Intento de escape fuera del directorio de clases detectado.")
        return

    ruta_transcripcion = os.path.join(directorio_destino, "transcripcion.txt")
    ruta_apuntes = os.path.join(directorio_destino, "apuntes.md")

    # ------------------------------------------------------------------
    # 2. Modo --solo-apuntes: saltar validación del archivo multimedia
    # ------------------------------------------------------------------
    if solo_apuntes:
        print("\n[MODO] --solo-apuntes: se omite la fase Whisper.")
        if not os.path.exists(ruta_transcripcion) or os.path.getsize(ruta_transcripcion) == 0:
            print(
                f"Error: No se encontró 'transcripcion.txt' en '{directorio_destino}'.\n"
                "Ejecuta primero el pipeline completo o usa --forzar-transcripcion.",
                file=sys.stderr,
            )
            return
        print(f"[INFO] Se reutiliza 'transcripcion.txt' existente ({os.path.getsize(ruta_transcripcion):,} bytes).")
    else:
        # Modo normal o --forzar-transcripcion: necesitamos el archivo multimedia
        if not os.path.exists(ruta_archivo_origen):
            print(f"Error: El archivo de entrada '{ruta_archivo_origen}' no existe.")
            return

        # [M-4] Validar que el archivo de origen sea un formato multimedia permitido
        EXTENSIONES_PERMITIDAS = (".mp4", ".mkv", ".mov", ".avi", ".mp3", ".m4a", ".wav")
        if not ruta_archivo_origen.lower().endswith(EXTENSIONES_PERMITIDAS):
            print(
                f"Error: Tipo de archivo no permitido '{os.path.basename(ruta_archivo_origen)}'. "
                f"Solo se aceptan: {', '.join(EXTENSIONES_PERMITIDAS)}"
            )
            return

        os.makedirs(directorio_destino, exist_ok=True)
        print(f"\n[DIR] Carpeta de trabajo lista: {directorio_destino}")

        # Copiar o mover el archivo de entrada a la carpeta correspondiente
        nombre_archivo = os.path.basename(ruta_archivo_origen)
        ruta_archivo_en_carpeta = os.path.join(directorio_destino, nombre_archivo)
        if not os.path.exists(ruta_archivo_en_carpeta):
            print("-> Copiando archivo multimedia a la carpeta de la clase...")
            shutil.copy2(ruta_archivo_origen, ruta_archivo_en_carpeta)

        # ------------------------------------------------------------------
        # FASE 1: Transcripción (Whisper)
        # ------------------------------------------------------------------
        transcripcion_previa = (
            os.path.exists(ruta_transcripcion) and os.path.getsize(ruta_transcripcion) > 0
        )

        if transcripcion_previa and not forzar_transcripcion:
            print("\n[FASE 1] Transcripción omitida: se reutiliza 'transcripcion.txt' existente.")
        else:
            if forzar_transcripcion and transcripcion_previa:
                print("\n[MODO] --forzar-transcripcion: sobrescribiendo transcripción y apuntes existentes.")
                # Eliminar apuntes previos para que no queden desincronizados
                if os.path.exists(ruta_apuntes):
                    os.remove(ruta_apuntes)
                    print("[INFO] 'apuntes.md' previos eliminados.")

            print("\n" + "="*50)
            print("[FASE 1] Transcripción Multiplataforma (CUDA / Metal)")
            print("="*50)
            cmd_transcribir = [
                sys.executable,
                str(Path(__file__).resolve().parent / "transcribir.py"),
                ruta_archivo_en_carpeta,
                ruta_transcripcion,
            ]
            subprocess.run(cmd_transcribir, check=True, timeout=14400)

    # ------------------------------------------------------------------
    # FASE 2: Generación de apuntes (Ollama)
    # ------------------------------------------------------------------
    print("\n" + "="*50)
    print("[FASE 2] Extracción de apuntes (Síntesis Map-Reduce)")
    print("="*50)

    cmd_apuntes = [
        sys.executable,
        str(Path(__file__).resolve().parent / "generar_apuntes.py"),
        ruta_transcripcion,
        ruta_apuntes,
    ]
    subprocess.run(cmd_apuntes, check=True, timeout=14400)

    # ------------------------------------------------------------------
    # FASE 3: Auditoría determinista (siempre se ejecuta)
    # ------------------------------------------------------------------
    _ejecutar_auditoria(ruta_apuntes)

    print("\n" + "="*50)
    print("[EXITO] FLUJO COMPLETADO CON ÉXITO")
    print(f"Todos los archivos de la sesión quedaron archivados en:\n{directorio_destino}")
    print("="*50)


if __name__ == "__main__":
    # Parseo manual de flags: se extraen del final de sys.argv antes de los posicionales
    _args = [a for a in sys.argv[1:] if not a.startswith("--")]
    _flags = [a for a in sys.argv[1:] if a.startswith("--")]

    _solo_apuntes = "--solo-apuntes" in _flags
    _forzar_transcripcion = "--forzar-transcripcion" in _flags

    if _solo_apuntes and _forzar_transcripcion:
        print("Error: --solo-apuntes y --forzar-transcripcion son mutuamente excluyentes.",
              file=sys.stderr)
        sys.exit(1)

    if len(_args) >= 3:
        materia_in = _args[0]
        clase_in = _args[1]
        archivo_in = _args[2]
    elif len(_args) >= 2 and _solo_apuntes:
        # En modo --solo-apuntes el archivo multimedia no es necesario
        materia_in = _args[0]
        clase_in = _args[1]
        archivo_in = ""   # no se usará
    else:
        print("=== Gestor Automático de Clases DAW ===")
        materia_in = input("Materia (ej. Programacion, Bases_de_Datos): ").strip()
        clase_in = input("Nombre o número de clase (ej. Clase_02_Condicionales): ").strip()
        archivo_in = input("Ruta o nombre del archivo de audio/vídeo: ").strip()

    ejecutar_pipeline(
        materia_in,
        clase_in,
        archivo_in,
        solo_apuntes=_solo_apuntes,
        forzar_transcripcion=_forzar_transcripcion,
    )