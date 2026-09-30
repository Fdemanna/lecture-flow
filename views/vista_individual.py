"""Módulo de procesamiento individual: subida de archivos, ejecución del pipeline y checkpointing."""
import os
from pathlib import Path
import time
from typing import Optional, Dict
import streamlit as st

from src.orchestrator import PipelineOrchestrator, normalizar_nombre, es_ruta_segura
from src.downloader import es_url_remota
from src.notion_exporter import exportar_a_notion
from src.checkpoint_manager import leer_estado_si_existe, CheckpointManager
from src.notificador import notificar_clase_completada
from views.estilos import render_terminal_topbar
from views.sidebar import MAPEO_ASIGNATURAS


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

    metodo_origen = st.radio(
        "Origen del material:",
        ["Subir nuevo archivo", "Usar un archivo ya guardado", "URL / Enlace remoto"],
        horizontal=True
    )

    ruta_archivo_final = None   # Ruta local al fichero de audio/vídeo
    url_remota_final = None     # URL remota si el usuario la pega
    directorio_final = None
    materia_actual = ""
    clase_actual = ""

    col_form_1, col_form_2 = st.columns(2)
    with col_form_1:
        asignaturas_base = [k for k in mapeo.keys() if k != "Otra"]
        materias_carpetas = sorted([
            d for d in os.listdir(carpeta_base_str)
            if (carpeta_base / d).is_dir()
        ])

        asignaturas_disponibles = []
        for m in asignaturas_base + materias_carpetas:
            if m not in asignaturas_disponibles:
                asignaturas_disponibles.append(m)

        opcion_nueva = "➕ Añadir nueva asignatura..."
        asignaturas_disponibles.append(opcion_nueva)

        def formato_asignatura(x):
            if x == opcion_nueva:
                return x
            return mapeo.get(x, x.replace("_", " "))

        seleccion_mat = st.selectbox(
            "Asignatura DAW:",
            asignaturas_disponibles,
            format_func=formato_asignatura
        )

        if seleccion_mat == opcion_nueva:
            materia_nombre = st.text_input(
                "Nombre de la nueva asignatura:",
                placeholder="Ej: Despliegue de Aplicaciones Web"
            ).strip()
        else:
            materia_nombre = seleccion_mat

    with col_form_2:
        clase_nombre = st.text_input(
            "Tema de la clase:",
            placeholder="Ej: Procedimientos almacenados y funciones"
        ).strip()

    if metodo_origen == "Subir nuevo archivo":
        archivo_cargado = st.file_uploader(
            "Arrastra aquí la grabación o pulsa para seleccionar (MP4, MKV, MP3, WAV)",
            type=["mp4", "mkv", "mp3", "m4a", "wav"],
            help="Aceleración hardware nativa (CUDA / Metal)"
        )
        if archivo_cargado and materia_nombre and clase_nombre:
            mat_segura = normalizar_nombre(materia_nombre)
            cla_segura = normalizar_nombre(clase_nombre)
            fichero_seguro = os.path.basename(normalizar_nombre(archivo_cargado.name))

            directorio_tentativo = carpeta_base / mat_segura / cla_segura
            if es_ruta_segura(directorio_tentativo, base=carpeta_base):
                directorio_final = str(directorio_tentativo)
                os.makedirs(directorio_final, exist_ok=True)
                ruta_archivo_final = str(directorio_tentativo / fichero_seguro)
                with open(ruta_archivo_final, "wb") as f:
                    f.write(archivo_cargado.getbuffer())
                materia_actual = mat_segura
                clase_actual = cla_segura

    elif metodo_origen == "URL / Enlace remoto":
        st.info(
            "🔗 Pega el enlace de la clase — compatible con YouTube, Blackboard Collaborate, "
            "Panopto, Vimeo, Twitch y la mayoría de plataformas de vídeo."
        )
        url_input = st.text_input(
            "URL de la clase:",
            placeholder="https://www.youtube.com/watch?v=... o https://blackboard.ejemplo.com/...",
            key="txt_url_remota",
        ).strip()

        if url_input and not es_url_remota(url_input):
            st.warning("⚠️ La URL introducida no parece válida. Debe comenzar por http:// o https://")

        if url_input and es_url_remota(url_input) and materia_nombre and clase_nombre:
            mat_segura = normalizar_nombre(materia_nombre)
            cla_segura = normalizar_nombre(clase_nombre)
            directorio_tentativo = carpeta_base / mat_segura / cla_segura
            if es_ruta_segura(directorio_tentativo, base=carpeta_base):
                directorio_final = str(directorio_tentativo)
                os.makedirs(directorio_final, exist_ok=True)
                url_remota_final = url_input
                materia_actual = mat_segura
                clase_actual = cla_segura

    else:
        encontrados = []
        for r, _, files in os.walk(carpeta_base_str, followlinks=False):
            for arch in files:
                if arch.lower().endswith((".mp4", ".mkv", ".mov", ".mp3", ".m4a", ".wav")):
                    ruta_c = Path(r) / arch
                    if es_ruta_segura(ruta_c, base=carpeta_base):
                        encontrados.append(str(ruta_c))
        if encontrados:
            opciones = [os.path.relpath(p, carpeta_base_str) for p in encontrados]
            sel = st.selectbox(
                "Archivo en carpeta:",
                opciones,
                format_func=lambda x: x.replace(os.sep, " / ").replace("_", " ")
            )
            ruta_archivo_final = os.path.realpath(os.path.join(carpeta_base_str, sel))
            directorio_final = os.path.dirname(ruta_archivo_final)
            partes = os.path.relpath(directorio_final, carpeta_base_str).split(os.sep)
            if len(partes) >= 2:
                materia_actual = partes[0]
                clase_actual = partes[1]

    st.write("")
    st.info("⏱ **Tiempo estimado:** Una clase de ~45 min suele tardar entre 15 y 25 minutos según tu hardware. Puedes dejar la ventana abierta en segundo plano.")

    col_btn1, col_btn2, col_btn3 = st.columns([1, 2, 1])
    with col_btn2:
        btn_iniciar = st.button("🚀 Iniciar Procesamiento", type="primary", use_container_width=True)

    st.html("""
    <div style="margin-top: 30px; padding: 20px; background-color: #131b2e; border-radius: 8px; border: 1px solid rgba(255,255,255,0.06);">
      <h5 style="margin-top:0; color:#dae2fd;">Flujo de trabajo automático</h5>
      <ol style="margin-bottom:0; color:#908fa0; font-size:0.9rem; padding-left:20px;">
        <li style="margin-bottom:8px;"><strong>Descarga (URLs):</strong> yt-dlp extrae la pista de audio en local.</li>
        <li style="margin-bottom:8px;"><strong>Transcripción:</strong> Whisper en local (CUDA / Metal) detectando marcas [HH:MM:SS].</li>
        <li style="margin-bottom:8px;"><strong>Síntesis:</strong> Ollama estructura conceptos, código y autoevaluación.</li>
        <li><strong>Auditoría Determinísta:</strong> Validación matemática de sintaxis, código y orden cronológico.</li>
      </ol>
    </div>
    """)

    if btn_iniciar:
        # Validar que hay un origen válido (archivo o URL)
        tiene_archivo = ruta_archivo_final and os.path.exists(ruta_archivo_final)
        tiene_url = url_remota_final and es_url_remota(url_remota_final)
        video_path_para_pipeline = url_remota_final if tiene_url else ruta_archivo_final

        if not tiene_archivo and not tiene_url:
            if metodo_origen == "URL / Enlace remoto":
                st.error("Por favor, introduce una URL válida que comience por http:// o https://")
            else:
                st.error("Por favor, selecciona o sube un archivo de clase válido.")
        elif not directorio_final:
            st.error("Indica una materia y tema para la clase.")
        else:
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

            try:
                resultado = orq.procesar_clase(
                    video_path=video_path_para_pipeline,
                    materia=materia_actual or "General",
                    nombre_clase=clase_actual or os.path.basename(directorio_final),
                    modo_reanudacion=reanudar,
                    exportar_notion=False,
                )

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
                        if st.button("🚀 Enviar a Notion ahora", key="btn_notion_preview", use_container_width=True, type="primary"):
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
