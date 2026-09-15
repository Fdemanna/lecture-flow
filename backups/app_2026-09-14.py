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
    page_title="Asistente DAW - Clases",
    page_icon="🎓",
    layout="wide"
)

if "clase_seleccionada" not in st.session_state:
    st.session_state["clase_seleccionada"] = None
if "materia_seleccionada" not in st.session_state:
    st.session_state["materia_seleccionada"] = None

TIMEOUT_SEGUNDOS = 900  # 15 min máx por paso


def es_ruta_segura(ruta_destino: str) -> bool:
    """Valida que la ruta absoluta esté contenida estrictamente en CARPETA_BASE."""
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
            if time.monotonic() - t_inicio > TIMEOUT_SEGUNDOS:
                proceso.kill()
                raise TimeoutError(
                    "El paso superó el límite de tiempo. "
                    "Ollama o el subproceso pueden estar bloqueados."
                )
    finally:
        if proceso.stdout:
            proceso.stdout.close()
    codigo_salida = proceso.wait()
    if codigo_salida != 0:
        raise subprocess.CalledProcessError(codigo_salida, comando)


# ---------------------------------------------------------------------------
# MENÚ LATERAL: NAVEGACIÓN Y GESTIÓN DE MATERIAS
# ---------------------------------------------------------------------------
st.sidebar.title("📚 Asignaturas DAW")

if st.sidebar.button("➕ Subir / Procesar Nueva Clase", use_container_width=True, type="primary"):
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
        materia_a_gestionar = st.selectbox("Seleccionar materia:", materias_existentes, key="sb_materia_admin")
        nuevo_nombre_mat = st.text_input("Nuevo nombre:", value=materia_a_gestionar.replace('_', ' '), key="txt_renombrar_mat")

        col_ren_m, col_del_m = st.columns(2)
        with col_ren_m:
            if st.button("✏️ Renombrar", use_container_width=True, key="btn_ren_mat"):
                nombre_sanitizado = normalizar_nombre(nuevo_nombre_mat.strip())
                if nombre_sanitizado and nombre_sanitizado != materia_a_gestionar:
                    ruta_antigua = os.path.join(CARPETA_BASE, materia_a_gestionar)
                    ruta_nueva = os.path.join(CARPETA_BASE, nombre_sanitizado)
                    if es_ruta_segura(ruta_nueva):
                        if os.path.exists(ruta_nueva):
                            st.sidebar.error("Ya existe una materia con ese nombre.")
                        else:
                            os.rename(ruta_antigua, ruta_nueva)
                            if st.session_state["materia_seleccionada"] == materia_a_gestionar:
                                st.session_state["materia_seleccionada"] = nombre_sanitizado
                            st.rerun()
                    else:
                        st.sidebar.error("Ruta de materia no permitida.")

        with col_del_m:
            if st.button("🗑️ Borrar", use_container_width=True, key="btn_del_mat"):
                st.session_state["confirmar_borrado_mat"] = materia_a_gestionar

        if st.session_state.get("confirmar_borrado_mat") == materia_a_gestionar:
            st.sidebar.warning(f"¿Eliminar '{materia_a_gestionar.replace('_', ' ')}' y todo su contenido?")
            col_si, col_no = st.sidebar.columns(2)
            if col_si.button("Sí, borrar", type="primary", use_container_width=True, key="btn_conf_del_mat"):
                ruta_borrar = os.path.join(CARPETA_BASE, materia_a_gestionar)
                if es_ruta_segura(ruta_borrar):
                    shutil.rmtree(ruta_borrar)
                    if st.session_state["materia_seleccionada"] == materia_a_gestionar:
                        st.session_state["materia_seleccionada"] = None
                        st.session_state["clase_seleccionada"] = None
                    st.session_state["confirmar_borrado_mat"] = None
                    st.rerun()
            if col_no.button("Cancelar", use_container_width=True, key="btn_canc_del_mat"):
                st.session_state["confirmar_borrado_mat"] = None
                st.rerun()
else:
    st.sidebar.info("Aún no hay materias registradas.")


# ---------------------------------------------------------------------------
# ÁREA PRINCIPAL
# ---------------------------------------------------------------------------
if st.session_state["clase_seleccionada"] and st.session_state["materia_seleccionada"]:
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
        st.caption(f"Materia: **{mat.replace('_', ' ')}**")
    with col_notion:
        if os.path.exists(apuntes_path):
            if st.button("🚀 Enviar a Notion", use_container_width=True):
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
        if st.button("⬅️ Volver al Inicio", use_container_width=True):
            st.session_state["clase_seleccionada"] = None
            st.session_state["materia_seleccionada"] = None
            st.rerun()

    # Panel plegable para editar o borrar la clase activa
    with st.expander("🛠️ Administrar esta clase (Renombrar o Borrar)"):
        col_edit_txt, col_edit_btn, col_del_clase = st.columns([3, 1, 1])
        with col_edit_txt:
            nuevo_nombre_clase = st.text_input("Renombrar tema:", value=cla.replace('_', ' '), label_visibility="collapsed")
        with col_edit_btn:
            if st.button("✏️ Guardar Nombre", use_container_width=True):
                nombre_sanitizado = normalizar_nombre(nuevo_nombre_clase.strip())
                if nombre_sanitizado and nombre_sanitizado != cla:
                    ruta_nueva_clase = os.path.join(CARPETA_BASE, mat, nombre_sanitizado)
                    if es_ruta_segura(ruta_nueva_clase):
                        if os.path.exists(ruta_nueva_clase):
                            st.error("Ya existe una clase con ese nombre en esta materia.")
                        else:
                            os.rename(carpeta_clase, ruta_nueva_clase)
                            st.session_state["clase_seleccionada"] = nombre_sanitizado
                            st.rerun()
                    else:
                        st.error("Nombre de ruta no permitido.")
        with col_del_clase:
            if st.button("🗑️ Borrar Clase", type="secondary", use_container_width=True):
                st.session_state["confirmar_borrado_clase"] = True

        if st.session_state.get("confirmar_borrado_clase"):
            st.warning(f"¿Estás seguro de que deseas eliminar permanentemente la clase '{cla.replace('_', ' ')}'?")
            col_conf_si, col_conf_no = st.columns([1, 1])
            if col_conf_si.button("Sí, eliminar definitivamente", type="primary", use_container_width=True):
                if es_ruta_segura(carpeta_clase):
                    shutil.rmtree(carpeta_clase)
                    st.session_state["clase_seleccionada"] = None
                    st.session_state["confirmar_borrado_clase"] = False
                    st.rerun()
            if col_conf_no.button("Cancelar", use_container_width=True):
                st.session_state["confirmar_borrado_clase"] = False
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
    st.title("🎓 Asistente de Estudio DAW")
    st.caption("Organizador local con MLX-Whisper y Qwen 2.5 en Apple Silicon")

    metodo_origen = st.radio(
        "Origen del material:",
        ["📁 Usar vídeo ya guardado en la carpeta 'clases/'", "⬆️ Subir archivo nuevo"],
        horizontal=True
    )

    ruta_archivo_final = None
    directorio_final = None
    materia_actual = ""
    clase_actual = ""

    if metodo_origen == "📁 Usar vídeo ya guardado en la carpeta 'clases/'":
        encontrados = []
        for r, _, files in os.walk(CARPETA_BASE, followlinks=False):
            for arch in files:
                if arch.lower().endswith((".mp4", ".mkv", ".mov", ".mp3", ".m4a", ".wav")):
                    ruta_candidata = os.path.realpath(os.path.join(r, arch))
                    if es_ruta_segura(ruta_candidata):
                        encontrados.append(os.path.join(r, arch))

        if encontrados:
            opciones = [os.path.relpath(p, CARPETA_BASE) for p in encontrados]
            sel = st.selectbox("Archivo a procesar:", opciones)
            ruta_seleccionada_real = os.path.realpath(os.path.join(CARPETA_BASE, sel))
            if not es_ruta_segura(ruta_seleccionada_real):
                st.error("Ruta inválida detectada. Posible symlink fuera del directorio de clases.")
                st.stop()
            ruta_archivo_final = ruta_seleccionada_real
            directorio_final = os.path.dirname(ruta_archivo_final)

            partes_rel = os.path.relpath(directorio_final, CARPETA_BASE).split(os.sep)
            if len(partes_rel) >= 2:
                materia_actual = partes_rel[0]
                clase_actual = partes_rel[1]
        else:
            st.warning("No hay archivos en 'clases/'.")
    else:
        col1, col2 = st.columns(2)
        with col1:
            asignaturas_comunes = ["Programacion", "Bases_de_Datos", "Lenguajes_de_Marcas", "Sistemas_Informaticos", "Entornos_de_Desarrollo", "Otra"]
            seleccion_mat = st.selectbox("Asignatura:", asignaturas_comunes)
            materia_nombre = st.text_input("Nombre de la materia:").strip() if seleccion_mat == "Otra" else seleccion_mat
        with col2:
            clase_nombre = st.text_input("Tema de clase:", placeholder="Tema_01_Variables").strip()

        archivo_cargado = st.file_uploader("Arrastra o selecciona el archivo:", type=["mp4", "mkv", "mp3", "m4a", "wav"])
        if archivo_cargado and materia_nombre and clase_nombre:
            mat_segura = normalizar_nombre(materia_nombre)
            cla_segura = normalizar_nombre(clase_nombre)
            nombre_fichero_seguro = os.path.basename(normalizar_nombre(archivo_cargado.name))

            directorio_tentativo = os.path.abspath(os.path.join(CARPETA_BASE, mat_segura, cla_segura))
            if not es_ruta_segura(directorio_tentativo):
                st.error("Ruta de destino inválida: intento de escape fuera del directorio de clases.")
            else:
                directorio_final = directorio_tentativo
                os.makedirs(directorio_final, exist_ok=True)
                ruta_archivo_final = os.path.join(directorio_final, nombre_fichero_seguro)
                with open(ruta_archivo_final, "wb") as f:
                    f.write(archivo_cargado.getbuffer())
                materia_actual = mat_segura
                clase_actual = cla_segura

    if st.button("🚀 Iniciar Procesamiento", type="primary"):
        if not ruta_archivo_final or not os.path.exists(ruta_archivo_final):
            st.error("Selecciona un archivo válido.")
        elif not directorio_final:
            st.error("Falta indicar la carpeta de destino.")
        else:
            os.makedirs(directorio_final, exist_ok=True)
            ruta_transcripcion = os.path.join(directorio_final, "transcripcion.txt")
            ruta_apuntes = os.path.join(directorio_final, "apuntes.md")

            barra_progreso = st.progress(0, text="Preparando el entorno...")
            estado_actual = st.status("Iniciando pipeline de estudio...", expanded=True)
            st.write("#### 📟 Consola en tiempo real")
            caja_consola = st.empty()

            try:
                transcripcion_previa = os.path.exists(ruta_transcripcion) and os.path.getsize(ruta_transcripcion) > 0

                if transcripcion_previa:
                    barra_progreso.progress(50, text="Paso 1/2 omitido: Transcripción previa detectada.")
                    estado_actual.write("ℹ️ Se reutiliza 'transcripcion.txt' existente en la carpeta.")
                    caja_consola.code("-> Archivo de transcripción encontrado. Omitiendo fase de audio.", language="bash")
                else:
                    barra_progreso.progress(10, text="Paso 1/2: Extrayendo audio y transcribiendo...")
                    cmd_transcribir = [sys.executable, "-u", "transcribir.py", ruta_archivo_final, ruta_transcripcion]
                    ejecutar_paso_con_progreso(
                        cmd_transcribir,
                        caja_consola,
                        estado_actual,
                        "Paso 1/2: Transcribiendo con Apple Silicon (MLX)..."
                    )
                    barra_progreso.progress(50, text="Transcripción completada.")

                barra_progreso.progress(60, text="Paso 2/2: Sintetizando apuntes y auditando con Qwen 2.5...")
                cmd_apuntes = [sys.executable, "-u", "generar_apuntes.py", ruta_transcripcion, ruta_apuntes]
                ejecutar_paso_con_progreso(
                    cmd_apuntes,
                    caja_consola,
                    estado_actual,
                    "Paso 2/2: Generando apuntes técnicos y auditoría..."
                )

                barra_progreso.progress(100, text="¡Proceso finalizado con éxito!")
                estado_actual.update(label="🎉 ¡Clase procesada y archivada!", state="complete", expanded=False)
                st.success(f"Archivos guardados en: `{directorio_final}`")

                if os.path.exists(ruta_apuntes):
                    st.divider()
                    col_prev_tit, col_prev_notion = st.columns([3, 1])
                    with col_prev_tit:
                        st.subheader("📝 Vista Previa de Apuntes")
                    with col_prev_notion:
                        if st.button("🚀 Enviar a Notion ahora", key="btn_notion_directo", use_container_width=True):
                            with st.spinner("Sincronizando con Notion..."):
                                try:
                                    with open(ruta_apuntes, "r", encoding="utf-8") as f:
                                        texto_md = f.read()
                                    mat_exp = materia_actual or "General"
                                    cla_exp = clase_actual or os.path.basename(directorio_final)
                                    url_notion = exportar_a_notion(cla_exp, mat_exp, texto_md)
                                    st.success("¡Exportado a Notion con éxito!")
                                    st.markdown(f"[🔗 Abrir página en Notion]({url_notion})")
                                except Exception as err:
                                    st.error(f"Error al exportar: {err}")

                    with open(ruta_apuntes, "r", encoding="utf-8") as f:
                        st.markdown(f.read())

            except Exception as e:
                estado_actual.update(label="❌ Error durante la ejecución", state="error")
                st.error(f"Fallo detectado: {e}")