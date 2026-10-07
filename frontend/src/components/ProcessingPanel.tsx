import { useEffect, useState } from 'react'
import {
  Upload,
  Link as LinkIcon,
  Play,
  Square,
  Sparkles,
  AlertCircle,
  FileCheck2,
  RefreshCw,
  CheckCircle2,
} from 'lucide-react'
import {
  getActiveJob,
  startJob,
  cancelJob,
  subscribeToJobEvents,
  type JobState,
  type JobEvent,
} from '../services/api'

interface ProcessingPanelProps {
  onJobFinished?: () => void
  onClose?: () => void
}

export function ProcessingPanel({ onJobFinished, onClose }: ProcessingPanelProps) {
  const [activeJob, setActiveJob] = useState<JobState | null>(null)
  const [checkingActive, setCheckingActive] = useState<boolean>(true)

  // Campos de formulario
  const [materia, setMateria] = useState<string>('')
  const [tema, setTema] = useState<string>('')
  const [tipoOrigen, setTipoOrigen] = useState<'url' | 'upload'>('url')
  const [urlInput, setUrlInput] = useState<string>('')
  const [archivo, setArchivo] = useState<File | null>(null)
  const [exportarNotion, setExportarNotion] = useState<boolean>(true)

  // Estado de envío
  const [submitting, setSubmitting] = useState<boolean>(false)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)
  const [successMsg, setSuccessMsg] = useState<string | null>(null)

  // Telemetría SSE en vivo
  const [livePhase, setLivePhase] = useState<string>('iniciando')
  const [liveProgress, setLiveProgress] = useState<number>(0)
  const [liveMessage, setLiveMessage] = useState<string>('Esperando inicio de pipeline...')
  const [logs, setLogs] = useState<string[]>([])

  // 1. Comprobar si ya existe un Job activo al montar
  useEffect(() => {
    let cancel = false

    async function checkJob() {
      try {
        const job = await getActiveJob()
        if (!cancel && job) {
          setActiveJob(job)
          setLivePhase(job.phase || 'en curso')
          setLiveProgress(job.progress || 10)
          setLiveMessage(job.message || 'Procesando en segundo plano...')
        }
      } catch (err) {
        console.error('Error al comprobar job activo:', err)
      } finally {
        if (!cancel) setCheckingActive(false)
      }
    }

    checkJob()

    return () => {
      cancel = true
    }
  }, [])

  // 2. Suscribirse a SSE cuando activeJob esté presente y no sea externo
  useEffect(() => {
    if (!activeJob || activeJob.job_id === 'external') return

    const unsubscribe = subscribeToJobEvents(
      activeJob.job_id,
      (ev: JobEvent) => {
        setLivePhase(ev.phase)
        setLiveProgress(ev.progress)
        setLiveMessage(ev.message)
        setLogs((prev) => [...prev.slice(-25), `[${ev.phase.toUpperCase()}] ${ev.message}`])

        if (ev.status === 'completed') {
          setActiveJob((prev) => (prev ? { ...prev, status: 'completed' } : null))
          setSuccessMsg('¡Procesamiento finalizado con éxito! Apuntes y quiz generados.')
          if (onJobFinished) onJobFinished()
        } else if (ev.status === 'failed') {
          setActiveJob(null)
          setErrorMsg(ev.error || ev.message || 'Fallo durante el procesamiento.')
        } else if (ev.status === 'cancelled') {
          setActiveJob(null)
          setErrorMsg('El procesamiento ha sido cancelado.')
        }
      },
      () => {
        // En caso de desconexión SSE, intentar sondeo de respaldo
        getActiveJob().then((job) => {
          if (!job) setActiveJob(null)
        })
      }
    )

    return () => {
      unsubscribe()
    }
  }, [activeJob?.job_id, onJobFinished])

  // Iniciar nuevo procesamiento
  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setErrorMsg(null)
    setSuccessMsg(null)

    if (!materia.trim() || !tema.trim()) {
      setErrorMsg('Debes especificar la asignatura (materia) y el nombre del tema.')
      return
    }

    if (tipoOrigen === 'url' && !urlInput.trim()) {
      setErrorMsg('Introduce una URL remota de YouTube o Collaborate.')
      return
    }

    if (tipoOrigen === 'upload' && !archivo) {
      setErrorMsg('Selecciona un archivo multimedia o presentación .pptx.')
      return
    }

    setSubmitting(true)

    try {
      let res
      if (tipoOrigen === 'upload' && archivo) {
        const formData = new FormData()
        formData.append('materia', materia.trim())
        formData.append('tema', tema.trim())
        formData.append('tipo_origen', 'upload')
        formData.append('archivo', archivo)
        formData.append('exportar_notion', String(exportarNotion))
        res = await startJob(formData)
      } else {
        res = await startJob({
          materia: materia.trim(),
          tema: tema.trim(),
          tipo_origen: 'url',
          url: urlInput.trim(),
          exportar_notion: exportarNotion,
        })
      }

      const nuevoJob: JobState = {
        job_id: res.job_id,
        materia: res.materia,
        tema: res.tema,
        status: 'running',
        phase: 'iniciando',
        progress: 2,
        message: 'Iniciando hilo de ejecución...',
      }

      setActiveJob(nuevoJob)
      setLivePhase('iniciando')
      setLiveProgress(2)
      setLiveMessage('Iniciando pipeline...')
      setLogs([`Job ${res.job_id} registrado correctamente.`])
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : 'Error al lanzar el procesamiento.')
    } finally {
      setSubmitting(false)
    }
  }

  // Cancelar procesamiento activo
  async function handleCancel() {
    if (!activeJob) return
    const confirmar = window.confirm('¿Seguro que deseas detener el procesamiento actual?')
    if (!confirmar) return

    try {
      await cancelJob(activeJob.job_id)
      setActiveJob(null)
      setLogs((prev) => [...prev, 'Procesamiento cancelado por el usuario.'])
      setErrorMsg('Procesamiento cancelado.')
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : 'Error al cancelar.')
    }
  }

  if (checkingActive) {
    return (
      <div style={{ textAlign: 'center', padding: '40px', color: '#94a3b8' }}>
        <RefreshCw size={24} className="animate-spin" style={{ margin: '0 auto 8px' }} />
        <span>Comprobando estado del orquestador...</span>
      </div>
    )
  }

  return (
    <div
      style={{
        backgroundColor: '#171b26',
        border: '1px solid rgba(255, 255, 255, 0.08)',
        borderRadius: '18px',
        padding: '28px',
        boxShadow: '0 12px 36px rgba(0, 0, 0, 0.35)',
        maxWidth: '840px',
        margin: '0 auto 32px',
      }}
    >
      {/* Cabecera del Panel */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '20px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div
            style={{
              width: '42px',
              height: '42px',
              borderRadius: '10px',
              backgroundColor: 'rgba(128, 131, 255, 0.15)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#8083ff',
            }}
          >
            <Sparkles size={22} />
          </div>
          <div>
            <h2 style={{ margin: 0, fontSize: '1.25rem', fontWeight: 700, color: '#f8fafc' }}>
              Nuevo Procesamiento de Clase
            </h2>
            <p style={{ margin: '2px 0 0', fontSize: '0.82rem', color: '#94a3b8' }}>
              Transcribe audio con Whisper o extrae texto de PPTX/PDF y genera apuntes técnicos con Qwen 2.5 local.
            </p>
          </div>
        </div>

        {onClose && (
          <button
            onClick={onClose}
            style={{
              background: 'transparent',
              border: 'none',
              color: '#94a3b8',
              cursor: 'pointer',
              fontSize: '0.85rem',
            }}
          >
            Cerrar
          </button>
        )}
      </div>

      {/* Avisos de Error / Éxito */}
      {errorMsg && (
        <div
          style={{
            padding: '12px 16px',
            borderRadius: '10px',
            backgroundColor: 'rgba(239, 68, 68, 0.12)',
            border: '1px solid rgba(239, 68, 68, 0.3)',
            color: '#fca5a5',
            fontSize: '0.86rem',
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            marginBottom: '20px',
          }}
        >
          <AlertCircle size={16} />
          <span>{errorMsg}</span>
        </div>
      )}

      {successMsg && (
        <div
          style={{
            padding: '12px 16px',
            borderRadius: '10px',
            backgroundColor: 'rgba(78, 222, 163, 0.12)',
            border: '1px solid rgba(78, 222, 163, 0.3)',
            color: '#4edea3',
            fontSize: '0.86rem',
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            marginBottom: '20px',
          }}
        >
          <CheckCircle2 size={16} />
          <span>{successMsg}</span>
        </div>
      )}

      {/* VISTA 1: MONITOR DE PROGRESO EN VIVO (Si hay job activo) */}
      {activeJob ? (
        <div
          style={{
            backgroundColor: '#12151e',
            border: '1px solid rgba(128, 131, 255, 0.25)',
            borderRadius: '14px',
            padding: '24px',
            display: 'flex',
            flexDirection: 'column',
            gap: '18px',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <span
                style={{
                  display: 'inline-block',
                  width: '10px',
                  height: '10px',
                  borderRadius: '50%',
                  backgroundColor: '#4edea3',
                  boxShadow: '0 0 10px rgba(78, 222, 163, 0.8)',
                }}
              />
              <span style={{ fontSize: '0.85rem', fontWeight: 600, color: '#f8fafc' }}>
                Pipeline Activo: {activeJob.materia} • {activeJob.tema}
              </span>
            </div>

            <button
              onClick={handleCancel}
              style={{
                backgroundColor: 'rgba(239, 68, 68, 0.15)',
                border: '1px solid rgba(239, 68, 68, 0.35)',
                color: '#f87171',
                padding: '6px 14px',
                borderRadius: '8px',
                fontSize: '0.78rem',
                fontWeight: 600,
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
              }}
            >
              <Square size={13} />
              Detener Procesamiento
            </button>
          </div>

          {/* Barra de Progreso */}
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem', marginBottom: '8px' }}>
              <span style={{ color: '#c0c1ff', fontWeight: 600, textTransform: 'capitalize' }}>
                Fase: {livePhase}
              </span>
              <span style={{ color: '#4edea3', fontWeight: 700 }}>{liveProgress}%</span>
            </div>

            <div
              style={{
                width: '100%',
                height: '10px',
                backgroundColor: 'rgba(255, 255, 255, 0.06)',
                borderRadius: '9999px',
                overflow: 'hidden',
              }}
            >
              <div
                style={{
                  width: `${Math.min(100, Math.max(2, liveProgress))}%`,
                  height: '100%',
                  background: 'linear-gradient(90deg, #8083ff, #4edea3)',
                  borderRadius: '9999px',
                  transition: 'width 0.4s ease',
                }}
              />
            </div>
            <p style={{ margin: '8px 0 0', fontSize: '0.82rem', color: '#94a3b8' }}>
              {liveMessage}
            </p>
          </div>

          {/* Consola de Eventos en Tiempo Real */}
          <div
            style={{
              backgroundColor: '#0a0d14',
              border: '1px solid rgba(255, 255, 255, 0.05)',
              borderRadius: '8px',
              padding: '12px 16px',
              fontFamily: "ui-monospace, 'JetBrains Mono', monospace",
              fontSize: '0.76rem',
              color: '#94a3b8',
              maxHeight: '140px',
              overflowY: 'auto',
              display: 'flex',
              flexDirection: 'column',
              gap: '4px',
            }}
          >
            {logs.length === 0 ? (
              <span style={{ fontStyle: 'italic', color: '#475569' }}>Esperando mensajes de telemetría...</span>
            ) : (
              logs.map((log, idx) => <span key={idx}>{log}</span>)
            )}
          </div>
        </div>
      ) : (
        /* VISTA 2: FORMULARIO DE INGESTA */
        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '18px' }}>
          {/* Fila Asignatura y Tema */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
            <div>
              <label style={{ display: 'block', fontSize: '0.82rem', color: '#cbd5e1', fontWeight: 500, marginBottom: '6px' }}>
                Asignatura (Materia):
              </label>
              <input
                type="text"
                placeholder="Ej. IPE, Entornos, Programacion"
                value={materia}
                onChange={(e) => setMateria(e.target.value)}
                disabled={submitting}
                style={{
                  width: '100%',
                  padding: '10px 14px',
                  backgroundColor: '#12151e',
                  border: '1px solid rgba(255, 255, 255, 0.08)',
                  borderRadius: '8px',
                  color: '#f8fafc',
                  fontSize: '0.88rem',
                  outline: 'none',
                  boxSizing: 'border-box',
                }}
              />
            </div>
            <div>
              <label style={{ display: 'block', fontSize: '0.82rem', color: '#cbd5e1', fontWeight: 500, marginBottom: '6px' }}>
                Nombre del Tema o Clase:
              </label>
              <input
                type="text"
                placeholder="Ej. Tema 2 Factores de Riesgo"
                value={tema}
                onChange={(e) => setTema(e.target.value)}
                disabled={submitting}
                style={{
                  width: '100%',
                  padding: '10px 14px',
                  backgroundColor: '#12151e',
                  border: '1px solid rgba(255, 255, 255, 0.08)',
                  borderRadius: '8px',
                  color: '#f8fafc',
                  fontSize: '0.88rem',
                  outline: 'none',
                  boxSizing: 'border-box',
                }}
              />
            </div>
          </div>

          {/* Selector de Tipo de Origen */}
          <div>
            <label style={{ display: 'block', fontSize: '0.82rem', color: '#cbd5e1', fontWeight: 500, marginBottom: '8px' }}>
              Fuente de Ingesta:
            </label>
            <div style={{ display: 'flex', gap: '10px' }}>
              <button
                type="button"
                onClick={() => setTipoOrigen('url')}
                style={{
                  flex: 1,
                  padding: '10px',
                  backgroundColor: tipoOrigen === 'url' ? 'rgba(128, 131, 255, 0.15)' : '#12151e',
                  border: tipoOrigen === 'url' ? '1px solid rgba(128, 131, 255, 0.4)' : '1px solid rgba(255, 255, 255, 0.08)',
                  borderRadius: '8px',
                  color: tipoOrigen === 'url' ? '#c0c1ff' : '#94a3b8',
                  fontSize: '0.84rem',
                  fontWeight: 600,
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '8px',
                }}
              >
                <LinkIcon size={16} />
                URL Remota (YouTube / Collaborate)
              </button>
              <button
                type="button"
                onClick={() => setTipoOrigen('upload')}
                style={{
                  flex: 1,
                  padding: '10px',
                  backgroundColor: tipoOrigen === 'upload' ? 'rgba(128, 131, 255, 0.15)' : '#12151e',
                  border: tipoOrigen === 'upload' ? '1px solid rgba(128, 131, 255, 0.4)' : '1px solid rgba(255, 255, 255, 0.08)',
                  borderRadius: '8px',
                  color: tipoOrigen === 'upload' ? '#c0c1ff' : '#94a3b8',
                  fontSize: '0.84rem',
                  fontWeight: 600,
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '8px',
                }}
              >
                <Upload size={16} />
                Subir Archivo (.mp4, .pptx, .pdf)
              </button>
            </div>
          </div>

          {/* Campo condicional según origen */}
          {tipoOrigen === 'url' ? (
            <div>
              <label style={{ display: 'block', fontSize: '0.82rem', color: '#cbd5e1', fontWeight: 500, marginBottom: '6px' }}>
                Enlace multimedia:
              </label>
              <input
                type="url"
                placeholder="https://..."
                value={urlInput}
                onChange={(e) => setUrlInput(e.target.value)}
                disabled={submitting}
                style={{
                  width: '100%',
                  padding: '10px 14px',
                  backgroundColor: '#12151e',
                  border: '1px solid rgba(255, 255, 255, 0.08)',
                  borderRadius: '8px',
                  color: '#f8fafc',
                  fontSize: '0.88rem',
                  outline: 'none',
                  boxSizing: 'border-box',
                }}
              />
            </div>
          ) : (
            <div>
              <label style={{ display: 'block', fontSize: '0.82rem', color: '#cbd5e1', fontWeight: 500, marginBottom: '6px' }}>
                Archivo local (Multimedia, PPTX o PDF):
              </label>
              <div
                style={{
                  border: '2px dashed rgba(255, 255, 255, 0.1)',
                  borderRadius: '10px',
                  padding: '24px',
                  textAlign: 'center',
                  backgroundColor: '#12151e',
                }}
              >
                <input
                  type="file"
                  id="lf-file-upload"
                  accept=".mp4,.mkv,.mp3,.wav,.pptx,.pdf"
                  onChange={(e) => setArchivo(e.target.files?.[0] || null)}
                  style={{ display: 'none' }}
                />
                <label
                  htmlFor="lf-file-upload"
                  style={{ cursor: 'pointer', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '8px' }}
                >
                  {archivo ? (
                    <>
                      <FileCheck2 size={32} color="#4edea3" />
                      <span style={{ fontSize: '0.9rem', color: '#4edea3', fontWeight: 600 }}>{archivo.name}</span>
                      <span style={{ fontSize: '0.74rem', color: '#94a3b8' }}>
                        {(archivo.size / (1024 * 1024)).toFixed(2)} MB • Haz clic para cambiar
                      </span>
                    </>
                  ) : (
                    <>
                      <Upload size={28} color="#8083ff" />
                      <span style={{ fontSize: '0.88rem', color: '#cbd5e1' }}>
                        Selecciona o arrastra un archivo (.mp4, .pptx, .pdf)
                      </span>
                      <span style={{ fontSize: '0.74rem', color: '#64748b' }}>
                        Soporte directo para presentaciones PowerPoint (.pptx), documentos PDF (.pdf) y audio/video
                      </span>
                    </>
                  )}
                </label>
              </div>
            </div>
          )}

          {/* Opciones adicionales */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '20px', fontSize: '0.82rem', color: '#cbd5e1' }}>
            <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer' }}>
              <input
                type="checkbox"
                checked={exportarNotion}
                onChange={(e) => setExportarNotion(e.target.checked)}
              />
              <span>Exportar automáticamente a Notion</span>
            </label>
          </div>

          {/* Botón de Inicio */}
          <button
            type="submit"
            disabled={submitting}
            style={{
              backgroundColor: '#8083ff',
              border: 'none',
              borderRadius: '10px',
              color: '#ffffff',
              padding: '12px 24px',
              fontSize: '0.92rem',
              fontWeight: 700,
              cursor: submitting ? 'wait' : 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '8px',
              boxShadow: '0 4px 18px rgba(128, 131, 255, 0.35)',
              marginTop: '8px',
            }}
          >
            {submitting ? <RefreshCw size={16} className="animate-spin" /> : <Play size={16} />}
            <span>{submitting ? 'Lanzando Pipeline...' : 'Iniciar Procesamiento de Clase'}</span>
          </button>
        </form>
      )}
    </div>
  )
}
