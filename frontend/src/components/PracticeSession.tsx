import { useEffect, useState } from 'react'
import {
  Flame,
  Zap,
  Trophy,
  CheckCircle2,
  XCircle,
  ArrowRight,
  RotateCcw,
  X,
  RefreshCw,
  AlertCircle,
} from 'lucide-react'
import {
  getDueQuestions,
  submitAnswer,
  type QuestionDto,
  type AnswerResultDto,
} from '../services/api'

interface PracticeSessionProps {
  onSessionCompleted?: () => void
  onClose: () => void
}

export function PracticeSession({ onSessionCompleted, onClose }: PracticeSessionProps) {
  const [questions, setQuestions] = useState<QuestionDto[]>([])
  const [currentIndex, setCurrentIndex] = useState<number>(0)
  const [loading, setLoading] = useState<boolean>(true)
  const [submitting, setSubmitting] = useState<boolean>(false)
  const [error, setError] = useState<string | null>(null)

  // Estado de la pregunta actual
  const [selectedOption, setSelectedOption] = useState<number | null>(null)
  const [answerResult, setAnswerResult] = useState<AnswerResultDto | null>(null)

  // Métricas acumuladas de la sesión
  const [sessionScore, setSessionScore] = useState<{
    correct: number
    total: number
    xpEarned: number
    finalRacha: number
  }>({
    correct: 0,
    total: 0,
    xpEarned: 0,
    finalRacha: 1,
  })

  const [isFinished, setIsFinished] = useState<boolean>(false)

  async function cargarPreguntas() {
    setLoading(true)
    setError(null)
    setIsFinished(false)
    setCurrentIndex(0)
    setSelectedOption(null)
    setAnswerResult(null)
    setSessionScore({ correct: 0, total: 0, xpEarned: 0, finalRacha: 1 })

    try {
      const lista = await getDueQuestions(5)
      setQuestions(lista)
      if (lista.length === 0) {
        setError('No hay preguntas disponibles en tus clases. Procesa una clase primero.')
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al cargar las preguntas de evaluación.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    cargarPreguntas()
  }, [])

  async function handleSelectOption(optionIndex: number) {
    if (submitting || answerResult !== null) return

    const currentQ = questions[currentIndex]
    if (!currentQ) return

    setSelectedOption(optionIndex)
    setSubmitting(true)

    try {
      const res = await submitAnswer(currentQ.id, optionIndex)
      setAnswerResult(res)

      setSessionScore((prev) => ({
        correct: prev.correct + (res.correct ? 1 : 0),
        total: prev.total + 1,
        xpEarned: prev.xpEarned + (res.correct ? 10 : 0),
        finalRacha: res.stats?.racha_actual ?? prev.finalRacha,
      }))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al enviar tu respuesta.')
    } finally {
      setSubmitting(false)
    }
  }

  function handleNextQuestion() {
    if (currentIndex + 1 < questions.length) {
      setCurrentIndex((prev) => prev + 1)
      setSelectedOption(null)
      setAnswerResult(null)
    } else {
      setIsFinished(true)
      if (onSessionCompleted) {
        onSessionCompleted()
      }
    }
  }

  const currentQ = questions[currentIndex]
  const LETRAS = ['A', 'B', 'C', 'D']

  // =========================================================================
  // 1. PANTALLA DE CARGA O ERROR
  // =========================================================================
  if (loading) {
    return (
      <div
        style={{
          backgroundColor: '#171b26',
          border: '1px solid rgba(255, 255, 255, 0.08)',
          borderRadius: '18px',
          padding: '60px 24px',
          textAlign: 'center',
          color: '#94a3b8',
          maxWidth: '780px',
          margin: '0 auto 32px',
        }}
      >
        <RefreshCw size={32} className="animate-spin" style={{ margin: '0 auto 16px', color: '#8083ff' }} />
        <h3 style={{ margin: 0, color: '#f8fafc', fontSize: '1.15rem' }}>Preparando sesión de Active Recall...</h3>
        <p style={{ margin: '6px 0 0', fontSize: '0.85rem' }}>
          Seleccionando ítems prioritarios con algoritmo de repetición espaciada SM-2.
        </p>
      </div>
    )
  }

  if (error && questions.length === 0) {
    return (
      <div
        style={{
          backgroundColor: '#171b26',
          border: '1px solid rgba(239, 68, 68, 0.3)',
          borderRadius: '18px',
          padding: '40px 28px',
          textAlign: 'center',
          maxWidth: '680px',
          margin: '0 auto 32px',
        }}
      >
        <AlertCircle size={36} color="#ef4444" style={{ margin: '0 auto 12px' }} />
        <h3 style={{ margin: 0, color: '#f8fafc', fontSize: '1.15rem' }}>No hay preguntas disponibles</h3>
        <p style={{ margin: '8px 0 20px', fontSize: '0.86rem', color: '#cbd5e1' }}>{error}</p>
        <button
          onClick={onClose}
          style={{
            backgroundColor: '#8083ff',
            color: '#fff',
            border: 'none',
            padding: '8px 18px',
            borderRadius: '8px',
            fontWeight: 600,
            cursor: 'pointer',
          }}
        >
          Volver al Dashboard
        </button>
      </div>
    )
  }

  // =========================================================================
  // 2. PANTALLA FINAL: RESUMEN DE SESIÓN COMPLETADA
  // =========================================================================
  if (isFinished) {
    const totalP = sessionScore.total || 1
    const porcentaje = Math.round((sessionScore.correct / totalP) * 100)

    return (
      <div
        style={{
          backgroundColor: '#171b26',
          border: '1px solid rgba(255, 255, 255, 0.08)',
          borderRadius: '20px',
          padding: '44px 32px',
          textAlign: 'center',
          maxWidth: '680px',
          margin: '0 auto 32px',
          boxShadow: '0 16px 44px rgba(0, 0, 0, 0.45)',
        }}
      >
        {/* Icono de Trofeo */}
        <div
          style={{
            width: '72px',
            height: '72px',
            borderRadius: '50%',
            backgroundColor: 'rgba(251, 191, 36, 0.15)',
            border: '1px solid rgba(251, 191, 36, 0.35)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            margin: '0 auto 18px',
            color: '#fbbf24',
          }}
        >
          <Trophy size={38} />
        </div>

        <h2 style={{ fontSize: '1.6rem', fontWeight: 800, color: '#f8fafc', margin: '0 0 8px' }}>
          ¡Sesión de Práctica Completada!
        </h2>
        <p style={{ margin: '0 0 28px', color: '#94a3b8', fontSize: '0.9rem' }}>
          Has repasado tus conocimientos con repetición espaciada SM-2 Lite.
        </p>

        {/* 3 Cápsulas Estadísticas */}
        <div
          style={{
            display: 'flex',
            justifyContent: 'center',
            gap: '16px',
            flexWrap: 'wrap',
            marginBottom: '32px',
          }}
        >
          {/* Cápsula Puntuación */}
          <div
            style={{
              backgroundColor: '#1c1f2a',
              border: '1px solid rgba(128, 131, 255, 0.25)',
              borderRadius: '12px',
              padding: '16px 20px',
              minWidth: '150px',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '6px', fontSize: '0.78rem', color: '#94a3b8', fontWeight: 500 }}>
              <Trophy size={14} color="#8083ff" />
              <span>Puntuación</span>
            </div>
            <div style={{ fontSize: '1.45rem', fontWeight: 700, color: '#c0c1ff', marginTop: '2px' }}>
              {sessionScore.correct} / {sessionScore.total} ({porcentaje}%)
            </div>
          </div>

          {/* Cápsula Experiencia */}
          <div
            style={{
              backgroundColor: '#1c1f2a',
              border: '1px solid rgba(78, 222, 163, 0.25)',
              borderRadius: '12px',
              padding: '16px 20px',
              minWidth: '150px',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '6px', fontSize: '0.78rem', color: '#94a3b8', fontWeight: 500 }}>
              <Zap size={14} color="#4edea3" />
              <span>Experiencia Ganada</span>
            </div>
            <div style={{ fontSize: '1.45rem', fontWeight: 700, color: '#4edea3', marginTop: '2px' }}>
              +{sessionScore.xpEarned} XP
            </div>
          </div>

          {/* Cápsula Racha */}
          <div
            style={{
              backgroundColor: '#1c1f2a',
              border: '1px solid rgba(251, 146, 60, 0.25)',
              borderRadius: '12px',
              padding: '16px 20px',
              minWidth: '150px',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '6px', fontSize: '0.78rem', color: '#94a3b8', fontWeight: 500 }}>
              <Flame size={14} color="#fb923c" />
              <span>Racha Diaria</span>
            </div>
            <div style={{ fontSize: '1.45rem', fontWeight: 700, color: '#fb923c', marginTop: '2px' }}>
              🔥 {sessionScore.finalRacha} {sessionScore.finalRacha === 1 ? 'día' : 'días'}
            </div>
          </div>
        </div>

        {/* Botones de Acción */}
        <div style={{ display: 'flex', justifyContent: 'center', gap: '14px' }}>
          <button
            onClick={cargarPreguntas}
            style={{
              backgroundColor: '#12151e',
              border: '1px solid rgba(255, 255, 255, 0.1)',
              color: '#cbd5e1',
              padding: '10px 20px',
              borderRadius: '10px',
              fontSize: '0.88rem',
              fontWeight: 600,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
            }}
          >
            <RotateCcw size={16} />
            Iniciar Otra Sesión
          </button>
          <button
            onClick={onClose}
            style={{
              backgroundColor: '#8083ff',
              border: 'none',
              color: '#ffffff',
              padding: '10px 24px',
              borderRadius: '10px',
              fontSize: '0.88rem',
              fontWeight: 700,
              cursor: 'pointer',
              boxShadow: '0 4px 18px rgba(128, 131, 255, 0.35)',
            }}
          >
            Volver al Dashboard
          </button>
        </div>
      </div>
    )
  }

  // =========================================================================
  // 3. TARJETA DE PREGUNTA INTERACTIVA
  // =========================================================================
  return (
    <div
      style={{
        backgroundColor: '#171b26',
        border: '1px solid rgba(255, 255, 255, 0.08)',
        borderRadius: '20px',
        padding: '32px',
        maxWidth: '820px',
        margin: '0 auto 32px',
        boxShadow: '0 12px 36px rgba(0, 0, 0, 0.35)',
      }}
    >
      {/* Cabecera de la Sesión: Progreso e Indicadores */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          borderBottom: '1px solid rgba(255, 255, 255, 0.06)',
          paddingBottom: '16px',
          marginBottom: '24px',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <span
            style={{
              fontSize: '0.74rem',
              fontWeight: 700,
              backgroundColor: 'rgba(128, 131, 255, 0.15)',
              color: '#c0c1ff',
              padding: '3px 9px',
              borderRadius: '6px',
              border: '1px solid rgba(128, 131, 255, 0.25)',
            }}
          >
            {currentQ?.materia_nombre || currentQ?.materia}
          </span>
          <span style={{ fontSize: '0.82rem', color: '#94a3b8' }}>
            {currentQ?.clase_nombre || currentQ?.clase}
          </span>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
          <span
            style={{
              fontSize: '0.82rem',
              fontWeight: 600,
              color: '#94a3b8',
              backgroundColor: '#12151e',
              padding: '4px 10px',
              borderRadius: '9999px',
              border: '1px solid rgba(255, 255, 255, 0.06)',
            }}
          >
            Pregunta {currentIndex + 1} de {questions.length}
          </span>
          <button
            onClick={onClose}
            title="Cerrar sesión"
            style={{
              background: 'transparent',
              border: 'none',
              color: '#94a3b8',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
            }}
          >
            <X size={18} />
          </button>
        </div>
      </div>

      {/* Enunciado de la Pregunta */}
      <div style={{ marginBottom: '24px' }}>
        <h3
          style={{
            fontSize: '1.25rem',
            fontWeight: 700,
            color: '#f8fafc',
            lineHeight: 1.45,
            margin: '0 0 12px',
          }}
        >
          {currentQ?.pregunta}
        </h3>

        {/* Bloque de Código si existe */}
        {currentQ?.codigo && (
          <pre
            style={{
              backgroundColor: '#0c0f17',
              border: '1px solid rgba(255, 255, 255, 0.06)',
              borderRadius: '8px',
              padding: '14px 18px',
              color: '#f8fafc',
              fontFamily: "ui-monospace, 'JetBrains Mono', monospace",
              fontSize: '0.86rem',
              overflowX: 'auto',
              margin: '12px 0 0',
            }}
          >
            <code>{currentQ.codigo}</code>
          </pre>
        )}
      </div>

      {/* Botones de Opciones */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', marginBottom: '24px' }}>
        {currentQ?.opciones.map((opcionRaw, idx) => {
          // Limpiar prefijo repetido tipo A) o 1.
          const textoLimpio = opcionRaw.replace(/^[A-Da-d][\)\.\-]\s*/, '').trim()
          const letra = LETRAS[idx] || String(idx + 1)

          let btnBg = '#12151e'
          let btnBorder = 'rgba(255, 255, 255, 0.06)'
          let textColor = '#e2e8f0'
          let indicatorIcon = null

          if (answerResult !== null) {
            if (idx === answerResult.correct_index) {
              btnBg = 'rgba(78, 222, 163, 0.15)'
              btnBorder = 'rgba(78, 222, 163, 0.5)'
              textColor = '#4edea3'
              indicatorIcon = <CheckCircle2 size={18} color="#4edea3" />
            } else if (idx === selectedOption && !answerResult.correct) {
              btnBg = 'rgba(239, 68, 68, 0.15)'
              btnBorder = 'rgba(239, 68, 68, 0.5)'
              textColor = '#fca5a5'
              indicatorIcon = <XCircle size={18} color="#ef4444" />
            } else {
              textColor = '#64748b'
            }
          }

          return (
            <button
              key={idx}
              onClick={() => handleSelectOption(idx)}
              disabled={submitting || answerResult !== null}
              style={{
                backgroundColor: btnBg,
                border: `1px solid ${btnBorder}`,
                borderRadius: '12px',
                padding: '14px 18px',
                textAlign: 'left',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                gap: '12px',
                cursor: answerResult === null && !submitting ? 'pointer' : 'default',
                transition: 'all 0.15s ease',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'flex-start', gap: '10px' }}>
                <span
                  style={{
                    fontWeight: 700,
                    color: answerResult !== null && idx === answerResult.correct_index ? '#4edea3' : '#8083ff',
                    minWidth: '22px',
                  }}
                >
                  {letra})
                </span>
                <span style={{ fontSize: '0.92rem', color: textColor, lineHeight: 1.4 }}>
                  {textoLimpio}
                </span>
              </div>
              {indicatorIcon}
            </button>
          )
        })}
      </div>

      {/* Caja de Explicación y Botón Continuar */}
      {answerResult !== null && (
        <div
          style={{
            backgroundColor: answerResult.correct ? 'rgba(78, 222, 163, 0.08)' : 'rgba(239, 68, 68, 0.08)',
            border: `1px solid ${answerResult.correct ? 'rgba(78, 222, 163, 0.3)' : 'rgba(239, 68, 68, 0.3)'}`,
            borderRadius: '14px',
            padding: '20px 24px',
            display: 'flex',
            flexDirection: 'column',
            gap: '14px',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              {answerResult.correct ? (
                <>
                  <CheckCircle2 size={18} color="#4edea3" />
                  <span style={{ color: '#4edea3', fontWeight: 700, fontSize: '0.95rem' }}>
                    ¡Correcto! (+10 XP)
                  </span>
                </>
              ) : (
                <>
                  <XCircle size={18} color="#ef4444" />
                  <span style={{ color: '#f87171', fontWeight: 700, fontSize: '0.95rem' }}>
                    Respuesta Incorrecta
                  </span>
                </>
              )}
            </div>

            <button
              onClick={handleNextQuestion}
              style={{
                backgroundColor: '#8083ff',
                color: '#ffffff',
                border: 'none',
                padding: '8px 18px',
                borderRadius: '8px',
                fontSize: '0.85rem',
                fontWeight: 700,
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                boxShadow: '0 2px 10px rgba(128, 131, 255, 0.3)',
              }}
            >
              <span>{currentIndex + 1 < questions.length ? 'Siguiente Pregunta' : 'Ver Resultados'}</span>
              <ArrowRight size={15} />
            </button>
          </div>

          <p style={{ margin: 0, fontSize: '0.88rem', color: '#cbd5e1', lineHeight: 1.6 }}>
            {answerResult.explanation}
          </p>
        </div>
      )}
    </div>
  )
}
