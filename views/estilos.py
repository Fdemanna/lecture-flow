"""Constantes de estilos CSS, fuentes personalizadas y componentes de diseño visual para LectureFlow."""
import streamlit as st

# ---------------------------------------------------------------------------
# Fuentes
# ---------------------------------------------------------------------------
FUENTES_IMPORT = """
@import url('https://fonts.googleapis.com/css2?family=Geist:wght@300;400;500;600;700&family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap');
@import url('https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200');
"""

CSS_GLOBAL = f"""
<style>
  {FUENTES_IMPORT}

  /* ---- Reset decorativos nativos ---- */
  #MainMenu {{visibility: hidden;}}
  footer {{visibility: hidden;}}
  header {{background-color: transparent !important;}}
  .stDeployButton {{display: none;}}

  /* ---- Tipografía y lienzo oscuro Obsidian Flow ---- */
  html, body, [class*="css"] {{
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    -webkit-font-smoothing: antialiased;
  }}

  h1, h2, h3, h4, h5, h6, .lf-page-title, .lf-section-label, .lf-origin-title {{
    font-family: 'Geist', sans-serif;
  }}

  .stApp {{
    background-color: #0b0f19;
    color: #dfe2f1;
  }}

  /* ---- Contenedor principal centrado ---- */
  .block-container {{
    max-width: 900px !important;
    padding-top: 1.5rem !important;
    padding-left: 2rem !important;
    padding-right: 2rem !important;
  }}

  /* ====================================================
     HEADER DE PÁGINA
  ==================================================== */
  .lf-page-header {{
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    margin-bottom: 1.5rem;
  }}
  .lf-breadcrumb {{
    display: flex;
    align-items: center;
    gap: 6px;
    font-family: 'Geist', sans-serif;
    font-size: 0.78rem;
    color: #94a3b8;
    margin-bottom: 4px;
    font-weight: 500;
  }}
  .lf-breadcrumb .bc-icon {{
    font-family: 'Material Symbols Outlined';
    font-size: 14px;
    color: #8083ff;
  }}
  .lf-breadcrumb .bc-sep {{
    color: #464554;
  }}
  .lf-page-title {{
    font-family: 'Geist', sans-serif;
    font-size: 1.35rem;
    font-weight: 700;
    color: #f8fafc;
    display: flex;
    align-items: center;
    gap: 10px;
    margin: 0;
    line-height: 1.3;
    letter-spacing: -0.02em;
  }}
  .lf-version-badge {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.62rem;
    font-weight: 600;
    color: #8083ff;
    background: rgba(128,131,255,0.12);
    border: 1px solid rgba(128,131,255,0.25);
    padding: 2px 8px;
    border-radius: 9999px;
    letter-spacing: 0.03em;
  }}
  .lf-status-capsule {{
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: #171b26;
    border: 1px solid rgba(78,222,163,0.18);
    color: #4edea3;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.68rem;
    font-weight: 500;
    padding: 5px 12px;
    border-radius: 9999px;
  }}
  .lf-status-dot {{
    width: 7px;
    height: 7px;
    border-radius: 9999px;
    background: #4edea3;
    animation: pulse-green 2s infinite;
  }}
  @keyframes pulse-green {{
    0%, 100% {{ opacity: 1; box-shadow: 0 0 0 0 rgba(78,222,163,0.4); }}
    50%        {{ opacity: 0.7; box-shadow: 0 0 0 4px rgba(78,222,163,0); }}
  }}

  /* ====================================================
     TARJETA GLASSMORPHIC ENVOLVENTE DEL FORMULARIO
  ==================================================== */
  .lf-glass-card,
  div[data-testid="stVerticalBlockBorderWrapper"]:has(.lf-form-anchor) {{
    background: #171b26 !important;
    border: 1px solid rgba(255, 255, 255, 0.06) !important;
    border-radius: 16px !important;
    padding: 24px !important;
    margin-bottom: 20px !important;
    box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.5) !important;
  }}

  /* ====================================================
     SELECTOR DE ORIGEN — st.radio estilizado en 3 tarjetas
  ==================================================== */
  div[data-testid="stRadio"] div[role="radiogroup"] {{
    display: flex !important;
    flex-direction: row !important;
    gap: 12px !important;
    width: 100% !important;
  }}
  /* Ocultar el círculo nativo de radio */
  div[data-testid="stRadio"] label[data-baseweb="radio"] > div:first-child,
  div[data-testid="stRadio"] input[type="radio"] {{
    display: none !important;
  }}
  /* Convertir cada opción en una tarjeta interactiva */
  div[data-testid="stRadio"] label[data-baseweb="radio"] {{
    flex: 1 1 0 !important;
    min-width: 0 !important;
    margin: 0 !important;
    background: #1c1f2a !important;
    border: 1.5px solid rgba(255, 255, 255, 0.08) !important;
    border-radius: 12px !important;
    padding: 14px 16px !important;
    cursor: pointer !important;
    position: relative !important;
    display: flex !important;
    flex-direction: column !important;
    align-items: flex-start !important;
    justify-content: center !important;
    transition: border-color 0.18s ease, background 0.18s ease, box-shadow 0.18s ease !important;
    user-select: none !important;
  }}
  div[data-testid="stRadio"] label[data-baseweb="radio"]:hover {{
    border-color: rgba(99, 102, 241, 0.4) !important;
    background: #222634 !important;
  }}
  /* Estado activo / seleccionado */
  div[data-testid="stRadio"] label[data-baseweb="radio"]:has(input:checked) {{
    background: #262a35 !important;
    border-color: #8083ff !important;
    box-shadow: 0 0 20px -3px rgba(99, 102, 241, 0.35) !important;
  }}
  /* Punto indicador activo en la esquina derecha */
  div[data-testid="stRadio"] label[data-baseweb="radio"]:has(input:checked)::after {{
    content: "" !important;
    position: absolute !important;
    top: 14px !important;
    right: 14px !important;
    width: 8px !important;
    height: 8px !important;
    border-radius: 50% !important;
    background: #8083ff !important;
    box-shadow: 0 0 8px #8083ff !important;
  }}
  /* Tipografía dentro de las tarjetas radio */
  div[data-testid="stRadio"] label[data-baseweb="radio"] div[data-testid="stMarkdownContainer"] {{
    width: 100% !important;
    color: #94a3b8 !important;
    font-family: 'Inter', sans-serif !important;
    font-size: 0.74rem !important;
    line-height: 1.4 !important;
  }}
  div[data-testid="stRadio"] label[data-baseweb="radio"] div[data-testid="stMarkdownContainer"] p {{
    margin: 0 !important;
  }}
  div[data-testid="stRadio"] label[data-baseweb="radio"] div[data-testid="stMarkdownContainer"] strong {{
    font-family: 'Geist', sans-serif !important;
    font-size: 0.88rem !important;
    color: #f8fafc !important;
    display: block !important;
    margin-bottom: 2px !important;
  }}

  /* ====================================================
     FILE UPLOADER ESTILIZADO
  ==================================================== */
  div[data-testid="stFileUploader"] {{
    background-color: #1c1f2a !important;
    border: 1.5px dashed rgba(255, 255, 255, 0.12) !important;
    border-radius: 12px !important;
    padding: 16px !important;
    transition: border-color 0.2s ease !important;
  }}
  div[data-testid="stFileUploader"]:hover {{
    border-color: rgba(99, 102, 241, 0.5) !important;
  }}
  div[data-testid="stFileUploader"] section {{
    background-color: transparent !important;
    border: none !important;
    padding: 0 !important;
  }}
  div[data-testid="stFileUploader"] button {{
    background: rgba(30, 41, 59, 0.8) !important;
    border: 1px solid rgba(255, 255, 255, 0.1) !important;
    color: #f8fafc !important;
    border-radius: 8px !important;
    font-family: 'Geist', sans-serif !important;
    font-weight: 500 !important;
  }}
  div[data-testid="stFileUploader"] button:hover {{
    border-color: #8083ff !important;
    background: rgba(99, 102, 241, 0.15) !important;
  }}

  /* ====================================================
     BANNER URL Y PILLS DE PLATAFORMAS
  ==================================================== */
  .lf-url-banner {{
    background: rgba(87, 27, 193, 0.12);
    border: 1px solid rgba(87, 27, 193, 0.35);
    border-radius: 12px;
    padding: 14px 18px;
    margin-bottom: 12px;
  }}
  .lf-url-banner .url-icon {{
    font-family: 'Material Symbols Outlined';
    font-size: 20px;
    color: #d0bcff;
    flex-shrink: 0;
  }}
  .lf-platform-pill {{
    font-family: 'Geist', sans-serif;
    font-size: 11px;
    font-weight: 500;
    color: #d0bcff;
    background: rgba(87, 27, 193, 0.25);
    border: 1px solid rgba(208, 188, 255, 0.25);
    padding: 2px 10px;
    border-radius: 9999px;
    letter-spacing: 0.01em;
    display: inline-block;
  }}

  /* ====================================================
     HARDWARE BADGE / ESTIMACIÓN
  ==================================================== */
  .lf-hw-strip {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: 10px;
    background: rgba(0, 56, 36, 0.25);
    border: 1px solid rgba(78, 222, 163, 0.2);
    border-radius: 10px;
    padding: 10px 16px;
    font-size: 0.8rem;
    color: #4edea3;
  }}
  .lf-hw-icon {{
    font-family: 'Material Symbols Outlined';
    font-size: 18px;
    color: #4edea3;
  }}

  /* ====================================================
     BOTÓN PRIMARIO GRADIENTE
  ==================================================== */
  .stButton > button[kind="primary"] {{
    background: linear-gradient(135deg, #6366f1 0%, #4f46e5 100%) !important;
    border: none !important;
    border-radius: 10px !important;
    font-weight: 600 !important;
    font-size: 0.92rem !important;
    letter-spacing: 0.01em !important;
    padding: 0.6rem 1.2rem !important;
    transition: opacity 0.18s ease, box-shadow 0.18s ease, transform 0.1s ease !important;
    box-shadow: 0 4px 20px rgba(99,102,241,0.35) !important;
  }}
  .stButton > button[kind="primary"]:hover {{
    opacity: 0.92 !important;
    box-shadow: 0 6px 28px rgba(99,102,241,0.5) !important;
    transform: translateY(-1px) !important;
  }}
  .stButton > button[kind="primary"]:active {{
    transform: translateY(0) !important;
    opacity: 1 !important;
  }}

  /* ====================================================
     HISTORIAL / SESIONES RECIENTES
  ==================================================== */
  .lf-history-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(190px, 1fr));
    gap: 10px;
    margin-top: 8px;
  }}
  .lf-history-item {{
    background: #1c1f2a;
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 10px;
    padding: 12px 14px;
    transition: border-color 0.15s ease, background 0.15s ease;
  }}
  .lf-history-item:hover {{
    border-color: rgba(128,131,255,0.3);
    background: #1e2130;
    cursor: pointer;
  }}
  .lf-history-materia {{
    font-size: 0.66rem;
    font-weight: 600;
    color: #8083ff;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    margin-bottom: 3px;
  }}
  .lf-history-clase {{
    font-size: 0.8rem;
    font-weight: 500;
    color: #e2e6f8;
    line-height: 1.3;
    margin-bottom: 4px;
  }}
  .lf-history-meta {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.63rem;
    color: #545870;
  }}

  /* ====================================================
     TERMINAL / CONSOLA
  ==================================================== */
  .lf-terminal-topbar {{
    background: #171b26;
    padding: 7px 14px;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
    display: flex;
    align-items: center;
    gap: 6px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.72rem;
    color: #545870;
    border: 1px solid rgba(255,255,255,0.06);
    border-bottom: none;
    margin-top: 16px;
  }}
  /* alias legacy */
  .terminal-topbar {{ }}

  /* ====================================================
     EXPANDERS — Fondo oscuro #1c1f2a y borde tenue
  ==================================================== */
  div[data-testid="stExpander"] {{
    background-color: #1c1f2a !important;
    border: 1px solid rgba(255, 255, 255, 0.06) !important;
    border-radius: 12px !important;
    overflow: hidden !important;
    margin-bottom: 12px !important;
  }}
  div[data-testid="stExpander"] details {{
    background-color: #1c1f2a !important;
    border: none !important;
  }}
  div[data-testid="stExpander"] summary {{
    background-color: #1c1f2a !important;
    color: #dfe2f1 !important;
    font-family: 'Geist', sans-serif !important;
    font-size: 0.88rem !important;
    font-weight: 500 !important;
    padding: 10px 16px !important;
    border-radius: 12px !important;
    transition: background 0.18s ease !important;
  }}
  div[data-testid="stExpander"] summary:hover {{
    background-color: #222634 !important;
    color: #f8fafc !important;
  }}
  div[data-testid="stExpander"] details[open] > summary {{
    border-bottom: 1px solid rgba(255, 255, 255, 0.06) !important;
    border-bottom-left-radius: 0 !important;
    border-bottom-right-radius: 0 !important;
  }}
  div[data-testid="stExpander"] div[data-testid="stExpanderDetails"] {{
    background-color: #171b26 !important;
    padding: 16px !important;
  }}

  /* ====================================================
     DIVIDER SUTIL
  ==================================================== */
  .lf-divider {{
    border: none;
    border-top: 1px solid rgba(255,255,255,0.06);
    margin: 20px 0;
  }}

  /* ====================================================
     SELECTBOX / INPUTS — unificación oscura
  ==================================================== */
  div[data-baseweb="select"] > div {{
    background-color: #1c1f2a !important;
    border-color: rgba(255,255,255,0.08) !important;
    border-radius: 8px !important;
    color: #e2e6f8 !important;
  }}
  div[data-baseweb="select"] > div:hover {{
    border-color: rgba(128,131,255,0.4) !important;
  }}
  div[data-baseweb="input"] > div {{
    background-color: #1c1f2a !important;
    border-color: rgba(255,255,255,0.08) !important;
    border-radius: 8px !important;
  }}
  div[data-baseweb="input"] > div:focus-within {{
    border-color: #8083ff !important;
    box-shadow: 0 0 0 2px rgba(128,131,255,0.2) !important;
  }}

  /* ====================================================
     LEGACY — compatibilidad con badge sidebar
  ==================================================== */
  .badge-status-chip {{
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background-color: #171b26;
    color: #4edea3;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.72rem;
    padding: 4px 11px;
    border-radius: 9999px;
    border: 1px solid rgba(78,222,163,0.2);
    font-weight: 500;
  }}
  .dot-ping {{
    width: 6px;
    height: 6px;
    border-radius: 9999px;
    background-color: #4edea3;
  }}
  .card-lectureflow {{
    background-color: #171b26;
    padding: 18px;
    border-radius: 12px;
    border: 1px solid rgba(255,255,255,0.06);
    margin-bottom: 16px;
  }}
</style>
"""


def aplicar_estilos() -> None:
    """Inyecta las fuentes personalizadas y estilos CSS globales en la aplicación Streamlit."""
    st.html(CSS_GLOBAL)


def render_header() -> None:
    """Renderiza el banner superior principal de LectureFlow."""
    st.html("""
    <div style="display:flex;justify-content:space-between;align-items:center;
                padding:14px 20px;background:#171b26;border-radius:12px;
                border:1px solid rgba(255,255,255,0.06);margin-bottom:20px;">
      <div style="display:flex;align-items:center;gap:12px;">
        <span style="font-size:22px;">🎓</span>
        <span style="font-weight:700;color:#e2e6f8;font-size:1.05rem;">LectureFlow</span>
      </div>
      <div class="lf-status-capsule">
        <span class="lf-status-dot"></span> Multiplataforma Local
      </div>
    </div>
    """
    )


def render_terminal_topbar(titulo: str = "stdout") -> None:
    """Renderiza la cabecera estilizada de consola para streams de salida."""
    st.html(f"""
    <div class="lf-terminal-topbar">
      <span style="color:#ff5f56;">●</span>
      <span style="color:#ffbd2e;">●</span>
      <span style="color:#27c93f;">●</span>
      <span style="margin-left:8px;">{titulo}</span>
    </div>
    """)
