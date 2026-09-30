"""Constantes de estilos CSS, fuentes personalizadas y componentes de diseño visual para LectureFlow."""
import streamlit as st

FUENTE_GOOGLE = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap');
"""

CSS_GLOBAL = f"""
<style>
  {FUENTE_GOOGLE}

  /* Ocultar elementos decorativos nativos */
  #MainMenu {{visibility: hidden;}}
  footer {{visibility: hidden;}}
  header {{background-color: transparent !important;}}

  /* Tipografía global y lienzo oscuro */
  html, body, [class*="css"] {{
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  }}

  .stApp {{
    background-color: #0b1326;
    color: #dae2fd;
  }}

  /* Badges y chips estilo Stitch */
  .badge-status-chip {{
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background-color: #131b2e;
    color: #4edea3;
    font-family: 'JetBrains Mono', ui-monospace, Menlo, Monaco, Consolas, monospace;
    font-size: 0.75rem;
    padding: 3px 10px;
    border-radius: 9999px;
    border: 1px solid rgba(78, 222, 163, 0.2);
    font-weight: 500;
  }}

  .dot-ping {{
    width: 6px;
    height: 6px;
    border-radius: 9999px;
    background-color: #4edea3;
  }}

  .terminal-topbar {{
    background-color: #131b2e;
    padding: 6px 12px;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
    display: flex;
    align-items: center;
    gap: 6px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.75rem;
    color: #908fa0;
    border: 1px solid rgba(255,255,255,0.06);
    border-bottom: none;
    margin-top: 14px;
  }}

  /* Tarjetas informativas con bordes sutiles */
  .card-lectureflow {{
    background-color: #131b2e;
    padding: 18px;
    border-radius: 8px;
    border: 1px solid rgba(255,255,255,0.06);
    margin-bottom: 16px;
  }}
</style>
"""

HTML_HEADER = """
<div style="display: flex; justify-content: space-between; align-items: center; padding: 12px 18px; background-color: #171f33; border-radius: 10px; border: 1px solid rgba(255,255,255,0.06); margin-bottom: 20px;">
  <div style="display: flex; align-items: center; gap: 12px;">
    <span style="font-size: 24px;">🎓</span>
    <div>
      <div style="display: flex; align-items: center; gap: 8px;">
        <span style="font-weight: 700; color: #dae2fd; font-size: 1.05rem;">LectureFlow</span>
      </div>
    </div>
  </div>
  <div class="badge-status-chip">
    <span class="dot-ping"></span> Multiplataforma Local
  </div>
</div>
"""


def aplicar_estilos() -> None:
    """Inyecta las fuentes personalizadas y estilos CSS globales en la aplicación Streamlit."""
    st.html(CSS_GLOBAL)


def render_header() -> None:
    """Renderiza el banner superior de bienvenida e indicativo de estado."""
    st.html(HTML_HEADER)


def render_terminal_topbar(titulo: str = "stdout") -> None:
    """Renderiza la cabecera estilizada de consola para streams de salida."""
    st.html(f"""
    <div class="terminal-topbar">
      <span style="color:#ff5f56;">●</span>
      <span style="color:#ffbd2e;">●</span>
      <span style="color:#27c93f;">●</span>
      <span style="margin-left: 8px;">{titulo}</span>
    </div>
    """)
