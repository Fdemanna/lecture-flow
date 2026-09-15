import os
import shutil
import subprocess
import sys
import streamlit as st
from procesar_clase import normalizar_nombre

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
    
    lineas_consola = []
    while True:
        linea = proceso.stdout.readline()
        if not linea and proceso.poll() is not None:
            break
        if linea:
            lineas_consola.append(linea)
            caja_texto.code("".join(lineas_consola[-8:]), language="bash")
            
    codigo_salida = proceso.wait()
    if codigo_salida != 0:
        raise subprocess.CalledProcessError(codigo_salida, comando)

# ---------------------------------------------------------------------------
# MENÚ LATERAL
# ---------------------------------------------------------------------------
st.sidebar.title("📚 Asignaturas DAW")

if st.sidebar.button("➕ Subir / Procesar Nueva Clase", use_container_width=True, type="primary"):
    st.session_state["clase_seleccionada"] = None
    st.session_state["materia_seleccionada"] = None
    st.rerun()

st.sidebar.divider()

materias_existentes = sorted([d for d in os.listdir(CARPETA_BASE) if os.path.isdir(os.path.join(CARPETA_BASE, d))])
if materias_existentes:
    for m in materias_existentes:
        with st.sidebar.expander(f"📁 {m.replace('_', ' ')}", expanded=True):
            ruta_m = os.path.join(CARPETA_BASE, m)
            clases_m = sorted([c for c in os.listdir(ruta_m) if os.path.isdir(os.path.join(ruta_m, c))])
            if clases_m:
                for c in clases_m:
                    if st.button(f"📄 {c.replace('_', ' ')}", key=f"btn_{m}_{c}", use_container_width=True):
                        st.session_state["materia_seleccionada"] = m
                        st.session_state["clase_seleccionada"] = c
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

    col_tit, col_btn = st.columns([4, 1])
    with col_tit:
        st.title(f"📖 {cla.replace('_', ' ')}")
        st.caption(f"Materia: **{mat.replace('_', ' ')}**")
    with col_btn:
        if st.button("⬅️ Volver al Inicio"):
            st.session_state["clase_seleccionada"] = None
            st.session_state["materia_seleccionada"] = None
            st.rerun()

    apuntes_path = os.path.join(carpeta_clase, "apuntes.md")
    auditoria_path = os.path.join(carpeta_clase, "apuntes_auditoria.md")
    transcripcion_path = os.path.join(carpeta_clase, "transcripcion.txt")

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

    if metodo_origen == "📁 Usar vídeo ya guardado en la carpeta 'clases/'":
        encontrados = []
        for r, _, files in os.walk(CARPETA_BASE):
            for arch in files:
                if arch.lower().endswith((".mp4", ".mkv", ".mov", ".mp3", ".m4a", ".wav")):
                    encontrados.append(os.path.join(r, arch))

        if encontrados:
            opciones = [os.path.relpath(p, CARPETA_BASE) for p in encontrados]
            sel = st.selectbox("Archivo a procesar:", opciones)
            ruta_archivo_final = os.path.join(CARPETA_BASE, sel)
            directorio_final = os.path.dirname(ruta_archivo_final)
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
            # Sanitización contra Path Traversal (C-1 y C-2)
            mat_segura = normalizar_nombre(materia_nombre)
            cla_segura = normalizar_nombre(clase_nombre)
            nombre_fichero_seguro = os.path.basename(normalizar_nombre(archivo_cargado.name))

            directorio_tentativo = os.path.abspath(os.path.join(CARPETA_BASE, mat_segura, cla_segura))
            carpeta_base_real = os.path.realpath(CARPETA_BASE)

            # Verificación de contención de ruta
            if not os.path.realpath(directorio_tentativo).startswith(carpeta_base_real + os.sep):
                st.error("Ruta de destino inválida: intento de escape fuera del directorio de clases.")
            else:
                directorio_final = directorio_tentativo
                os.makedirs(directorio_final, exist_ok=True)
                ruta_archivo_final = os.path.join(directorio_final, nombre_fichero_seguro)
                with open(ruta_archivo_final, "wb") as f:
                    f.write(archivo_cargado.getbuffer())

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
                # Verificación de transcripción previa
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

                # Paso 2: Generación de apuntes y auditoría
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
                    st.subheader("📝 Vista Previa de Apuntes")
                    with open(ruta_apuntes, "r", encoding="utf-8") as f:
                        st.markdown(f.read())

            except Exception as e:
                estado_actual.update(label="❌ Error durante la ejecución", state="error")
                st.error(f"Fallo detectado: {e}")