"""
CLI Wrapper delgado para el orquestador de clases DAW.
Invoca directamente a 'PipelineOrchestrator' para ejecutar el pipeline unificado.

Uso interactivo:
    python src/procesar_clase.py

Uso directo por argumentos:
    python src/procesar_clase.py "Programacion" "Clase_02_Condicionales" ruta/video.mp4

Flags opcionales:
    --solo-apuntes          Omite Whisper y usa transcripcion.txt existente.
    --forzar-transcripcion  Sobrescribe transcripción y apuntes existentes.
    --no-notion             Omite la exportación a Notion.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Configuración de codificación para Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Importación robusta
try:
    from src.orchestrator import PipelineOrchestrator, normalizar_nombre
except ModuleNotFoundError:
    _ROOT = Path(__file__).resolve().parent.parent
    if str(_ROOT) not in sys.path:
        sys.path.insert(0, str(_ROOT))
    from src.orchestrator import PipelineOrchestrator, normalizar_nombre


def ejecutar_pipeline(
    materia: str,
    nombre_clase: str,
    ruta_archivo_origen: str = "",
    solo_apuntes: bool = False,
    forzar_transcripcion: bool = False,
    exportar_notion: bool = True,
) -> dict:
    """Wrapper delgado que delega la orquestación a PipelineOrchestrator."""
    def _mostrar_progreso(fase: str, porcentaje: int, mensaje: str) -> None:
        print(f"[{fase.upper()}] ({porcentaje}%) {mensaje}", flush=True)

    orquestador = PipelineOrchestrator(
        callback_progreso=_mostrar_progreso,
        callback_linea=lambda linea: print(linea, end="", flush=True),
    )

    resultado = orquestador.procesar_clase(
        video_path=ruta_archivo_origen,
        materia=materia,
        nombre_clase=nombre_clase,
        solo_apuntes=solo_apuntes,
        forzar_transcripcion=forzar_transcripcion,
        exportar_notion=exportar_notion,
    )

    if not resultado["exito"]:
        print(f"\n[ERROR] El pipeline finalizó con error: {resultado['error']}", file=sys.stderr)
        sys.exit(1)

    print("\n" + "="*50)
    print(f"[ÉXITO] Pipeline completado en {resultado['duracion']}")
    print(f"Archivos archivados en: {resultado['directorio']}")
    if resultado.get("url_notion"):
        print(f"URL de Notion: {resultado['url_notion']}")
    print("="*50)

    return resultado


if __name__ == "__main__":
    _args = [a for a in sys.argv[1:] if not a.startswith("--")]
    _flags = [a for a in sys.argv[1:] if a.startswith("--")]

    _solo_apuntes = "--solo-apuntes" in _flags
    _forzar_transcripcion = "--forzar-transcripcion" in _flags
    _exportar_notion = "--no-notion" not in _flags

    if _solo_apuntes and _forzar_transcripcion:
        print("Error: --solo-apuntes y --forzar-transcripcion son mutuamente excluyentes.", file=sys.stderr)
        sys.exit(1)

    if len(_args) >= 3:
        materia_in = _args[0]
        clase_in = _args[1]
        archivo_in = _args[2]
    elif len(_args) >= 2 and _solo_apuntes:
        materia_in = _args[0]
        clase_in = _args[1]
        archivo_in = ""
    else:
        print("=== Gestor Automático de Clases DAW (CLI) ===")
        materia_in = input("Materia (ej. Programacion, Bases_de_Datos): ").strip()
        clase_in = input("Nombre o número de clase (ej. Clase_02_Condicionales): ").strip()
        archivo_in = input("Ruta o nombre del archivo de audio/vídeo: ").strip() if not _solo_apuntes else ""

    ejecutar_pipeline(
        materia=materia_in,
        nombre_clase=clase_in,
        ruta_archivo_origen=archivo_in,
        solo_apuntes=_solo_apuntes,
        forzar_transcripcion=_forzar_transcripcion,
        exportar_notion=_exportar_notion,
    )