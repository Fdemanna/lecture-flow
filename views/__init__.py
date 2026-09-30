"""Módulo de vistas de interfaz de usuario para LectureFlow."""
from views.estilos import (
    aplicar_estilos,
    render_header,
    render_terminal_topbar,
    CSS_GLOBAL,
    HTML_HEADER,
)
from views.sidebar import renderizar_sidebar, MAPEO_ASIGNATURAS
from views.vista_individual import renderizar_vista_individual
from views.vista_lotes import renderizar_vista_lotes
from views.editor_apuntes import renderizar_editor_apuntes

# Alias para compatibilidad
inyectar_estilos = aplicar_estilos
render_sidebar = renderizar_sidebar
render_vista_individual = renderizar_vista_individual
render_vista_lotes = renderizar_vista_lotes
render_editor_apuntes = renderizar_editor_apuntes

__all__ = [
    "aplicar_estilos",
    "inyectar_estilos",
    "render_header",
    "render_terminal_topbar",
    "CSS_GLOBAL",
    "HTML_HEADER",
    "renderizar_sidebar",
    "render_sidebar",
    "renderizar_vista_individual",
    "render_vista_individual",
    "renderizar_vista_lotes",
    "render_vista_lotes",
    "renderizar_editor_apuntes",
    "render_editor_apuntes",
    "MAPEO_ASIGNATURAS",
]
