import { useEffect, useState } from 'react'
import {
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
        setError('No hay preguntas disponibles en tus clases. Genera apuntes para procesar preguntas.')
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
      setError(err instanceof Error ? err.message : 'Error al registrar tu respuesta.')
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

  // 1. Pantalla de carga
  if (loading) {
    return (
      <div className="bg-[#141824] border border-white/7 rounded-2xl p-16 text-center text-slate-400 max-w-2xl mx-auto mb-8 shadow-xl">
        <RefreshCw size={28} className="animate-spin text-[#4f6bff] mx-auto mb-3" />
        <h3 className="text-base font-semibold text-slate-100 m-0">Preparando sesión de práctica</h3>
        <p className="text-xs text-slate-500 mt-1.5 mb-0">
          Seleccionando ítems prioritarios mediante el algoritmo SM-2 Lite.
        </p>
      </div>
    )
  }

  // 2. Pantalla de error o sin preguntas
  if (error && questions.length === 0) {
    return (
      <div className="bg-[#141824] border border-red-500/25 rounded-2xl p-10 text-center max-w-lg mx-auto mb-8 shadow-xl">
        <AlertCircle size={32} className="text-red-400 mx-auto mb-3" />
        <h3 className="text-base font-semibold text-slate-100 m-0">Sin preguntas para repasar</h3>
        <p className="text-xs text-slate-400 mt-2 mb-6 leading-relaxed">{error}</p>
        <button
          onClick={onClose}
          className="px-4 py-2 text-xs font-medium rounded-lg bg-[#4f6bff] text-white hover:bg-[#637eff] transition-colors cursor-pointer"
        >
          Volver al espacio de trabajo
        </button>
      </div>
    )
  }

  // 3. Pantalla de resumen final
  if (isFinished) {
    const totalP = sessionScore.total || 1
    const porcentaje = Math.round((sessionScore.correct / totalP) * 100)

    return (
      <div className="bg-[#141824] border border-white/8 rounded-2xl p-10 text-center max-w-xl mx-auto mb-8 shadow-2xl">
        <div className="w-14 h-14 rounded-full bg-[#4f6bff]/15 border border-[#4f6bff]/30 flex items-center justify-center mx-auto mb-4 text-[#8083ff]">
          <Trophy size={28} />
        </div>

        <h2 className="text-xl font-bold text-slate-100 m-0 mb-1 text-balance">
          Sesión de práctica completada
        </h2>
        <p className="text-xs text-slate-400 m-0 mb-6 text-pretty">
          Has repasado tus conocimientos con repetición espaciada SM-2 Lite.
        </p>

        {/* Métricas clave */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mb-8">
          <div className="bg-[#0b0e14] border border-white/6 rounded-xl p-4">
            <span className="text-[11px] font-mono text-slate-500 block mb-1">Puntuación</span>
            <span className="text-lg font-bold text-[#c0c1ff] tabular-nums">
              {sessionScore.correct} / {sessionScore.total}
            </span>
            <span className="text-[11px] text-slate-500 block mt-0.5 font-mono tabular-nums">({porcentaje}%)</span>
          </div>

          <div className="bg-[#0b0e14] border border-white/6 rounded-xl p-4">
            <span className="text-[11px] font-mono text-slate-500 block mb-1">Experiencia</span>
            <span className="text-lg font-bold text-[#34d399] tabular-nums">
              +{sessionScore.xpEarned} XP
            </span>
            <span className="text-[11px] text-slate-500 block mt-0.5 font-mono">acumulada</span>
          </div>

          <div className="bg-[#0b0e14] border border-white/6 rounded-xl p-4">
            <span className="text-[11px] font-mono text-slate-500 block mb-1">Racha diaria</span>
            <span className="text-lg font-bold text-[#e5a158] tabular-nums">
              {sessionScore.finalRacha} {sessionScore.finalRacha === 1 ? 'día' : 'días'}
            </span>
            <span className="text-[11px] text-slate-500 block mt-0.5 font-mono">consecutivos</span>
          </div>
        </div>

        {/* Acciones finales */}
        <div className="flex items-center justify-center gap-3">
          <button
            onClick={cargarPreguntas}
            className="inline-flex items-center gap-2 px-4 py-2 text-xs font-medium rounded-lg bg-white/5 border border-white/10 text-slate-300 hover:bg-white/10 hover:text-white transition-colors cursor-pointer"
          >
            <RotateCcw size={14} />
            <span>Iniciar otra sesión</span>
          </button>
          <button
            onClick={onClose}
            className="px-5 py-2 text-xs font-medium rounded-lg bg-[#4f6bff] text-white hover:bg-[#637eff] transition-colors cursor-pointer shadow-sm"
          >
            Volver al espacio de trabajo
          </button>
        </div>
      </div>
    )
  }

  // 4. Tarjeta interactiva de pregunta
  return (
    <div className="bg-[#141824] border border-white/7 rounded-2xl p-8 max-w-3xl mx-auto mb-8 shadow-2xl">
      {/* Cabecera de la pregunta */}
      <header className="flex items-center justify-between border-b border-white/6 pb-4 mb-6">
        <div className="flex items-center gap-2 text-xs">
          <span className="font-medium text-slate-300 bg-white/5 border border-white/8 px-2 py-0.5 rounded">
            {currentQ?.materia_nombre || currentQ?.materia}
          </span>
          <span className="text-slate-600">/</span>
          <span className="text-slate-400">
            {currentQ?.clase_nombre || currentQ?.clase}
          </span>
        </div>

        <div className="flex items-center gap-3">
          <span className="text-xs font-mono tabular-nums text-slate-400 bg-white/5 px-2.5 py-1 rounded-full border border-white/6">
            Pregunta {currentIndex + 1} de {questions.length}
          </span>
          <button
            onClick={onClose}
            className="text-slate-500 hover:text-slate-300 transition-colors cursor-pointer"
            title="Cerrar sesión"
          >
            <X size={16} />
          </button>
        </div>
      </header>

      {/* Enunciado */}
      <div className="mb-6">
        <h3 className="text-base sm:text-lg font-semibold text-slate-100 leading-snug m-0 mb-3 text-pretty">
          {currentQ?.pregunta}
        </h3>

        {currentQ?.codigo && (
          <pre className="bg-[#090c12] border border-white/6 rounded-lg p-4 font-mono text-xs text-slate-200 overflow-x-auto mt-3">
            <code>{currentQ.codigo}</code>
          </pre>
        )}
      </div>

      {/* Opciones */}
      <div className="flex flex-col gap-2.5 mb-6">
        {currentQ?.opciones.map((opcionRaw, idx) => {
          const textoLimpio = opcionRaw.replace(/^[A-Da-d][\)\.\-]\s*/, '').trim()
          const letra = LETRAS[idx] || String(idx + 1)

          let cardStyle = 'bg-[#0b0e14] border-white/7 text-slate-300 hover:bg-[#1a2030] hover:text-white'
          let indicatorIcon = null

          if (answerResult !== null) {
            if (idx === answerResult.correct_index) {
              cardStyle = 'bg-[#34d399]/15 border-[#34d399]/40 text-[#34d399]'
              indicatorIcon = <CheckCircle2 size={16} className="text-[#34d399] shrink-0" />
            } else if (idx === selectedOption && !answerResult.correct) {
              cardStyle = 'bg-[#f87171]/15 border-[#f87171]/40 text-[#f87171]'
              indicatorIcon = <XCircle size={16} className="text-[#f87171] shrink-0" />
            } else {
              cardStyle = 'bg-[#0b0e14]/50 border-white/5 text-slate-600 opacity-60'
            }
          }

          return (
            <button
              key={idx}
              onClick={() => handleSelectOption(idx)}
              disabled={submitting || answerResult !== null}
              className={`p-3.5 rounded-xl border text-left flex items-center justify-between gap-3 transition-colors cursor-pointer disabled:cursor-default ${cardStyle}`}
            >
              <div className="flex items-start gap-3">
                <span className="font-mono font-semibold text-xs text-slate-400 mt-0.5 min-w-[18px]">
                  {letra})
                </span>
                <span className="text-xs leading-relaxed">{textoLimpio}</span>
              </div>
              {indicatorIcon}
            </button>
          )
        })}
      </div>

      {/* Explicación y botón siguiente */}
      {answerResult !== null && (
        <div
          className={`p-4 rounded-xl border flex flex-col gap-3 ${
            answerResult.correct
              ? 'bg-[#34d399]/10 border-[#34d399]/30 text-slate-200'
              : 'bg-[#f87171]/10 border-[#f87171]/30 text-slate-200'
          }`}
        >
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              {answerResult.correct ? (
                <>
                  <CheckCircle2 size={16} className="text-[#34d399]" />
                  <span className="text-xs font-semibold text-[#34d399]">
                    Respuesta correcta (+10 XP)
                  </span>
                </>
              ) : (
                <>
                  <XCircle size={16} className="text-[#f87171]" />
                  <span className="text-xs font-semibold text-[#f87171]">
                    Respuesta incorrecta
                  </span>
                </>
              )}
            </div>

            <button
              onClick={handleNextQuestion}
              className="inline-flex items-center gap-1.5 px-3.5 py-1.5 text-xs font-medium rounded-lg bg-[#4f6bff] text-white hover:bg-[#637eff] transition-colors cursor-pointer shadow-sm"
            >
              <span>{currentIndex + 1 < questions.length ? 'Siguiente pregunta' : 'Ver resultados'}</span>
              <ArrowRight size={13} />
            </button>
          </div>

          <p className="text-xs text-slate-300 leading-relaxed m-0 border-t border-white/6 pt-2">
            {answerResult.explanation}
          </p>
        </div>
      )}
    </div>
  )
}
