import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
import streamlit as st
from src.procesar_clase import normalizar_nombre
from src.notion_exporter import exportar_a_notion
from src.auditor import auditar_apuntes

ROOT_DIR = Path(__file__).resolve().parent
CARPETA_BASE = str(ROOT_DIR / "clases")
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
  .badge-status-chip {
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

MAPEO_ASIGNATURAS = {
    "Bases_de_Datos": "Bases de Datos",
    "Programacion": "Programación",
    "Lenguajes_de_Marcas": "Lenguajes de Marcas",
    "Entornos_de_Desarrollo": "Entornos de Desarrollo",
    "Sistemas_Informaticos": "Sistemas Informáticos",
    "FOL": "Formación y Orientación Laboral (FOL)",
    "Otra": "Otra (personalizada)"
}

TIMEOUT_SEGUNDOS = 14400  # 4 horas para clases largas (>1.5h)


def es_ruta_segura(ruta_destino: str) -> bool:
    base_real = os.path.realpath(CARPETA_BASE)
    candidata_real = os.path.realpath(ruta_destino)
    return candidata_real.startswith(base_real + os.sep)


def _ejecutar_subproceso_con_spinner(
    cmd: list,
    spinner_msg: str,
    exito_msg: str,
    error_prefix: str = "Error en el subproceso",
) -> bool:
    """Ejecuta un comando en subproceso mostrando un st.spinner.

    Devuelve True si el proceso terminó con código 0, False en caso contrario.
    """
    with st.spinner(spinner_msg):
        try:
            resultado = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=TIMEOUT_SEGUNDOS,
            )
            if resultado.returncode != 0:
                st.error(f"{error_prefix}:\n```\n{resultado.stderr[-2000:]}\n```")
                return False
            st.success(exito_msg)
            return True
        except subprocess.TimeoutExpired:
            st.error("Tiempo de espera agotado. El proceso tardó demasiado.")
            return False
        except Exception as exc:
            st.error(f"{error_prefix}: {exc}")
            return False


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
st.sidebar.markdown("###  Asignaturas 📚")

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
        label = MAPEO_ASIGNATURAS.get(m, m.replace('_', ' '))
        with st.sidebar.expander(f"📁 {label}", expanded=True):
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
else:
    st.sidebar.info("Aquí aparecerán tus asignaturas y clases procesadas.")

st.sidebar.divider()
if materias_existentes:
    with st.sidebar.expander("⚙️ Administrar Asignaturas"):
        tab_renombrar, tab_eliminar = st.tabs(["✏️ Renombrar", "🗑️ Eliminar"])
        
        with tab_renombrar:
            mat_renombrar = st.selectbox("Materia a renombrar:", materias_existentes, key="sb_renombrar", format_func=lambda x: MAPEO_ASIGNATURAS.get(x, x.replace('_', ' ')))
            nuevo_nombre = st.text_input("Nuevo nombre para la asignatura:", value=mat_renombrar.replace('_', ' '), key="txt_nuevo_nombre")
            if st.button("Guardar nuevo nombre", use_container_width=True):
                sanit = normalizar_nombre(nuevo_nombre.strip())
                if sanit and sanit != mat_renombrar:
                    try:
                        os.rename(os.path.join(CARPETA_BASE, mat_renombrar), os.path.join(CARPETA_BASE, sanit))
                        st.sidebar.success("Asignatura renombrada correctamente.")
                        time.sleep(0.5)
                        st.rerun()
                    except OSError as e:
                        st.sidebar.error(f"Error al renombrar: {e}")
                        
        with tab_eliminar:
            mat_eliminar = st.selectbox("Asignatura a borrar:", materias_existentes, key="sb_eliminar", format_func=lambda x: MAPEO_ASIGNATURAS.get(x, x.replace('_', ' ')))
            
            ruta_eliminar = os.path.join(CARPETA_BASE, mat_eliminar)
            try:
                elementos = len(os.listdir(ruta_eliminar))
                st.warning(f"⚠️ Esta carpeta contiene {elementos} elemento(s).")
            except OSError:
                pass
                
            confirmacion = st.checkbox("Confirmo que deseo eliminar esta asignatura y todos sus archivos")
            
            if st.button("Eliminar permanentemente", type="primary", disabled=not confirmacion, use_container_width=True):
                try:
                    shutil.rmtree(ruta_eliminar)
                    st.sidebar.success("Asignatura eliminada.")
                    time.sleep(0.5)
                    st.rerun()
                except OSError as e:
                    st.sidebar.error(f"Error al eliminar: {e}")


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
      </div>
    </div>
  </div>
  <div class="badge-status-chip">
    <span class="dot-ping"></span> Multiplataforma Local
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

    # ------------------------------------------------------------------
    # Botones de reprocesamiento granular
    # ------------------------------------------------------------------
    tiene_transcripcion = (
        os.path.exists(transcripcion_path)
        and os.path.getsize(transcripcion_path) > 0
    )

    # Buscar el primer archivo multimedia guardado en la carpeta de la clase
    _EXTS_MEDIA = (".mp4", ".mkv", ".mov", ".avi", ".mp3", ".m4a", ".wav")
    _archivo_media = next(
        (
            os.path.join(carpeta_clase, f)
            for f in os.listdir(carpeta_clase)
            if f.lower().endswith(_EXTS_MEDIA)
        ),
        None,
    )

    with st.expander("🔧 Reprocesar esta clase", expanded=False):
        col_re1, col_re2 = st.columns(2)

        with col_re1:
            _btn_solo_apuntes = st.button(
                "🔄 Re-generar Apuntes (Solo LLM)",
                key="btn_solo_apuntes",
                use_container_width=True,
                disabled=not tiene_transcripcion,
                help="Regenera los apuntes con Ollama usando la transcripción existente. Whisper se omite.",
            )
            if not tiene_transcripcion:
                st.caption("⚠️ Sin transcripción disponible — ejecuta primero el pipeline completo.")

        with col_re2:
            _btn_forzar = st.button(
                "⚠️ Re-transcribir desde audio",
                key="btn_forzar_transcripcion",
                use_container_width=True,
                disabled=_archivo_media is None,
                help="Vuelve a ejecutar Whisper desde el audio guardado y regenera los apuntes completos.",
            )
            if _archivo_media is None:
                st.caption("⚠️ No se encontró archivo multimedia en la carpeta de la clase.")

        # ---- Acción: Solo LLM ----
        if _btn_solo_apuntes:
            _cmd_solo = [
                sys.executable, "-u",
                str(ROOT_DIR / "src" / "procesar_clase.py"),
                mat, cla, "",
                "--solo-apuntes",
            ]
            _ok = _ejecutar_subproceso_con_spinner(
                _cmd_solo,
                spinner_msg="Re-sintetizando apuntes con Ollama y auditando... (Whisper omitido)",
                exito_msg="✅ Apuntes regenerados correctamente. Recarga la pestaña para ver los cambios.",
                error_prefix="Error en la re-generación de apuntes",
            )
            if _ok:
                st.rerun()

        # ---- Acción: Forzar Transcripción ----
        if _btn_forzar:
            if "confirmar_retranscribir" not in st.session_state:
                st.session_state["confirmar_retranscribir"] = False

            if not st.session_state["confirmar_retranscribir"]:
                st.warning(
                    "⚠️ **Esto sobrescribirá la transcripción y los apuntes existentes.** "
                    "Pulsa de nuevo el botón para confirmar."
                )
                st.session_state["confirmar_retranscribir"] = True
            else:
                st.session_state["confirmar_retranscribir"] = False
                _cmd_forzar = [
                    sys.executable, "-u",
                    str(ROOT_DIR / "src" / "procesar_clase.py"),
                    mat, cla, _archivo_media or "",
                    "--forzar-transcripcion",
                ]
                _ok2 = _ejecutar_subproceso_con_spinner(
                    _cmd_forzar,
                    spinner_msg="Re-transcribiendo con Whisper y regenerando apuntes... (esto puede tardar)",
                    exito_msg="✅ Re-transcripción y apuntes completados.",
                    error_prefix="Error en la re-transcripción",
                )
                if _ok2:
                    st.rerun()

    st.divider()

    tab1, tab2, tab3 = st.tabs(["📝 Apuntes y Ejemplos", "🔍 Control de Alucinaciones", "📜 Transcripción Cruda"])

    with tab1:
        if os.path.exists(apuntes_path):
            with open(apuntes_path, "r", encoding="utf-8") as f:
                st.markdown(f.read())
        else:
            st.warning("Apuntes pendientes de generación.")
    with tab2:
        if os.path.exists(apuntes_path):
            with open(apuntes_path, "r", encoding="utf-8") as _f:
                _texto_md = _f.read()

            _res = auditar_apuntes(_texto_md)

            # --- Badge de estado global ---
            if _res.es_valido:
                st.html("""
                <div style="display:inline-flex;align-items:center;gap:8px;
                            background:#0d2e1f;border:1px solid #4edea3;
                            border-radius:8px;padding:10px 18px;margin-bottom:12px;">
                  <span style="font-size:1.3rem;">✅</span>
                  <span style="color:#4edea3;font-weight:700;">Auditoría superada — sin errores</span>
                </div>""")
            else:
                st.html("""
                <div style="display:inline-flex;align-items:center;gap:8px;
                            background:#2e0d0d;border:1px solid #e05c5c;
                            border-radius:8px;padding:10px 18px;margin-bottom:12px;">
                  <span style="font-size:1.3rem;">❌</span>
                  <span style="color:#e05c5c;font-weight:700;">Auditoría fallida — revisa los errores</span>
                </div>""")

            # --- Métricas rápidas ---
            _mc1, _mc2, _mc3 = st.columns(3)
            _mc1.metric("Timestamps", _res.timestamps_detectados)
            _mc2.metric("Cobertura de términos", f"{_res.cobertura_terminos:.0%}")
            _mc3.metric("Errores críticos", len(_res.errores))

            # --- Errores críticos ---
            if _res.errores:
                st.markdown("##### 🔴 Errores críticos")
                for _err in _res.errores:
                    st.error(_err)

            # --- Advertencias ---
            if _res.advertencias:
                st.markdown("##### 🟡 Advertencias")
                for _adv in _res.advertencias:
                    st.warning(_adv)

            if not _res.errores and not _res.advertencias:
                st.success("Los apuntes superaron todas las reglas de validación sin advertencias.")
        else:
            st.info("Genera los apuntes primero para ejecutar la auditoría determinista.")
    with tab3:
        if os.path.exists(transcripcion_path):
            with open(transcripcion_path, "r", encoding="utf-8") as f:
                st.text_area("Transcripción:", f.read(), height=450)

else:
    # VISTA CONSOLA DE PROCESAMIENTO
    st.markdown("#### ⚡ Procesar una grabación")
    st.caption("Convierte grabaciones de clase en apuntes estructurados con marcas de tiempo.")

    metodo_origen = st.radio(
        "Origen del material:",
        ["Subir nuevo archivo", "Usar un archivo ya guardado"],
        horizontal=True
    )

    ruta_archivo_final = None
    directorio_final = None
    materia_actual = ""
    clase_actual = ""

    col_form_1, col_form_2 = st.columns(2)
    with col_form_1:
        # 1. Asignaturas oficiales
        asignaturas_base = [k for k in MAPEO_ASIGNATURAS.keys() if k != "Otra"]
        
        # 2. Carpetas existentes (materias_existentes ya se calcula arriba, pero lo re-obtenemos por si acaso o usamos la variable)
        materias_carpetas = sorted([
            d for d in os.listdir(CARPETA_BASE)
            if os.path.isdir(os.path.join(CARPETA_BASE, d))
        ])
        
        # Unir ambas listas sin duplicados manteniendo orden
        asignaturas_disponibles = []
        for m in asignaturas_base + materias_carpetas:
            if m not in asignaturas_disponibles:
                asignaturas_disponibles.append(m)
                
        # 3. Opción para nueva asignatura
        OPCION_NUEVA = "➕ Añadir nueva asignatura..."
        asignaturas_disponibles.append(OPCION_NUEVA)
        
        def formato_asignatura(x):
            if x == OPCION_NUEVA:
                return x
            return MAPEO_ASIGNATURAS.get(x, x.replace("_", " "))
            
        seleccion_mat = st.selectbox(
            "Asignatura DAW:", 
            asignaturas_disponibles, 
            format_func=formato_asignatura
        )
        
        if seleccion_mat == OPCION_NUEVA:
            materia_nombre = st.text_input("Nombre de la nueva asignatura:", placeholder="Ej: Despliegue de Aplicaciones Web").strip()
        else:
            materia_nombre = seleccion_mat

    with col_form_2:
        clase_nombre = st.text_input("Tema de la clase:", placeholder="Ej: Procedimientos almacenados y funciones").strip()

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
            sel = st.selectbox("Archivo en carpeta:", opciones, format_func=lambda x: x.replace(os.sep, " / ").replace("_", " "))
            ruta_archivo_final = os.path.realpath(os.path.join(CARPETA_BASE, sel))
            directorio_final = os.path.dirname(ruta_archivo_final)
            partes = os.path.relpath(directorio_final, CARPETA_BASE).split(os.sep)
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
        <li style="margin-bottom:8px;"><strong>Transcripción:</strong> Whisper en local (CUDA / Metal) detectando marcas [HH:MM:SS].</li>
        <li style="margin-bottom:8px;"><strong>Síntesis:</strong> Ollama estructura conceptos, código y autoevaluación.</li>
        <li><strong>Auditoría Determinista:</strong> Validación matemática de sintaxis, código y orden cronológico.</li>
      </ol>
    </div>
    """)

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
                    barra_progreso.progress(15, text="Paso 1/2: Extrayendo PCM WAV y transcribiendo audio...")
                    cmd_transcribir = [sys.executable, "-u", str(ROOT_DIR / "src" / "transcribir.py"), ruta_archivo_final, ruta_transcripcion]
                    ejecutar_paso_con_progreso(cmd_transcribir, caja_consola, estado_actual, "Paso 1/2: Whisper transcribiendo...")
                    barra_progreso.progress(50, text="Transcripción completada.")

                # 2. Generación con Qwen 2.5
                barra_progreso.progress(65, text="Paso 2/2: Sintetizando apuntes y auditando con Qwen 2.5...")
                cmd_apuntes = [sys.executable, "-u", str(ROOT_DIR / "src" / "generar_apuntes.py"), ruta_transcripcion, ruta_apuntes]
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