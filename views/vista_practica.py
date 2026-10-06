"""Vista de Evaluación Activa y Práctica Diaria (Spaced Repetition Flashcards & Quiz)."""
from __future__ import annotations

from pathlib import Path
import re
from typing import Optional
import streamlit as st

from src.study_engine import (
    obtener_progreso,
    actualizar_racha,
    registrar_respuesta,
    obtener_preguntas_disponibles,
)

LETRAS_OPCIONES = ["A", "B", "C", "D"]


def limpiar_texto_opcion(opcion: str) -> str:
    """Elimina prefijos como 'A)', 'B.', 'C -', etc. si ya vienen incluidos en la opción."""
    return re.sub(r"^[A-Da-d][\)\.\-]\s*", "", str(opcion).strip())


def renderizar_vista_practica(root_dir: Path) -> None:
    """Renderiza la interfaz de evaluación activa y práctica de estudio."""
    # 1. Inicialización de estado en session_state
    if "quiz_preguntas" not in st.session_state:
        st.session_state["quiz_preguntas"] = None
    if "quiz_indice" not in st.session_state:
        st.session_state["quiz_indice"] = 0
    if "quiz_respondida" not in st.session_state:
        st.session_state["quiz_respondida"] = False
    if "quiz_opcion_elegida" not in st.session_state:
        st.session_state["quiz_opcion_elegida"] = None
    if "quiz_aciertos_sesion" not in st.session_state:
        st.session_state["quiz_aciertos_sesion"] = 0
    if "quiz_terminado" not in st.session_state:
        st.session_state["quiz_terminado"] = False

    progreso = obtener_progreso()
    racha_actual = progreso.get("racha_actual", 0)
    xp_total = progreso.get("xp_total", 0)

    # 2. Cargar preguntas si no están instanciadas
    if st.session_state["quiz_preguntas"] is None:
        preguntas_cargadas = obtener_preguntas_disponibles(root_dir, limite=5)
        st.session_state["quiz_preguntas"] = preguntas_cargadas
        st.session_state["quiz_indice"] = 0
        st.session_state["quiz_respondida"] = False
        st.session_state["quiz_opcion_elegida"] = None
        st.session_state["quiz_aciertos_sesion"] = 0
        st.session_state["quiz_terminado"] = False

    preguntas = st.session_state["quiz_preguntas"]

    # 3. Caso: No hay preguntas disponibles
    if not preguntas:
        st.markdown(
            """
            <div style="background: #171b26; border: 1px solid rgba(255,255,255,0.08); border-radius: 16px; padding: 32px; text-align: center; margin-top: 20px;">
                <div style="font-size: 3rem; margin-bottom: 12px;">📚</div>
                <h3 style="color: #f8fafc; font-family: 'Geist', sans-serif; margin-bottom: 8px;">No hay preguntas de evaluación disponibles</h3>
                <p style="color: #94a3b8; font-size: 0.95rem; max-width: 520px; margin: 0 auto 24px auto;">
                    Aún no se ha generado ningún banco de preguntas. Procesa una clase desde el menú lateral para que el asistente extraiga automáticamente los cuestionarios tipo test.
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        col_c1, col_c2, col_c3 = st.columns([1, 2, 1])
        with col_c2:
            if st.button("➕ Ir a Procesar Nueva Clase", use_container_width=True, type="primary"):
                st.session_state["clase_seleccionada"] = None
                st.session_state["materia_seleccionada"] = None
                st.session_state["vista_actual"] = "individual"
                st.session_state["vista_principal"] = "individual"
                st.rerun()
        return

    # 4. Caso: Sesión terminada
    if st.session_state["quiz_terminado"]:
        total_p = len(preguntas)
        aciertos = st.session_state["quiz_aciertos_sesion"]
        porcentaje = round((aciertos / total_p) * 100) if total_p > 0 else 0
        xp_ganada = aciertos * 10

        st.markdown(
            f"""
            <div style="background: #171b26; border: 1px solid rgba(255,255,255,0.08); border-radius: 20px; padding: 36px; text-align: center; margin-top: 10px;">
                <div style="font-size: 3.5rem; margin-bottom: 12px;">🏆</div>
                <h2 style="color: #f8fafc; font-family: 'Geist', sans-serif; font-size: 1.6rem; margin-bottom: 6px;">¡Sesión de Práctica Completada!</h2>
                <p style="color: #94a3b8; font-size: 0.92rem; margin-bottom: 24px;">Has repasado tus conocimientos con repetición espaciada SM-2.</p>
                
                <div style="display: flex; justify-content: center; gap: 16px; flex-wrap: wrap; margin-bottom: 28px;">
                    <div style="background: #1c1f2a; border: 1px solid rgba(128,131,255,0.25); border-radius: 12px; padding: 14px 20px; min-width: 140px;">
                        <div style="font-size: 0.78rem; color: #94a3b8; font-weight: 500;">Puntuación</div>
                        <div style="font-size: 1.4rem; font-weight: 700; color: #c0c1ff; margin-top: 2px;">{aciertos} / {total_p} ({porcentaje}%)</div>
                    </div>
                    <div style="background: #1c1f2a; border: 1px solid rgba(78,222,163,0.25); border-radius: 12px; padding: 14px 20px; min-width: 140px;">
                        <div style="font-size: 0.78rem; color: #94a3b8; font-weight: 500;">Experiencia Ganada</div>
                        <div style="font-size: 1.4rem; font-weight: 700; color: #4edea3; margin-top: 2px;">+{xp_ganada} XP</div>
                    </div>
                    <div style="background: #1c1f2a; border: 1px solid rgba(251,146,60,0.25); border-radius: 12px; padding: 14px 20px; min-width: 140px;">
                        <div style="font-size: 0.78rem; color: #94a3b8; font-weight: 500;">Racha Diaria</div>
                        <div style="font-size: 1.4rem; font-weight: 700; color: #fb923c; margin-top: 2px;">🔥 {"1 día" if racha_actual == 1 else f"{racha_actual} días"}</div>
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        col_b1, col_b2 = st.columns(2)
        with col_b1:
            if st.button("🔄 Iniciar Otra Sesión", use_container_width=True, type="primary"):
                st.session_state["quiz_preguntas"] = None
                st.session_state["quiz_indice"] = 0
                st.session_state["quiz_respondida"] = False
                st.session_state["quiz_opcion_elegida"] = None
                st.session_state["quiz_aciertos_sesion"] = 0
                st.session_state["quiz_terminado"] = False
                st.rerun()
        with col_b2:
            if st.button("🏠 Volver al Inicio", use_container_width=True):
                st.session_state["clase_seleccionada"] = None
                st.session_state["materia_seleccionada"] = None
                st.session_state["vista_actual"] = "individual"
                st.session_state["vista_principal"] = "individual"
                st.rerun()
        return

    # 5. Pregunta activa
    idx = st.session_state["quiz_indice"]
    total = len(preguntas)
    p_actual = preguntas[idx]

    materia_nombre = p_actual.get("materia", "General").replace("_", " ")
    clase_nombre = p_actual.get("clase", "Tema").replace("_", " ")
    enunciado = p_actual.get("pregunta", "")
    codigo = p_actual.get("codigo", "")
    opciones = p_actual.get("opciones", [])
    correcta_idx = int(p_actual.get("correcta", 0))
    explicacion = p_actual.get("explicacion", "")

    # Barra superior de estado (Obsidian Flow)
    texto_dias = "1 día seguido" if racha_actual == 1 else f"{racha_actual} días seguidos"
    st.markdown(
        f"""
        <div style="display: flex; align-items: center; justify-content: space-between; background: #171b26; border: 1px solid rgba(255,255,255,0.06); border-radius: 12px; padding: 12px 20px; margin-bottom: 16px;">
            <div style="display: flex; align-items: center; gap: 14px;">
                <span style="background: rgba(251,146,60,0.12); color: #fb923c; border: 1px solid rgba(251,146,60,0.25); padding: 4px 10px; border-radius: 9999px; font-size: 0.8rem; font-weight: 600;">
                    🔥 {texto_dias}
                </span>
                <span style="background: rgba(78,222,163,0.12); color: #4edea3; border: 1px solid rgba(78,222,163,0.25); padding: 4px 10px; border-radius: 9999px; font-size: 0.8rem; font-weight: 600;">
                    ⚡ {xp_total} XP
                </span>
            </div>
            <div style="color: #94a3b8; font-size: 0.85rem; font-weight: 600; font-family: 'Geist', sans-serif;">
                Pregunta <span style="color: #f8fafc;">{idx + 1}</span> de <span style="color: #f8fafc;">{total}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Tarjeta de la pregunta
    st.markdown(
        f"""
        <div style="background: #171b26; border: 1px solid rgba(255,255,255,0.06); border-radius: 16px; padding: 24px; margin-bottom: 16px;">
            <div style="font-size: 0.78rem; font-weight: 500; color: #8083ff; margin-bottom: 8px; font-family: 'Geist', sans-serif; display: flex; align-items: center; gap: 6px;">
                📁 <span>{materia_nombre}</span> <span style="color: #475569;">/</span> <span>{clase_nombre}</span>
            </div>
            <h3 style="color: #f8fafc; font-family: 'Geist', sans-serif; font-size: 1.15rem; font-weight: 600; line-height: 1.45; margin: 0 0 12px 0;">
                {enunciado}
            </h3>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Bloque de código si aplica
    if codigo and codigo.strip():
        st.code(codigo.strip(), language="python")

    respondida = st.session_state["quiz_respondida"]
    elegida = st.session_state["quiz_opcion_elegida"]

    # Modo A: Esperando respuesta del usuario (Botones interactivos)
    if not respondida:
        st.markdown("<p style='font-size: 0.85rem; color: #94a3b8; margin-bottom: 10px; font-weight: 500;'>Selecciona tu respuesta:</p>", unsafe_allow_html=True)
        for i, opt in enumerate(opciones):
            letra = LETRAS_OPCIONES[i] if i < len(LETRAS_OPCIONES) else f"Opción {i+1}"
            opt_limpia = limpiar_texto_opcion(opt)
            texto_btn = f"{letra}) {opt_limpia}"
            if st.button(texto_btn, key=f"btn_opt_{idx}_{i}", use_container_width=True):
                st.session_state["quiz_respondida"] = True
                st.session_state["quiz_opcion_elegida"] = i
                es_acierto = (i == correcta_idx)
                if es_acierto:
                    st.session_state["quiz_aciertos_sesion"] += 1
                    registrar_respuesta(p_actual["id"], acierto=True, xp_ganado=10)
                else:
                    registrar_respuesta(p_actual["id"], acierto=False, xp_ganado=0)
                st.rerun()

    # Modo B: Pregunta ya respondida (Feedback visual + Explicación)
    else:
        for i, opt in enumerate(opciones):
            letra = LETRAS_OPCIONES[i] if i < len(LETRAS_OPCIONES) else f"{i+1}"
            opt_limpia = limpiar_texto_opcion(opt)
            es_correcta = (i == correcta_idx)
            fue_elegida = (i == elegida)

            if es_correcta:
                st.markdown(
                    f"""
                    <div style="background: rgba(78,222,163,0.12); border: 1.5px solid #4edea3; border-radius: 12px; padding: 12px 18px; margin-bottom: 8px; color: #4edea3; font-weight: 600; display: flex; align-items: center; justify-content: space-between;">
                        <span><strong style="background: #003824; color: #4edea3; padding: 2px 8px; border-radius: 6px; margin-right: 8px;">{letra}</strong> {opt_limpia}</span>
                        <span>✅ Correcta</span>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            elif fue_elegida and not es_correcta:
                st.markdown(
                    f"""
                    <div style="background: rgba(255,180,171,0.1); border: 1.5px solid #ffb4ab; border-radius: 12px; padding: 12px 18px; margin-bottom: 8px; color: #ffb4ab; font-weight: 600; display: flex; align-items: center; justify-content: space-between;">
                        <span><strong style="background: #690005; color: #ffb4ab; padding: 2px 8px; border-radius: 6px; margin-right: 8px;">{letra}</strong> {opt_limpia}</span>
                        <span>❌ Tu respuesta</span>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    f"""
                    <div style="background: #1c1f2a; border: 1px solid rgba(255,255,255,0.05); border-radius: 12px; padding: 12px 18px; margin-bottom: 8px; color: #64748b; display: flex; align-items: center;">
                        <span><strong style="background: rgba(255,255,255,0.05); color: #94a3b8; padding: 2px 8px; border-radius: 6px; margin-right: 8px;">{letra}</strong> {opt_limpia}</span>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

        # Caja de justificación pedagógica
        st.markdown(
            f"""
            <div style="background: #1c1f2a; border-left: 4px solid #8083ff; border-radius: 8px; padding: 14px 18px; margin-top: 14px; margin-bottom: 18px;">
                <div style="font-weight: 600; color: #c0c1ff; font-size: 0.85rem; margin-bottom: 4px; font-family: 'Geist', sans-serif;">
                    💡 Justificación Pedagógica y Análisis de Errores:
                </div>
                <div style="color: #e2e8f0; font-size: 0.92rem; line-height: 1.55;">
                    {explicacion}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        es_ultima = (idx == total - 1)
        btn_label = "🏆 Finalizar Sesión" if es_ultima else "Siguiente pregunta ➔"

        if st.button(btn_label, type="primary", use_container_width=True, key="btn_avanzar_quiz"):
            if es_ultima:
                st.session_state["quiz_terminado"] = True
                actualizar_racha()
            else:
                st.session_state["quiz_indice"] += 1
                st.session_state["quiz_respondida"] = False
                st.session_state["quiz_opcion_elegida"] = None
            st.rerun()
