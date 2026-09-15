import os
import sys
import subprocess
import platform

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
# En Windows, registrar las rutas de las DLLs de NVIDIA si existen en el entorno
if platform.system() == "Windows":
    base_venv = sys.prefix
    rutas_dll = [
        os.path.join(base_venv, "Lib", "site-packages", "nvidia", "cublas", "bin"),
        os.path.join(base_venv, "Lib", "site-packages", "nvidia", "cudnn", "bin"),
    ]
    for ruta in rutas_dll:
        if os.path.isdir(ruta):
            try:
                os.add_dll_directory(ruta)
            except (AttributeError, OSError):
                pass
            os.environ["PATH"] = ruta + os.pathsep + os.environ.get("PATH", "")

def extraer_audio_rapido(ruta_entrada: str, ruta_audio_temp: str):
    print("-> Extrayendo pista de audio con FFmpeg...", flush=True)
    comando = [
        "ffmpeg", "-y", "-i", ruta_entrada,
        "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
        ruta_audio_temp
    ]
    subprocess.run(comando, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    print("-> Audio extraído con éxito. Cargando red neuronal...", flush=True)

def transcribir_archivo(ruta_entrada: str, ruta_salida: str = "transcripcion.txt"):
    if not os.path.exists(ruta_entrada):
        print(f"Error: El archivo '{ruta_entrada}' no existe.", flush=True)
        return

    print(f"--- Procesando: {os.path.basename(ruta_entrada)} ---", flush=True)

    es_video = ruta_entrada.lower().endswith((".mp4", ".mkv", ".mov", ".avi"))
    audio_a_procesar = ruta_entrada
    archivo_temp = None

    if es_video:
        archivo_temp = os.path.splitext(ruta_entrada)[0] + "_temp.wav"
        if os.path.exists(archivo_temp):
            print(f"[AVISO] Temporal huérfano detectado, limpiando: {archivo_temp}", flush=True)
            try:
                os.remove(archivo_temp)
            except OSError as e:
                print(f"   No se pudo eliminar el temporal huérfano: {e}", flush=True)
        extraer_audio_rapido(ruta_entrada, archivo_temp)
        audio_a_procesar = archivo_temp

    try:
        sistema = platform.system()

        with open(ruta_salida, "w", encoding="utf-8") as f:
            if sistema == "Darwin":
                import mlx_whisper
                repo_modelo = "mlx-community/whisper-large-v3-turbo"
                print("Iniciando transcripción con mlx-whisper (macOS Metal)...", flush=True)
                resultado = mlx_whisper.transcribe(
                    audio_a_procesar,
                    path_or_hf_repo=repo_modelo,
                    language="es",
                    word_timestamps=False,
                    verbose=True
                )
                for seg in resultado.get("segments", []):
                    ini = int(seg["start"])
                    h = ini // 3600
                    m = (ini % 3600) // 60
                    s = ini % 60
                    tiempo_str = f"[{h:02d}:{m:02d}:{s:02d}]"
                    linea = f"{tiempo_str} {seg['text'].strip()}\n"
                    print(linea, end="", flush=True)
                    f.write(linea)
                    f.flush()
            else:
                from faster_whisper import WhisperModel
                print(f"Iniciando transcripción con faster-whisper ({sistema})...", flush=True)
                try:
                    print("Intentando cargar modelo en CUDA...", flush=True)
                    model = WhisperModel("large-v3-turbo", device="cuda", compute_type="float16")
                except Exception as e:
                    print(f"Fallo al cargar en CUDA ({e}). Haciendo fallback a CPU (int8)...", flush=True)
                    model = WhisperModel("large-v3-turbo", device="cpu", compute_type="int8")

                segments, info = model.transcribe(audio_a_procesar, language="es")
                for seg in segments:
                    ini = int(seg.start)
                    h = ini // 3600
                    m = (ini % 3600) // 60
                    s = ini % 60
                    tiempo_str = f"[{h:02d}:{m:02d}:{s:02d}]"
                    linea = f"{tiempo_str} {seg.text.strip()}\n"
                    print(linea, end="", flush=True)
                    f.write(linea)
                    f.flush()

        print(f"\n--- Transcripción completada y guardada en: {ruta_salida} ---", flush=True)

    finally:
        if archivo_temp and os.path.exists(archivo_temp):
            os.remove(archivo_temp)

if __name__ == "__main__":
    archivo_a_procesar = sys.argv[1] if len(sys.argv) > 1 else "clase_muestra.mp4"
    archivo_salida = sys.argv[2] if len(sys.argv) > 2 else "transcripcion.txt"
    transcribir_archivo(archivo_a_procesar, archivo_salida)
