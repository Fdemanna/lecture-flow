import os
import shutil
import subprocess
import sys
import time
import streamlit as st
from procesar_clase import normalizar_nombre
from notion_exporter import exportar_a_notion

CARPETA_BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "clases")
os.makedirs(CARPETA_BASE, exist_ok=True)

st.set_page_config(
    page_title="LectureFlow - Asistente de Estudio",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Inyección de estilos limpia compatible con Streamlit
st.html("""
<style>
  /* Ocultar elementos decorativos nativos */
  #MainMenu {visibility: hidden;}
  footer {visibility: hidden;}
  header {background-color: transparent !important;}
  
  /* Ajustes de tipografía y tarjetas */
  .stApp {
    background-color: #0b1326;
    color: #dae2fd;
  }
  
  /* Badges y chips estilo Stitch */
  .badge-m4-chip {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background-color: #131b2e;
    color: #4edea3;
    font-family: ui-monospace, Menlo, Monaco, Consolas, monospace;
    font-size: 0.75rem;
    padding: 3px 10px;
    border-radius: 9999px;
    border: 1px solid rgba(78, 222, 163, 0.2);
    font-weight: 500;
  }
  .dot-ping {
    width: 6px;
    height: 6px;
    border-radius: 9999px;
    background-color: #4edea3;
  }
  .terminal-topbar {
    background-color: #131b2e;
    padding: 6px 12px;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
    display: flex;
    align-items: center;
    gap: 6px;
    font-family: monospace;
    font-size: 0.75rem;
    color: #908fa0;
    border: 1px solid rgba(255,255,255,0.06);
    border-bottom: none;
    margin-top: 14px;
  }
</style>
""")

if "clase_seleccionada" not in st.session_state:
    st.session_state["clase_seleccionada"] = None
if "materia_seleccionada" not in st.session_state:
    st.session_state["materia_seleccionada"] = None

TIMEOUT_SEGUNDOS = 14400  # 4 horas para clases largas (>1.5h)


def es_ruta_segura(ruta_destino: str) -> bool:
    base_real = os.path.realpath(CARPETA_BASE)
    candidata_real = os.path.realpath(ruta_destino)
    return candidata_real.startswith(base_real + os.sep)


def ejecutar_paso_con_progreso(comando, caja_texto, contenedor_estado, mensaje_estado):
    contenedor_estado.update(label=mensaje_estado, state="running")
    proceso = subprocess.Popen(
        comando,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        universal_newlines=True
    )
    try:
        lineas_consola = []
        t_inicio = time.monotonic()
        while True:
            linea = proceso.stdout.readline()
            if not linea and proceso.poll() is not None:
                break
            if linea:
                lineas_consola.append(linea)
                caja_texto.code("".join(lineas_consola[-8:]), language="bash")
            if TIMEOUT_SEGUNDOS is not None and (time.monotonic() - t_inicio > TIMEOUT_SEGUNDOS):
                proceso.kill()
                raise TimeoutError("Timeout: Subproceso excedió el tiempo límite.")
    finally:
        if proceso.stdout:
            proceso.stdout.close()
    codigo_salida = proceso.wait()
    if codigo_salida != 0:
        raise subprocess.CalledProcessError(codigo_salida, comando)


# ---------------------------------------------------------------------------
# MENÚ LATERAL: ASIGNATURAS Y GESTIÓN
# ---------------------------------------------------------------------------
st.sidebar.markdown("### 📚 Asignaturas DAW")

if st.sidebar.button("➕ Subir / Nueva Clase", use_container_width=True, type="primary"):
    st.session_state["clase_seleccionada"] = None
    st.session_state["materia_seleccionada"] = None
    st.rerun()

st.sidebar.divider()

materias_existentes = sorted([
    d for d in os.listdir(CARPETA_BASE)
    if os.path.isdir(os.path.join(CARPETA_BASE, d))
])

if materias_existentes:
    for m in materias_existentes:
        with st.sidebar.expander(f"📁 {m.replace('_', ' ')}", expanded=True):
            ruta_m = os.path.join(CARPETA_BASE, m)
            clases_m = sorted([
                c for c in os.listdir(ruta_m)
                if os.path.isdir(os.path.join(ruta_m, c))
            ])
            if clases_m:
                for c in clases_m:
                    if st.button(f"📄 {c.replace('_', ' ')}", key=f"btn_{m}_{c}", use_container_width=True):
                        st.session_state["materia_seleccionada"] = m
                        st.session_state["clase_seleccionada"] = c
                        st.rerun()
            else:
                st.caption("Sin clases registradas.")

    st.sidebar.divider()
    with st.sidebar.expander("⚙️ Administrar Materias"):
        mat_admin = st.selectbox("Materia:", materias_existentes, key="sb_admin_m")
        nom_nuevo_m = st.text_input("Nuevo nombre:", value=mat_admin.replace('_', ' '), key="txt_admin_m")
        col_r_m, col_b_m = st.columns(2)
        with col_r_m:
            if st.button("✏️ Renombrar", use_container_width=True):
                sanit = normalizar_nombre(nom_nuevo_m.strip())
                if sanit and sanit != mat_admin:
                    os.rename(os.path.join(CARPETA_BASE, mat_admin), os.path.join(CARPETA_BASE, sanit))
                    st.rerun()
        with col_b_m:
            if st.button("🗑️ Borrar", use_container_width=True):
                shutil.rmtree(os.path.join(CARPETA_BASE, mat_admin))
                st.rerun()


# ---------------------------------------------------------------------------
# ÁREA PRINCIPAL
# ---------------------------------------------------------------------------
# Header superior con badges
st.html("""
<div style="display: flex; justify-content: space-between; align-items: center; padding: 12px 18px; background-color: #171f33; border-radius: 10px; border: 1px solid rgba(255,255,255,0.06); margin-bottom: 20px;">
  <div style="display: flex; align-items: center; gap: 12px;">
    <span style="font-size: 24px;">🎓</span>
    <div>
      <div style="display: flex; align-items: center; gap: 8px;">
        <span style="font-weight: 700; color: #dae2fd; font-size: 1.05rem;">LectureFlow</span>
        <span style="font-size: 0.75rem; color: #908fa0;">/ Procesar</span>
      </div>
      <div style="display: flex; align-items: center; gap: 6px;">
        <span class="dot-ping"></span>
        <span style="font-size: 0.7rem; color: #4edea3;">Apple Silicon M4 • Local LLM</span>
      </div>
    </div>
  </div>
  <div class="badge-m4-chip">
    <span class="dot-ping"></span> M4 Ready
  </div>
</div>
""")

if st.session_state["clase_seleccionada"] and st.session_state["materia_seleccionada"]:
    # VISTA DE CLASE SELECCIONADA
    mat = st.session_state["materia_seleccionada"]
    cla = st.session_state["clase_seleccionada"]
    carpeta_clase = os.path.join(CARPETA_BASE, mat, cla)

    if not os.path.exists(carpeta_clase):
        st.session_state["clase_seleccionada"] = None
        st.rerun()

    apuntes_path = os.path.join(carpeta_clase, "apuntes.md")
    auditoria_path = os.path.join(carpeta_clase, "apuntes_auditoria.md")
    transcripcion_path = os.path.join(carpeta_clase, "transcripcion.txt")

    col_tit, col_notion, col_btn = st.columns([3, 1, 1])
    with col_tit:
        st.title(f"📖 {cla.replace('_', ' ')}")
        st.caption(f"Asignatura: **{mat.replace('_', ' ')}**")
    with col_notion:
        if os.path.exists(apuntes_path):
            if st.button("🚀 Enviar a Notion", use_container_width=True, type="primary"):
                with st.spinner("Sincronizando con Notion..."):
                    try:
                        with open(apuntes_path, "r", encoding="utf-8") as f:
                            texto_md = f.read()
                        url_notion = exportar_a_notion(cla, mat, texto_md)
                        st.success("¡Exportado a Notion!")
                        st.markdown(f"[🔗 Abrir en Notion]({url_notion})")
                    except Exception as err:
                        st.error(f"Error al exportar: {err}")
    with col_btn:
        if st.button("⬅️ Nueva Clase", use_container_width=True):
            st.session_state["clase_seleccionada"] = None
            st.session_state["materia_seleccionada"] = None
            st.rerun()

    tab1, tab2, tab3 = st.tabs(["📝 Apuntes y Ejemplos", "🔍 Control de Alucinaciones", "📜 Transcripción Cruda"])
    with tab1:
        if os.path.exists(apuntes_path):
            with open(apuntes_path, "r", encoding="utf-8") as f:
                st.markdown(f.read())
        else:
            st.warning("Apuntes pendientes de generación.")
    with tab2:
        if os.path.exists(auditoria_path):
            with open(auditoria_path, "r", encoding="utf-8") as f:
                st.markdown(f.read())
        else:
            st.info("No hay auditoría generada.")
    with tab3:
        if os.path.exists(transcripcion_path):
            with open(transcripcion_path, "r", encoding="utf-8") as f:
                st.text_area("Transcripción:", f.read(), height=450)

else:
    # VISTA CONSOLA DE PROCESAMIENTO
    st.markdown("#### ⚡ Consola de Procesamiento Local")
    st.caption("MLX Whisper + Qwen 2.5 (Local M4) • GPU 16-Core")

    metodo_origen = st.radio(
        "Origen del material:",
        ["Subir nuevo archivo", "Elegir en /clases"],
        horizontal=True
    )

    ruta_archivo_final = None
    directorio_final = None
    materia_actual = ""
    clase_actual = ""

    col_form_1, col_form_2 = st.columns(2)
    with col_form_1:
        asignaturas_disponibles = [
            "Bases_de_Datos",
            "Programacion",
            "Lenguajes_de_Marcas",
            "Entornos_de_Desarrollo",
            "Otra"
        ]
        seleccion_mat = st.selectbox("Asignatura DAW:", asignaturas_disponibles)
        materia_nombre = st.text_input("Nombre de la asignatura:").strip() if seleccion_mat == "Otra" else seleccion_mat

    with col_form_2:
        clase_nombre = st.text_input("Tema de la clase:", placeholder="Tema_04_Procedimientos").strip()

    if metodo_origen == "Subir nuevo archivo":
        archivo_cargado = st.file_uploader(
            "Arrastra aquí la grabación o pulsa para seleccionar (MP4, MKV, MP3, WAV)",
            type=["mp4", "mkv", "mp3", "m4a", "wav"],
            help="Aceleración nativa con Metal M4"
        )
        if archivo_cargado and materia_nombre and clase_nombre:
            mat_segura = normalizar_nombre(materia_nombre)
            cla_segura = normalizar_nombre(clase_nombre)
            fichero_seguro = os.path.basename(normalizar_nombre(archivo_cargado.name))

            directorio_tentativo = os.path.abspath(os.path.join(CARPETA_BASE, mat_segura, cla_segura))
            if es_ruta_segura(directorio_tentativo):
                directorio_final = directorio_tentativo
                os.makedirs(directorio_final, exist_ok=True)
                ruta_archivo_final = os.path.join(directorio_final, fichero_seguro)
                with open(ruta_archivo_final, "wb") as f:
                    f.write(archivo_cargado.getbuffer())
                materia_actual = mat_segura
                clase_actual = cla_segura
    else:
        encontrados = []
        for r, _, files in os.walk(CARPETA_BASE, followlinks=False):
            for arch in files:
                if arch.lower().endswith((".mp4", ".mkv", ".mov", ".mp3", ".m4a", ".wav")):
                    ruta_c = os.path.realpath(os.path.join(r, arch))
                    if es_ruta_segura(ruta_c):
                        encontrados.append(os.path.join(r, arch))
        if encontrados:
            opciones = [os.path.relpath(p, CARPETA_BASE) for p in encontrados]
            sel = st.selectbox("Archivo en carpeta:", opciones)
            ruta_archivo_final = os.path.realpath(os.path.join(CARPETA_BASE, sel))
            directorio_final = os.path.dirname(ruta_archivo_final)
            partes = os.path.relpath(directorio_final, CARPETA_BASE).split(os.sep)
            if len(partes) >= 2:
                materia_actual = partes[0]
                clase_actual = partes[1]

    st.write("")
    btn_iniciar = st.button("🚀 Iniciar Procesamiento con Apple Silicon", type="primary", use_container_width=True)

    if btn_iniciar:
        if not ruta_archivo_final or not os.path.exists(ruta_archivo_final):
            st.error("Por favor, selecciona o sube un archivo de clase válido.")
        elif not directorio_final:
            st.error("Indica una materia y tema para la clase.")
        else:
            os.makedirs(directorio_final, exist_ok=True)
            ruta_transcripcion = os.path.join(directorio_final, "transcripcion.txt")
            ruta_apuntes = os.path.join(directorio_final, "apuntes.md")

            barra_progreso = st.progress(0, text="Iniciando pipeline de estudio...")
            estado_actual = st.status("Ejecutando pipeline unificado...", expanded=True)

            st.html("""
            <div class="terminal-topbar">
              <span style="color:#ff5f56;">●</span>
              <span style="color:#ffbd2e;">●</span>
              <span style="color:#27c93f;">●</span>
              <span style="margin-left: 8px;">stdout - pipeline_local.py</span>
            </div>
            """)
            caja_consola = st.empty()

            try:
                # 1. Audio y Transcripción
                transcripcion_previa = os.path.exists(ruta_transcripcion) and os.path.getsize(ruta_transcripcion) > 0
                if transcripcion_previa:
                    barra_progreso.progress(50, text="Paso 1/2 omitido: Transcripción previa detectada.")
                    caja_consola.code("[INFO] Se reutiliza 'transcripcion.txt' existente.", language="bash")
                else:
                    barra_progreso.progress(15, text="Paso 1/2: Extrayendo PCM WAV y transcribiendo con MLX...")
                    cmd_transcribir = [sys.executable, "-u", "transcribir.py", ruta_archivo_final, ruta_transcripcion]
                    ejecutar_paso_con_progreso(cmd_transcribir, caja_consola, estado_actual, "Paso 1/2: MLX-Whisper transcribiendo...")
                    barra_progreso.progress(50, text="Transcripción completada.")

                # 2. Generación con Qwen 2.5
                barra_progreso.progress(65, text="Paso 2/2: Sintetizando apuntes y auditando con Qwen 2.5...")
                cmd_apuntes = [sys.executable, "-u", "generar_apuntes.py", ruta_transcripcion, ruta_apuntes]
                ejecutar_paso_con_progreso(cmd_apuntes, caja_consola, estado_actual, "Paso 2/2: Síntesis Map-Reduce...")

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
                                    url_notion = exportar_a_notion(cla_exp, mat_exp, texto_md)
                                    st.success("¡Exportado a Notion con éxito!")
                                    st.markdown(f"[🔗 Abrir en Notion]({url_notion})")
                                except Exception as err:
                                    st.error(f"Error al exportar: {err}")

                    with open(ruta_apuntes, "r", encoding="utf-8") as f:
                        st.markdown(f.read())

            except Exception as e:
                estado_actual.update(label="❌ Error durante la ejecución", state="error")
                st.error(f"Fallo detectado: {e}")