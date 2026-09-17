"""
Orquestador de clases DAW.
Organiza la jerarquía de carpetas por materia y clase,
y encadena la transcripción (MLX) con la generación de apuntes (Ollama).

Uso interactivo:
    python procesar_clase.py

Uso directo por argumentos:
    python procesar_clase.py "Programacion" "Clase_02_Condicionales" ruta/video.mp4
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

def ejecutar_pipeline(materia: str, nombre_clase: str, ruta_archivo_origen: str):
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

    # 1. Preparar nombres y rutas
    materia_clean = normalizar_nombre(materia)
    clase_clean = normalizar_nombre(nombre_clase)

    directorio_destino = os.path.join(CARPETA_BASE, materia_clean, clase_clean)

    # [M-4] Verificar contención estricta de la ruta destino dentro de CARPETA_BASE
    carpeta_base_real = os.path.realpath(CARPETA_BASE)
    if not os.path.realpath(directorio_destino).startswith(carpeta_base_real + os.sep):
        print("Error: Ruta de destino inválida. Intento de escape fuera del directorio de clases detectado.")
        return

    os.makedirs(directorio_destino, exist_ok=True)
    
    print(f"\n[DIR] Carpeta de trabajo lista: {directorio_destino}")

    # Copiar o mover el archivo de entrada a la carpeta correspondiente
    nombre_archivo = os.path.basename(ruta_archivo_origen)
    ruta_archivo_en_carpeta = os.path.join(directorio_destino, nombre_archivo)
    
    if not os.path.exists(ruta_archivo_en_carpeta):
        print(f"-> Copiando archivo multimedia a la carpeta de la clase...")
        shutil.copy2(ruta_archivo_origen, ruta_archivo_en_carpeta)

    ruta_transcripcion = os.path.join(directorio_destino, "transcripcion.txt")
    ruta_apuntes = os.path.join(directorio_destino, "apuntes.md")

    # 2. Ejecutar Fase 1: Transcripción (Whisper)
    print("\n" + "="*50)
    print("[FASE 1] Transcripción Multiplataforma (CUDA / Metal)")
    print("="*50)
    
    cmd_transcribir = [
        sys.executable,
        str(Path(__file__).resolve().parent / "transcribir.py"),
        ruta_archivo_en_carpeta,
        ruta_transcripcion
    ]
    subprocess.run(cmd_transcribir, check=True, timeout=14400)

    # 3. Ejecutar Fase 2: Apuntes (Ollama)
    print("\n" + "="*50)
    print("[FASE 2] Extracción de apuntes (Síntesis Map-Reduce)")
    print("="*50)

    cmd_apuntes = [
        sys.executable,
        str(Path(__file__).resolve().parent / "generar_apuntes.py"),
        ruta_transcripcion,
        ruta_apuntes
    ]
    subprocess.run(cmd_apuntes, check=True, timeout=14400)

    # 4. Auditoría determinista (sustituye el critic-loop del LLM)
    print("\n" + "="*50)
    print("[FASE 3] Auditoría determinista de apuntes")
    print("="*50)

    if os.path.exists(ruta_apuntes):
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
    else:
        print("[AUDITORÍA] No se encontró el archivo de apuntes para auditar.",
              file=sys.stderr)

    print("\n" + "="*50)
    print("[EXITO] FLUJO COMPLETADO CON ÉXITO")
    print(f"Todos los archivos de la sesión quedaron archivados en:\n{directorio_destino}")
    print("="*50)

if __name__ == "__main__":
    if len(sys.argv) >= 4:
        materia_in = sys.argv[1]
        clase_in = sys.argv[2]
        archivo_in = sys.argv[3]
    else:
        print("=== Gestor Automático de Clases DAW ===")
        materia_in = input("Materia (ej. Programacion, Bases_de_Datos): ").strip()
        clase_in = input("Nombre o número de clase (ej. Clase_02_Condicionales): ").strip()
        archivo_in = input("Ruta o nombre del archivo de audio/vídeo: ").strip()

    ejecutar_pipeline(materia_in, clase_in, archivo_in)