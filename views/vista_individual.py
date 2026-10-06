"""Módulo de procesamiento individual: subida de archivos, ejecución del pipeline y checkpointing."""
import os
from pathlib import Path
import time
from typing import Optional, Dict
import streamlit as st

from src.orchestrator import PipelineOrchestrator, normalizar_nombre, es_ruta_segura
from src.downloader import es_url_remota
from src.notion_exporter import exportar_a_notion, notion_configurado
from src.checkpoint_manager import leer_estado_si_existe, CheckpointManager
from src.notificador import notificar_clase_completada
from views.estilos import render_terminal_topbar
from views.sidebar import MAPEO_ASIGNATURAS
from src.transcribir import MODELO_WHISPER
from src.generar_apuntes import MODELO_LLM


def renderizar_vista_individual(
    root_dir: Path,
    orquestador: Optional[PipelineOrchestrator] = None,
    mapeo_asignaturas: Optional[Dict[str, str]] = None,
) -> None:
    """Renderiza el formulario y consola de procesamiento individual de clases."""
    carpeta_base = root_dir / "clases"
    carpeta_base.mkdir(parents=True, exist_ok=True)
    carpeta_base_str = str(carpeta_base)
    mapeo = mapeo_asignaturas or MAPEO_ASIGNATURAS

    # -------------------------------------------------------------------------
    # GESTIÓN SEGURA DE ESTADO: txt_tema_clase y sugerencia automática
    # DEBE ocurrir antes de renderizar st.text_input(..., key="txt_tema_clase")
    # -------------------------------------------------------------------------
    if "txt_tema_clase" not in st.session_state:
        st.session_state["txt_tema_clase"] = ""

    arch_cargado_state = st.session_state.get("uploader_archivo_individual")
    sel_guardado_state = st.session_state.get("sel_archivo_existente")
    origen_actual = st.session_state.get("lf_origen_radio", "upload")

    archivo_detectado_id = None
    if arch_cargado_state is not None and origen_actual == "upload":
        archivo_detectado_id = arch_cargado_state.name
    elif origen_actual == "library" and sel_guardado_state:
        archivo_detectado_id = sel_guardado_state

    if archivo_detectado_id:
        sug_nombre = Path(archivo_detectado_id).stem.replace("_", " ").strip()
        ultimo_detectado = st.session_state.get("_ultimo_archivo_detectado")
        if ultimo_detectado != archivo_detectado_id:
            st.session_state["_ultimo_archivo_detectado"] = archivo_detectado_id
            if (not st.session_state.get("txt_tema_clase", "").strip() or
                    st.session_state.get("txt_tema_clase") == st.session_state.get("_ultima_sugerencia_nombre")):
                st.session_state["txt_tema_clase"] = sug_nombre
                st.session_state["_ultima_sugerencia_nombre"] = sug_nombre
        elif not st.session_state.get("txt_tema_clase", "").strip():
            st.session_state["txt_tema_clase"] = sug_nombre
            st.session_state["_ultima_sugerencia_nombre"] = sug_nombre

    # =========================================================================
    # HEADER DE PÁGINA — Breadcrumb + título + badge versión + status capsule
    # =========================================================================
    asignatura_guardada = st.session_state.get("sel_asignatura_individual") or ""
    bc_asignatura = (
        mapeo.get(asignatura_guardada, asignatura_guardada.replace("_", " "))
        if asignatura_guardada else "—"
    )

    st.html(f"""
    <div class="lf-page-header">
      <div>
        <div class="lf-breadcrumb">
          <span class="bc-icon">folder_open</span>
          <span>{bc_asignatura}</span>
          <span class="bc-sep">/</span>
          <span>Nueva clase</span>
        </div>
        <div class="lf-page-title">
          Procesar Nueva Clase
          <span class="lf-version-badge">v2.4 Pro</span>
        </div>
      </div>
      <div class="lf-status-capsule">
        <span class="lf-status-dot"></span> Sistema listo
      </div>
    </div>
    """)

    # -------------------------------------------------------------------------
    # GESTIÓN DE CERROJO (LOCKFILE) ANTIDUPLICADOS
    # -------------------------------------------------------------------------
    ruta_lock = root_dir / "data" / ".procesando.lock"
    en_proceso = ruta_lock.exists()
    contenido_lock = ""
    if en_proceso:
        try:
            contenido_lock = ruta_lock.read_text(encoding="utf-8").strip()
        except Exception:
            contenido_lock = "Proceso activo"

        st.warning(f"⏳ Hay un procesamiento en curso ({contenido_lock}). Por favor, espera a que termine para no duplicar tareas.")
        if st.button("⚠️ Forzar desbloqueo", help="Úsalo solo si el proceso anterior falló o se interrumpió", key="btn_forzar_desbloqueo"):
            ruta_lock.unlink(missing_ok=True)
            st.rerun()

    # =========================================================================
    # FORMULARIO PRINCIPAL — Tarjeta envolvente glassmorphic única (#171b26)
    # =========================================================================
    with st.container(border=True):
        st.html('<div class="lf-form-anchor" style="display:none;"></div>')

        # ---------------------------------------------------------------------
        # 1. SELECTOR DE ORIGEN — st.radio interactivo integrado (sin botones sueltos)
        # ---------------------------------------------------------------------
        OPCIONES_ORIGEN = ["upload", "library", "url"]
        TEXTOS_ORIGEN = {
            "upload": ":material/upload: **Subir archivo**\n\nMP4, MKV, MP3, WAV · local",
            "library": ":material/folder_open: **Archivo guardado**\n\nBiblioteca de clases",
            "url": ":material/link: **URL / Enlace remoto**\n\nYouTube, Panopto, Vimeo…",
        }

        # Inicializar default si no existe
        if "lf_origen_radio" not in st.session_state:
            st.session_state["lf_origen_radio"] = "upload"

        metodo_origen_key = st.radio(
            "Método de entrada",
            options=OPCIONES_ORIGEN,
            format_func=lambda k: TEXTOS_ORIGEN.get(k, k),
            horizontal=True,
            label_visibility="collapsed",
            key="lf_origen_radio",
        )

        st.html('<hr class="lf-divider" style="margin: 18px 0 16px 0;">')

        # ---------------------------------------------------------------------
        # 2. REJILLA 5:7 (Asignatura y Tema de la clase)
        # ---------------------------------------------------------------------
        col_form_1, col_form_2 = st.columns([5, 7])

        ruta_archivo_final = None
        url_input = ""
        archivo_cargado = None
        directorio_final = None
        materia_actual = ""
        clase_actual = ""

        with col_form_1:
            st.html("""
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
              <span style="font-family:'Geist',sans-serif; font-size:13px; font-weight:600; color:#dfe2f1;">Asignatura DAW:</span>
              <span style="font-family:'JetBrains Mono',monospace; font-size:10px; font-weight:600; color:#c0c1ff; background:rgba(192,193,255,0.12); border:1px solid rgba(192,193,255,0.25); padding:1px 7px; border-radius:9999px;">Obligatorio</span>
            </div>
            """)

            directorio_base = root_dir / "clases"
            if directorio_base.exists():
                asignaturas_reales = sorted([
                    d.name for d in directorio_base.iterdir()
                    if d.is_dir() and not d.name.startswith(".")
                ])
            else:
                asignaturas_reales = []

            opcion_nueva = "➕ Nueva asignatura..."
            if not asignaturas_reales:
                asignaturas_disponibles = [opcion_nueva]
            else:
                asignaturas_disponibles = asignaturas_reales + [opcion_nueva]

            def formato_asignatura(x):
                if x == opcion_nueva:
                    return x
                return mapeo.get(x, x.replace("_", " "))

            idx_asignatura = 0
            if asignatura_guardada in asignaturas_disponibles:
                idx_asignatura = asignaturas_disponibles.index(asignatura_guardada)

            seleccion_mat = st.selectbox(
                "Asignatura DAW",
                asignaturas_disponibles,
                index=idx_asignatura,
                placeholder="Selecciona una asignatura...",
                format_func=formato_asignatura,
                label_visibility="collapsed",
                key="sel_asignatura_individual",
            )

            if seleccion_mat == opcion_nueva:
                materia_nombre = st.text_input(
                    "Nombre de la nueva asignatura:",
                    placeholder="Ej: Despliegue de Aplicaciones Web",
                    key="txt_nueva_asignatura",
                ).strip()
            elif seleccion_mat:
                materia_nombre = seleccion_mat
            else:
                materia_nombre = ""

        with col_form_2:
            st.html("""
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
              <span style="font-family:'Geist',sans-serif; font-size:13px; font-weight:600; color:#dfe2f1;">Tema de la clase:</span>
              <span style="font-family:'JetBrains Mono',monospace; font-size:10px; font-weight:600; color:#908fa0; background:rgba(144,143,160,0.12); border:1px solid rgba(144,143,160,0.25); padding:1px 7px; border-radius:9999px;">Slug autogenerado</span>
            </div>
            """)

            clase_nombre = st.text_input(
                "Tema de la clase",
                placeholder="Ej: Procedimientos almacenados y funciones",
                label_visibility="collapsed",
                key="txt_tema_clase",
            ).strip()

        # ---------------------------------------------------------------------
        # 3. SECCIÓN CONDICIONAL SEGÚN ORIGEN ACTIVO
        # ---------------------------------------------------------------------
        if metodo_origen_key == "url":
            st.html("""
            <div class="lf-url-banner">
              <div style="display:flex; align-items:center; gap:8px; margin-bottom:8px;">
                <span class="url-icon">link</span>
                <span style="font-family:'Geist',sans-serif; font-weight:600; color:#f8fafc; font-size:0.86rem;">Compatible con más de 30 plataformas de vídeo</span>
              </div>
              <div style="display:flex; flex-wrap:wrap; gap:6px;">
                <span class="lf-platform-pill">YouTube</span>
                <span class="lf-platform-pill">Blackboard Collaborate</span>
                <span class="lf-platform-pill">Panopto</span>
                <span class="lf-platform-pill">Vimeo</span>
                <span class="lf-platform-pill">Twitch</span>
                <span class="lf-platform-pill">Drive / Cloud</span>
              </div>
            </div>
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px; margin-top:10px;">
              <div style="display:flex; align-items:center; gap:6px;">
                <span style="font-family:'Material Symbols Outlined'; font-size:16px; color:#8083ff;">play_circle</span>
                <span style="font-family:'Geist',sans-serif; font-size:13px; font-weight:600; color:#dfe2f1;">URL del vídeo o sesión:</span>
              </div>
              <span style="font-family:'JetBrains Mono',monospace; font-size:10px; font-weight:600; color:#4edea3; background:rgba(78,222,163,0.12); border:1px solid rgba(78,222,163,0.25); padding:1px 7px; border-radius:9999px;">● Detectado: 1080p</span>
            </div>
            """)
            url_input = st.text_input(
                "URL de la clase",
                placeholder="https://www.youtube.com/watch?v=... o https://blackboard.ejemplo.com/...",
                label_visibility="collapsed",
                key="txt_url_remota",
            ).strip()
            if url_input and not es_url_remota(url_input):
                st.warning("⚠️ La URL introducida no parece válida. Debe comenzar por http:// o https://")

        elif metodo_origen_key == "upload":
            st.html("""
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px; margin-top:10px;">
              <div style="display:flex; align-items:center; gap:6px;">
                <span style="font-family:'Material Symbols Outlined'; font-size:16px; color:#8083ff;">cloud_upload</span>
                <span style="font-family:'Geist',sans-serif; font-size:13px; font-weight:600; color:#dfe2f1;">Archivo multimedia local:</span>
              </div>
              <span style="font-family:'JetBrains Mono',monospace; font-size:10px; font-weight:600; color:#c0c1ff; background:rgba(192,193,255,0.12); border:1px solid rgba(192,193,255,0.25); padding:1px 7px; border-radius:9999px;">MP4, MK3, WAV, PPTX</span>
            </div>
            """)
            archivo_cargado = st.file_uploader(
                "Arrastra aquí la grabación o pulsa para seleccionar",
                type=["mp4", "mkv", "mp3", "wav", "m4a", "pptx"],
                help="Aceleración hardware nativa (CUDA / Metal)",
                label_visibility="collapsed",
                key="uploader_archivo_individual",
            )

        else:  # library
            st.html("""
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px; margin-top:10px;">
              <div style="display:flex; align-items:center; gap:6px;">
                <span style="font-family:'Material Symbols Outlined'; font-size:16px; color:#8083ff;">folder_open</span>
                <span style="font-family:'Geist',sans-serif; font-size:13px; font-weight:600; color:#dfe2f1;">Seleccionar de la biblioteca:</span>
              </div>
              <span style="font-family:'JetBrains Mono',monospace; font-size:10px; font-weight:600; color:#908fa0; background:rgba(144,143,160,0.12); border:1px solid rgba(144,143,160,0.25); padding:1px 7px; border-radius:9999px;">Biblioteca local</span>
            </div>
            """)
            encontrados = []
            for r, _, files in os.walk(carpeta_base_str, followlinks=False):
                for arch in files:
                    if arch.lower().endswith((".mp4", ".mkv", ".mov", ".mp3", ".m4a", ".wav", ".pptx")):
                        ruta_c = Path(r) / arch
                        if es_ruta_segura(ruta_c, base=carpeta_base):
                            encontrados.append(str(ruta_c))
            if encontrados:
                opciones = [os.path.relpath(p, carpeta_base_str) for p in encontrados]
                sel = st.selectbox(
                    "Archivo en carpeta",
                    opciones,
                    format_func=lambda x: x.replace(os.sep, " / ").replace("_", " "),
                    label_visibility="collapsed",
                    key="sel_archivo_existente",
                )
                ruta_archivo_final = os.path.realpath(os.path.join(carpeta_base_str, sel))
            else:
                st.info("No hay archivos multimedia en la biblioteca. Procesa primero una clase o sube un archivo.")

        # ---------------------------------------------------------------------
        # 4. CÁPSULA INFORMATIVA DE HARDWARE Y ESTIMACIÓN
        # ---------------------------------------------------------------------
        st.html(f"""
        <div class="lf-hw-strip" style="margin-top:16px;">
          <div style="display:flex; align-items:center; gap:8px;">
            <span class="lf-hw-icon">timer</span>
            <span style="color:#dfe2f1; font-weight:500;">Tiempo estimado: <strong>~15-25 min</strong> para una clase de 45-60 min</span>
          </div>
          <div style="display:flex; align-items:center; gap:8px;">
            <span style="font-family:'JetBrains Mono',monospace; font-size:11px; color:#4edea3; background:rgba(16,185,129,0.15); border:1px solid rgba(16,185,129,0.3); padding:2px 8px; border-radius:9999px;">● Aceleración local activa</span>
            <span style="font-family:'JetBrains Mono',monospace; font-size:11px; color:#94a3b8; background:#1c1f2a; border:1px solid rgba(255,255,255,0.08); padding:2px 8px; border-radius:9999px;">{MODELO_WHISPER} Local</span>
            <span style="font-family:'JetBrains Mono',monospace; font-size:11px; color:#8083ff; background:rgba(128,131,255,0.12); border:1px solid rgba(128,131,255,0.25); padding:2px 8px; border-radius:9999px;">{MODELO_LLM}</span>
          </div>
        </div>
        """)

        # ---------------------------------------------------------------------
        # 5. VALIDACIÓN EXPLÍCITA DE CAMPOS
        # ---------------------------------------------------------------------
        materia_limpia = (materia_nombre or "").strip()
        materia_valida = bool(materia_limpia)

        clase_limpia = (clase_nombre or st.session_state.get("txt_tema_clase", "") or "").strip()
        tema_valido = bool(clase_limpia)

        tiene_url = False
        origen_valido = False
        if metodo_origen_key == "upload":
            arch_actual = archivo_cargado or st.session_state.get("uploader_archivo_individual")
            if arch_actual is not None:
                origen_valido = True
        elif metodo_origen_key == "url":
            url_actual = (url_input or st.session_state.get("txt_url_remota", "") or "").strip()
            if url_actual and es_url_remota(url_actual):
                origen_valido = True
                tiene_url = True
        elif metodo_origen_key == "library":
            if ruta_archivo_final and os.path.exists(ruta_archivo_final):
                origen_valido = True

        faltantes = []
        if not materia_valida:
            faltantes.append("Asignatura")
        if not tema_valido:
            faltantes.append("Tema de la clase")
        if not origen_valido:
            faltantes.append("Archivo multimedia o URL remota")

        # ---------------------------------------------------------------------
        # 6. BOTÓN PRINCIPAL Y OPCIONES AVANZADAS DENTRO DE LA CARD
        # ---------------------------------------------------------------------
        st.write("")
        col_btn1, col_btn2, col_btn3 = st.columns([1, 4, 1])
        with col_btn2:
            btn_iniciar = st.button(
                "🚀 Iniciar Procesamiento",
                type="primary",
                use_container_width=True,
                key="btn_iniciar_individual",
                disabled=en_proceso,
            )
            if faltantes and not en_proceso:
                st.caption(
                    "ℹ️ Completa los campos obligatorios "
                    "(*Asignatura*, *Tema* y *Archivo/URL*) para habilitar el procesamiento."
                )

        with st.expander("⚙️ Opciones avanzadas de procesamiento"):
            st.html("""
            <div style="padding:8px 0;color:#94a3b8;font-size:0.8rem;line-height:1.5;">
              Las opciones de exportación y modelo se configuran desde las variables de entorno
              (<code style="color:#8083ff;">NOTION_TOKEN</code>,
               <code style="color:#8083ff;">TELEGRAM_BOT_TOKEN</code>).
              El modelo de transcripción y síntesis se selecciona automáticamente según el hardware disponible.
            </div>
            """)

    # =========================================================================
    # FLUJO DE TRABAJO — tarjeta glassmorphic informativa
    # =========================================================================
    st.html("""
    <div class="lf-glass-card" style="margin-top:12px;">
      <p class="lf-section-label">Flujo de trabajo automático</p>
      <ol style="margin:0;color:#8b90ab;font-size:0.85rem;padding-left:20px;line-height:2;">
        <li><strong style="color:#e2e6f8;">Descarga (URLs):</strong> yt-dlp extrae la pista de audio en local.</li>
        <li><strong style="color:#e2e6f8;">Transcripción:</strong> Whisper en local (CUDA / Metal) detectando marcas [HH:MM:SS].</li>
        <li><strong style="color:#e2e6f8;">Síntesis:</strong> Ollama estructura conceptos, código y autoevaluación.</li>
        <li><strong style="color:#e2e6f8;">Auditoría Determinísta:</strong> Validación matemática de sintaxis, código y orden cronológico.</li>
      </ol>
    </div>
    """)

    # =========================================================================
    # HISTORIAL — Grid de sesiones recientes
    # =========================================================================
    clases_recientes = []
    if carpeta_base.exists():
        for mat_dir in sorted(carpeta_base.iterdir()):
            if not mat_dir.is_dir():
                continue
            for clase_dir in sorted(mat_dir.iterdir(), reverse=True):
                if not clase_dir.is_dir():
                    continue
                apuntes_path = clase_dir / "apuntes.md"
                if apuntes_path.exists():
                    ts = apuntes_path.stat().st_mtime
                    clases_recientes.append({
                        "materia": mapeo.get(mat_dir.name, mat_dir.name.replace("_", " ")),
                        "clase": clase_dir.name.replace("_", " "),
                        "fecha": time.strftime("%d/%m/%Y", time.localtime(ts)),
                    })
                if len(clases_recientes) >= 6:
                    break
            if len(clases_recientes) >= 6:
                break

    if clases_recientes:
        st.html('<hr class="lf-divider"><p class="lf-section-label">Sesiones recientes</p>')
        items_html = "".join([
            f"""<div class="lf-history-item">
              <div class="lf-history-materia">{c['materia']}</div>
              <div class="lf-history-clase">{c['clase']}</div>
              <div class="lf-history-meta">📄 apuntes.md · {c['fecha']}</div>
            </div>"""
            for c in clases_recientes
        ])
        st.html(f'<div class="lf-history-grid">{items_html}</div>')

    # =========================================================================
    # EJECUCIÓN DEL PIPELINE
    # =========================================================================
    if btn_iniciar or st.session_state.get("modo_reanudacion") is not None:
        if en_proceso and st.session_state.get("modo_reanudacion") is None:
            st.warning("⏳ Ya hay un procesamiento en curso. Espera a que termine.")
            st.stop()

        if len(faltantes) > 0:
            st.error(
                f"⚠️ No se puede iniciar el procesamiento. "
                f"Faltan los siguientes campos obligatorios: **{', '.join(faltantes)}**."
            )
            st.stop()

        mat_segura = normalizar_nombre(materia_limpia)
        cla_segura = normalizar_nombre(clase_limpia)

        if metodo_origen_key == "upload":
            fichero_seguro = os.path.basename(normalizar_nombre(archivo_cargado.name))
            directorio_tentativo = carpeta_base / mat_segura / cla_segura
            if not es_ruta_segura(directorio_tentativo, base=carpeta_base):
                st.error("⚠️ La ruta de destino no es segura.")
                st.stop()
            directorio_final = str(directorio_tentativo)
            os.makedirs(directorio_final, exist_ok=True)
            ruta_archivo_final = str(directorio_tentativo / fichero_seguro)
            with open(ruta_archivo_final, "wb") as f:
                f.write(archivo_cargado.getbuffer())
            materia_actual = mat_segura
            clase_actual = cla_segura
            video_path_para_pipeline = ruta_archivo_final

        elif metodo_origen_key == "url":
            directorio_tentativo = carpeta_base / mat_segura / cla_segura
            if not es_ruta_segura(directorio_tentativo, base=carpeta_base):
                st.error("⚠️ La ruta de destino no es segura.")
                st.stop()
            directorio_final = str(directorio_tentativo)
            os.makedirs(directorio_final, exist_ok=True)
            url_remota_final = url_input
            materia_actual = mat_segura
            clase_actual = cla_segura
            video_path_para_pipeline = url_remota_final

        elif metodo_origen_key == "library":
            directorio_final = os.path.dirname(ruta_archivo_final)
            materia_actual = mat_segura
            clase_actual = cla_segura
            video_path_para_pipeline = ruta_archivo_final

        os.makedirs(directorio_final, exist_ok=True)
        ruta_apuntes = os.path.join(directorio_final, "apuntes.md")

        # Detección y diálogo de checkpoints de sesión previa (solo archivos locales)
        estado_previo = None if tiene_url else leer_estado_si_existe(directorio_final)
        if estado_previo is not None and st.session_state.get("modo_reanudacion") is None:
            fase_guardada = estado_previo.get("fase_actual", "desconocida")
            ts_guardado = estado_previo.get("ultimo_timestamp", 0.0)
            segs_guardados = len(estado_previo.get("segmentos_transcritos", []))
            fecha_upd = estado_previo.get("fecha_actualizacion", "")

            st.info(
                f"**Sesión previa detectada** para este archivo.  \n"
                f"Fase: `{fase_guardada}` | Tiempo cubierto: `{ts_guardado:.0f}s` | "
                f"Segmentos: `{segs_guardados}` | Última actualización: `{fecha_upd[:19].replace('T', ' ')} UTC`"
            )
            col_r1, col_r2 = st.columns(2)
            with col_r1:
                if st.button(
                    "Reanudar sesión previa",
                    key="btn_reanudar_checkpoint",
                    use_container_width=True,
                    type="primary",
                ):
                    st.session_state["modo_reanudacion"] = True
                    st.session_state["directorio_pipeline"] = directorio_final
                    st.rerun()
            with col_r2:
                if st.button(
                    "Empezar de nuevo",
                    key="btn_nuevo_checkpoint",
                    use_container_width=True,
                ):
                    cp_purga = CheckpointManager(directorio_final, ruta_archivo_final)
                    cp_purga.purgar()
                    st.session_state["modo_reanudacion"] = False
                    st.session_state["directorio_pipeline"] = directorio_final
                    st.rerun()
            st.stop()

        reanudar = st.session_state.get("modo_reanudacion") is True
        st.session_state["modo_reanudacion"] = None
        st.session_state["directorio_pipeline"] = None

        # Conexión de callbacks con la consola y barra de progreso de Streamlit
        barra_progreso = st.progress(0, text="Iniciando pipeline de estudio...")
        estado_actual = st.status("Ejecutando pipeline unificado...", expanded=True)

        render_terminal_topbar("stdout - pipeline_local.py")
        caja_consola = st.empty()
        lineas_consola = []

        def cb_progreso_indiv(fase: str, pct: int, msg: str):
            barra_progreso.progress(pct, text=msg)
            estado_actual.update(label=f"[{fase.upper()}] {msg}", state="running")

        def cb_linea_indiv(linea: str):
            lineas_consola.append(linea)
            caja_consola.code("".join(lineas_consola[-8:]), language="bash")

        if orquestador is None:
            orq = PipelineOrchestrator(
                callback_progreso=cb_progreso_indiv,
                callback_linea=cb_linea_indiv,
            )
        else:
            orq = orquestador
            orq.callback_progreso = cb_progreso_indiv
            orq.callback_linea = cb_linea_indiv

        materia_proc = materia_actual or "General"
        tema_proc = clase_actual or os.path.basename(directorio_final)

        # Crear el lockfile justo antes de invocar el orquestador
        ruta_lock.parent.mkdir(parents=True, exist_ok=True)
        ruta_lock.write_text(f"{materia_proc} - {tema_proc}", encoding="utf-8")

        try:
            exportar_notion_activo = notion_configurado()
            try:
                resultado = orq.procesar_clase(
                    video_path=video_path_para_pipeline,
                    materia=materia_proc,
                    nombre_clase=tema_proc,
                    modo_reanudacion=reanudar,
                    exportar_notion=exportar_notion_activo,
                )
            finally:
                ruta_lock.unlink(missing_ok=True)

            if not resultado.get("exito"):
                raise RuntimeError(resultado.get("error") or "Error en el pipeline de procesamiento.")

            barra_progreso.progress(100, text="¡Completado con éxito!")
            estado_actual.update(label="🎉 ¡Clase procesada y archivada!", state="complete", expanded=False)

            if os.path.exists(ruta_apuntes):
                st.divider()
                col_p_tit, col_p_btn = st.columns([3, 1])
                with col_p_tit:
                    st.subheader("📝 Vista Previa de los Apuntes Generados")
                with col_p_btn:
                    if st.button(
                        "🚀 Enviar a Notion ahora",
                        key="btn_notion_preview",
                        use_container_width=True,
                        type="primary",
                    ):
                        with st.spinner("Sincronizando con Notion..."):
                            try:
                                with open(ruta_apuntes, "r", encoding="utf-8") as f:
                                    texto_md = f.read()
                                mat_exp = materia_actual or "General"
                                cla_exp = clase_actual or os.path.basename(directorio_final)
                                t_inicio_export = time.monotonic()
                                url_notion = exportar_a_notion(cla_exp, mat_exp, texto_md)
                                cp_completado = CheckpointManager(directorio_final, ruta_archivo_final)
                                cp_completado.marcar_completado()
                                st.success("¡Exportado a Notion con éxito!")
                                st.markdown(f"[🔗 Abrir en Notion]({url_notion})")
                                dur_seg = int(time.monotonic() - t_inicio_export)
                                dur_str = f"{dur_seg // 60}m {dur_seg % 60}s"
                                notificar_clase_completada(
                                    nombre_clase=cla_exp,
                                    duracion=dur_str,
                                    url_notion=url_notion,
                                )
                            except Exception as err:
                                st.error(f"Error al exportar: {err}")

                with open(ruta_apuntes, "r", encoding="utf-8") as f:
                    st.markdown(f.read())

        except Exception as e:
            estado_actual.update(label="❌ Error durante la ejecución", state="error")
            st.error(f"Fallo detectado: {e}")
