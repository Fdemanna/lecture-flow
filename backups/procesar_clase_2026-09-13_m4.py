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
import sys
import shutil
import subprocess

CARPETA_BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "clases")

def normalizar_nombre(texto: str) -> str:
    """Elimina caracteres problemáticos para carpetas del sistema."""
    caracteres_validos = "-_.() abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    limpio = "".join(c for c in texto if c in caracteres_validos)
    return limpio.strip().replace(" ", "_")

def ejecutar_pipeline(materia: str, nombre_clase: str, ruta_archivo_origen: str):
    if not os.path.exists(ruta_archivo_origen):
        print(f"Error: El archivo de entrada '{ruta_archivo_origen}' no existe.")
        return

    # 1. Preparar nombres y rutas
    materia_clean = normalizar_nombre(materia)
    clase_clean = normalizar_nombre(nombre_clase)
    
    directorio_destino = os.path.join(CARPETA_BASE, materia_clean, clase_clean)
    os.makedirs(directorio_destino, exist_ok=True)
    
    print(f"\n📁 Carpeta de trabajo lista: {directorio_destino}")

    # Copiar o mover el archivo de entrada a la carpeta correspondiente
    nombre_archivo = os.path.basename(ruta_archivo_origen)
    ruta_archivo_en_carpeta = os.path.join(directorio_destino, nombre_archivo)
    
    if not os.path.exists(ruta_archivo_en_carpeta):
        print(f"-> Copiando archivo multimedia a la carpeta de la clase...")
        shutil.copy2(ruta_archivo_origen, ruta_archivo_en_carpeta)

    ruta_transcripcion = os.path.join(directorio_destino, "transcripcion.txt")
    ruta_apuntes = os.path.join(directorio_destino, "apuntes.md")

    # 2. Ejecutar Fase 1: Transcripción (MLX-Whisper)
    print("\n" + "="*50)
    print("▶ FASE 1: Transcripción con Apple Silicon")
    print("="*50)
    
    cmd_transcribir = [
        sys.executable,
        "transcribir.py",
        ruta_archivo_en_carpeta,
        ruta_transcripcion
    ]
    subprocess.run(cmd_transcribir, check=True)

    # 3. Ejecutar Fase 2: Apuntes y Auditoría (Ollama)
    print("\n" + "="*50)
    print("▶ FASE 2: Extracción de apuntes y control de alucinaciones")
    print("="*50)
    
    cmd_apuntes = [
        sys.executable,
        "generar_apuntes.py",
        ruta_transcripcion,
        ruta_apuntes
    ]
    subprocess.run(cmd_apuntes, check=True)

    print("\n" + "="*50)
    print("🎉 FLUJO COMPLETADO CON ÉXITO")
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