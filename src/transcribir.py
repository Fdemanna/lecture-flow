import os
import sys
import subprocess
import platform
from pathlib import Path
from typing import Optional

# Importación robusta del gestor de checkpoints
try:
    from src.checkpoint_manager import CheckpointManager, FASE_TRANSCRIBIENDO, FASE_SINTETIZANDO
except ModuleNotFoundError:
    _ROOT = Path(__file__).resolve().parent.parent
    if str(_ROOT) not in sys.path:
        sys.path.insert(0, str(_ROOT))
    from src.checkpoint_manager import CheckpointManager, FASE_TRANSCRIBIENDO, FASE_SINTETIZANDO

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
            add_dll = getattr(os, "add_dll_directory", None)
            if callable(add_dll):
                try:
                    add_dll(ruta)
                except OSError:
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

def transcribir_archivo(
    ruta_entrada: str,
    ruta_salida: str = "transcripcion.txt",
    checkpoint: Optional["CheckpointManager"] = None,
):
    if not os.path.exists(ruta_entrada):
        print(f"Error: El archivo '{ruta_entrada}' no existe.", flush=True)
        return

    print(f"--- Procesando: {os.path.basename(ruta_entrada)} ---", flush=True)

    # ---- Reanudación: escribir segmentos previos y determinar offset ----
    timestamp_reanudacion: float = 0.0
    if checkpoint is not None:
        segmentos_previos = checkpoint.segmentos_transcritos
        if segmentos_previos:
            timestamp_reanudacion = checkpoint.ultimo_timestamp
            print(
                f"[CHECKPOINT] Reanudando desde {timestamp_reanudacion:.1f}s "
                f"({len(segmentos_previos)} segmentos previos recuperados).",
                flush=True,
            )
            # Escribir los segmentos ya transcritos al archivo de salida
            with open(ruta_salida, "w", encoding="utf-8") as _f:
                _f.writelines(segmentos_previos)
        checkpoint.avanzar_fase(FASE_TRANSCRIBIENDO)

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

        # Modo apertura: 'a' si reanudamos, 'w' si empezamos desde cero
        modo_apertura = "a" if timestamp_reanudacion > 0.0 else "w"
        with open(ruta_salida, modo_apertura, encoding="utf-8") as f:
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
                    inicio_seg = float(seg["start"])
                    # Saltar segmentos ya guardados en checkpoint previo
                    if inicio_seg <= timestamp_reanudacion:
                        continue
                    ini = int(inicio_seg)
                    h = ini // 3600
                    m = (ini % 3600) // 60
                    s = ini % 60
                    tiempo_str = f"[{h:02d}:{m:02d}:{s:02d}]"
                    linea = f"{tiempo_str} {seg['text'].strip()}\n"
                    print(linea, end="", flush=True)
                    f.write(linea)
                    f.flush()
                    if checkpoint is not None:
                        checkpoint.registrar_segmento(linea, inicio_seg)
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
                    inicio_seg = float(seg.start)
                    # Saltar segmentos ya guardados en checkpoint previo
                    if inicio_seg <= timestamp_reanudacion:
                        continue
                    ini = int(inicio_seg)
                    h = ini // 3600
                    m = (ini % 3600) // 60
                    s = ini % 60
                    tiempo_str = f"[{h:02d}:{m:02d}:{s:02d}]"
                    linea = f"{tiempo_str} {seg.text.strip()}\n"
                    print(linea, end="", flush=True)
                    f.write(linea)
                    f.flush()
                    if checkpoint is not None:
                        checkpoint.registrar_segmento(linea, inicio_seg)

        print(f"\n--- Transcripción completada y guardada en: {ruta_salida} ---", flush=True)
        # Guardar el último segmento y avanzar fase
        if checkpoint is not None:
            checkpoint.registrar_segmento("", checkpoint.ultimo_timestamp, forzar_guardado=True)
            checkpoint.avanzar_fase(FASE_SINTETIZANDO)

    finally:
        if archivo_temp and os.path.exists(archivo_temp):
            try:
                os.remove(archivo_temp)
            except OSError as e:
                print(f"[AVISO] No se pudo eliminar el archivo temporal '{archivo_temp}': {e}", flush=True)


if __name__ == "__main__":
    _args_posicionales = [a for a in sys.argv[1:] if not a.startswith("--")]
    _flags = [a for a in sys.argv[1:] if a.startswith("--")]

    archivo_a_procesar = _args_posicionales[0] if len(_args_posicionales) > 0 else "clase_muestra.mp4"
    archivo_salida = _args_posicionales[1] if len(_args_posicionales) > 1 else "transcripcion.txt"

    _checkpoint: "CheckpointManager | None" = None
    if "--reanudar" in _flags:
        _dir_salida = str(Path(archivo_salida).resolve().parent)
        _checkpoint = CheckpointManager(_dir_salida, archivo_a_procesar)
        if not _checkpoint.existe_sesion_previa():
            print("[CHECKPOINT] No se encontró sesión previa válida; iniciando transcripción completa.", flush=True)
            _checkpoint = None

    transcribir_archivo(archivo_a_procesar, archivo_salida, checkpoint=_checkpoint)
