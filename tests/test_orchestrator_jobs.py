"""Tests unitarios para la gestión integrada de trabajos asíncronos en src/orchestrator.py."""
import asyncio
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

from src.orchestrator import JobManager, RUTA_LOCK


@pytest.fixture(autouse=True)
def limpiar_estado_job_manager():
    """Garantiza aislamiento entre tests restableciendo el estado del singleton."""
    jm = JobManager()
    with jm._lock:
        jm._active_job = None
        jm._subscribers.clear()
        jm._job_history.clear()
    if RUTA_LOCK.exists():
        try:
            RUTA_LOCK.unlink(missing_ok=True)
        except Exception:
            pass
    yield
    with jm._lock:
        jm._active_job = None
        jm._subscribers.clear()
        jm._job_history.clear()
    if RUTA_LOCK.exists():
        try:
            RUTA_LOCK.unlink(missing_ok=True)
        except Exception:
            pass


def test_job_manager_singleton():
    """Comprueba que JobManager implementa un singleton coherente."""
    jm1 = JobManager()
    jm2 = JobManager()
    assert jm1 is jm2


def test_obtener_job_activo_vacio():
    """Verifica que sin jobs ni lockfile, devuelve None."""
    jm = JobManager()
    assert jm.obtener_job_activo() is None


def test_obtener_job_activo_detecta_lockfile_externo(tmp_path):
    """Verifica que detecta un bloqueo iniciado externamente (ej. Streamlit)."""
    jm = JobManager()
    RUTA_LOCK.parent.mkdir(parents=True, exist_ok=True)
    RUTA_LOCK.write_text("Sistemas / Tema_01", encoding="utf-8")

    try:
        activo = jm.obtener_job_activo()
        assert activo is not None
        assert activo["es_externo"] is True
        assert activo["materia"] == "Sistemas"
        assert activo["tema"] == "Tema_01"
        assert activo["status"] == "running"
    finally:
        RUTA_LOCK.unlink(missing_ok=True)


def test_cancelar_job_activo():
    """Verifica que cancelar_job marca el estado cancelado y elimina el lockfile."""
    jm = JobManager()
    RUTA_LOCK.parent.mkdir(parents=True, exist_ok=True)
    RUTA_LOCK.write_text("Test / Dummy", encoding="utf-8")

    with jm._lock:
        jm._active_job = {
            "job_id": "job_12345",
            "materia": "Test",
            "tema": "Dummy",
            "status": "running",
            "phase": "transcripcion",
            "progress": 20,
            "message": "En curso",
        }

    exito = jm.cancelar_job("job_12345")
    assert exito is True
    assert jm.obtener_job_activo() is None
    assert not RUTA_LOCK.exists()


def test_suscribir_eventos_emite_estado_inicial():
    """Verifica que suscribir_eventos emite el estado inicial al conectarse."""
    async def _test():
        jm = JobManager()
        with jm._lock:
            jm._job_history["job_finalizado"] = {
                "job_id": "job_finalizado",
                "status": "completed",
                "phase": "completado",
                "progress": 100,
                "message": "Finalizado con éxito",
            }

        gen = jm.suscribir_eventos("job_finalizado")
        primer_evento = await gen.__anext__()
        assert "data: " in primer_evento
        assert "completed" in primer_evento
        assert "job_finalizado" in primer_evento

    asyncio.run(_test())
