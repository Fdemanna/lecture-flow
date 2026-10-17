"""Módulo de compatibilidad para JobManager.

DEPRECATION NOTE:
La gestión de jobs y eventos en segundo plano ha sido consolidada directamente
en 'src.orchestrator' para respetar la regla arquitectónica de puente único.
Por favor, importa directamente:
    from src.orchestrator import job_manager, JobManager
"""
from __future__ import annotations

from src.orchestrator import JobManager, job_manager

__all__ = ["JobManager", "job_manager"]
