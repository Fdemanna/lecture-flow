import os
import sys
import subprocess
import mlx_whisper

def extraer_audio_rapido(ruta_entrada: str, ruta_audio_temp: str):
    print("-> Extrayendo pista de audio con FFmpeg...", flush=True)
    comando = [
        "ffmpeg", "-y", "-i", ruta_entrada,
        "-vn", "-acodec", "libmp3lame", "-ar", "16000", "-ac", "1",
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
        archivo_temp = os.path.splitext(ruta_entrada)[0] + "_temp.mp3"
        # [M-1] Limpieza de temporal huérfano de sesiones anteriores (crash / SIGKILL)
        if os.path.exists(archivo_temp):
            print(f"⚠️  Temporal huérfano detectado, limpiando: {archivo_temp}", flush=True)
            try:
                os.remove(archivo_temp)
            except OSError as e:
                print(f"   No se pudo eliminar el temporal huérfano: {e}", flush=True)
        extraer_audio_rapido(ruta_entrada, archivo_temp)
        audio_a_procesar = archivo_temp

    try:
        repo_modelo = "mlx-community/whisper-medium-mlx"
        print("Iniciando transcripción con Whisper en Apple Silicon...", flush=True)

        resultado = mlx_whisper.transcribe(
            audio_a_procesar,
            path_or_hf_repo=repo_modelo,
            language="es",
            word_timestamps=False,
            verbose=True  # Imprime cada segmento en la consola según lo procesa
        )

        lineas = []
        for seg in resultado.get("segments", []):
            ini = int(seg["start"])
            h = ini // 3600
            m = (ini % 3600) // 60
            s = ini % 60
            tiempo_str = f"[{h:02d}:{m:02d}:{s:02d}]"
            lineas.append(f"{tiempo_str} {seg['text'].strip()}")

        with open(ruta_salida, "w", encoding="utf-8") as f:
            f.write("\n".join(lineas))

        print(f"--- Transcripción completada y guardada en: {ruta_salida} ---", flush=True)

    finally:
        if archivo_temp and os.path.exists(archivo_temp):
            os.remove(archivo_temp)

if __name__ == "__main__":
    archivo_a_procesar = sys.argv[1] if len(sys.argv) > 1 else "clase_muestra.mp4"
    archivo_salida = sys.argv[2] if len(sys.argv) > 2 else "transcripcion.txt"
    transcribir_archivo(archivo_a_procesar, archivo_salida)