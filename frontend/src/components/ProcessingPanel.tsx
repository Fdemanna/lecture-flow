import { useEffect, useRef, useState } from 'react'
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

  // Telemetria SSE en vivo
  const [livePhase, setLivePhase] = useState<string>('iniciando')
  const [liveProgress, setLiveProgress] = useState<number>(0)
  const [liveMessage, setLiveMessage] = useState<string>('Esperando inicio de pipeline…')
  const [logs, setLogs] = useState<string[]>([])

  // onJobFinished llega como funcion nueva en cada render del padre: se guarda en un ref para
  // que el efecto SSE no se reinicie (el backend reenvia el ultimo estado al resuscribirse).
  const onJobFinishedRef = useRef(onJobFinished)
  useEffect(() => {
    onJobFinishedRef.current = onJobFinished
  }, [onJobFinished])
  const jobFinalizadoRef = useRef<string | null>(null)

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
          setLiveMessage(job.message || 'Procesando en segundo plano…')
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

  // 2. Suscribirse a SSE cuando activeJob este presente y no sea externo
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
          if (jobFinalizadoRef.current === ev.job_id) return
          jobFinalizadoRef.current = ev.job_id
          setActiveJob((prev) => (prev ? { ...prev, status: 'completed' } : null))
          setSuccessMsg('Procesamiento finalizado con exito. Apuntes y quiz generados.')
          onJobFinishedRef.current?.()
        } else if (ev.status === 'failed') {
          setActiveJob(null)
          setErrorMsg(ev.error || ev.message || 'Fallo durante el procesamiento.')
        } else if (ev.status === 'cancelled') {
          setActiveJob(null)
          setErrorMsg('El procesamiento ha sido cancelado.')
        }
      },
      () => {
        // En caso de desconexion SSE, intentar sondeo de respaldo
        getActiveJob()
          .then((job) => {
            if (!job) setActiveJob(null)
          })
          .catch((err) => {
            console.error('Error en sondeo de respaldo tras desconexion SSE:', err)
          })
      }
    )

    return () => {
      unsubscribe()
    }
  }, [activeJob?.job_id])

  // 3. Sondeo (polling) periodico cuando activeJob es un proceso externo o archivo de bloqueo (.procesando.lock)
  useEffect(() => {
    if (!activeJob || activeJob.job_id !== 'external') return

    const intervalo = setInterval(async () => {
      try {
        const job = await getActiveJob()
        if (!job) {
          // El lockfile fue liberado o el proceso externo finalizo
          setActiveJob(null)
          setSuccessMsg('El proceso externo ha concluido y el bloqueo ha sido liberado.')
          onJobFinishedRef.current?.()
        } else if (job.job_id !== 'external') {
          // Mutó a un job orquestado con SSE
          setActiveJob(job)
        } else {
          setLiveMessage((prev) => (job.message && job.message !== prev ? job.message : prev))
        }
      } catch (err) {
        console.error('Error al sondear estado de proceso externo:', err)
      }
    }, 2500)

    return () => {
      clearInterval(intervalo)
    }
  }, [activeJob?.job_id])

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
      setErrorMsg('Selecciona un archivo multimedia o presentacion .pptx.')
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
        message: 'Iniciando hilo de ejecucion…',
      }

      setActiveJob(nuevoJob)
      setLivePhase('iniciando')
      setLiveProgress(2)
      setLiveMessage('Iniciando pipeline…')
    } catch (err: any) {
      const is409 =
        err?.status === 409 ||
        err?.response?.status === 409 ||
        (err instanceof Error &&
          (err.message.includes('409') ||
            err.message.toLowerCase().includes('conflicto') ||
            err.message.toLowerCase().includes('conflict') ||
            err.message.toLowerCase().includes('en curso')))

      if (is409) {
        setErrorMsg(
          'Conflicto (409): Ya hay una tarea en curso o existe un archivo de bloqueo pendiente. Revisa si hay un proceso activo.'
        )
      } else {
        setErrorMsg(err instanceof Error ? err.message : String(err))
      }
    } finally {
      setSubmitting(false)
    }
  }

  // Cancelar procesamiento activo o liberar archivo de bloqueo huérfano
  async function handleCancel() {
    if (!activeJob) return
    const esExterno = activeJob.job_id === 'external' || Boolean(activeJob.es_externo)
    const confirmar = window.confirm(
      esExterno
        ? 'Se detecto un proceso externo o archivo de bloqueo activo (data/.procesando.lock). ¿Deseas liberar el bloqueo para permitir nuevas tareas?'
        : '¿Seguro que deseas detener el procesamiento actual?'
    )
    if (!confirmar) return

    try {
      await cancelJob(activeJob.job_id)
      setActiveJob(null)
      const msg = esExterno ? 'Archivo de bloqueo liberado con exito.' : 'Procesamiento cancelado por el usuario.'
      setLogs((prev) => [...prev, msg])
      setSuccessMsg(msg)
      onJobFinishedRef.current?.()
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : 'Error al cancelar o liberar bloqueo.')
    }
  }

  if (checkingActive) {
    return (
      <div className="flex flex-col items-center justify-center p-10 text-slate-400">
        <RefreshCw size={22} className="animate-spin mb-2" />
        <span className="text-sm">Comprobando estado del orquestador…</span>
      </div>
    )
  }

  return (
    <div className="bg-[#141824] border border-white/10 rounded-2xl p-6 sm:p-7 shadow-2xl max-w-3xl mx-auto mb-8">
      {/* Cabecera del Panel */}
      <div className="flex items-center justify-between mb-5">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-indigo-500/15 border border-indigo-500/20 flex items-center justify-center text-indigo-400">
            <Sparkles size={20} />
          </div>
          <div>
            <h2 className="text-lg font-bold text-slate-100">
              Nuevo procesamiento de clase
            </h2>
            <p className="text-xs text-slate-400 mt-0.5">
              Transcribe audio con Whisper o extrae texto de PPTX/PDF y genera apuntes tecnicos con Qwen 2.5 local.
            </p>
          </div>
        </div>

        {onClose && (
          <button
            onClick={onClose}
            className="text-xs text-slate-400 hover:text-slate-200 transition-colors px-2 py-1 rounded-md border border-transparent hover:border-white/10"
          >
            Cerrar
          </button>
        )}
      </div>

      {/* Avisos de Error / Exito */}
      {errorMsg && (
        <div role="alert" aria-live="assertive" className="flex items-center gap-2 p-3 mb-5 rounded-lg bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs sm:text-sm">
          <AlertCircle size={16} className="shrink-0" aria-hidden="true" />
          <span>{errorMsg}</span>
        </div>
      )}

      {successMsg && (
        <div role="status" aria-live="polite" className="flex items-center gap-2 p-3 mb-5 rounded-lg bg-emerald-500/10 border border-emerald-500/30 text-emerald-300 text-xs sm:text-sm">
          <CheckCircle2 size={16} className="shrink-0" aria-hidden="true" />
          <span>{successMsg}</span>
        </div>
      )}

      {/* VISTA 1: MONITOR DE PROGRESO EN VIVO (Si hay job activo o bloqueo externo) */}
      {activeJob ? (
        <div className="bg-[#0f121d] border border-indigo-500/30 rounded-xl p-5 flex flex-col gap-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <span
                className={`w-2.5 h-2.5 rounded-full ${
                  activeJob.job_id === 'external'
                    ? 'bg-amber-400 ring-4 ring-amber-500/20'
                    : 'bg-emerald-400 ring-4 ring-emerald-500/20'
                } animate-pulse`}
              />
              <span className="text-xs sm:text-sm font-semibold text-slate-200">
                {activeJob.job_id === 'external' ? 'Proceso externo / Bloqueo: ' : 'Pipeline activo: '}
                {activeJob.materia} &bull; {activeJob.tema}
              </span>
            </div>

            <button
              onClick={handleCancel}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium text-rose-400 bg-rose-500/10 border border-rose-500/30 hover:bg-rose-500/20 transition-colors cursor-pointer"
            >
              <Square size={12} />
              {activeJob.job_id === 'external' ? 'Liberar bloqueo' : 'Detener procesamiento'}
            </button>
          </div>

          {/* Barra de Progreso */}
          <div>
            <div className="flex justify-between text-xs mb-1.5 font-medium">
              <span className="text-indigo-300 capitalize">
                Fase: {activeJob.job_id === 'external' ? 'Monitoreo externo (polling)' : livePhase}
              </span>
              <span className="text-emerald-400 font-semibold tabular-nums">{liveProgress}%</span>
            </div>

            <div className="w-full h-2 bg-white/5 rounded-full overflow-hidden">
              <div
                className={`h-full ${
                  activeJob.job_id === 'external'
                    ? 'bg-amber-500 animate-pulse'
                    : 'bg-gradient-to-r from-indigo-500 to-emerald-400'
                } rounded-full transition-[width] duration-300 ease-out`}
                style={{ width: `${Math.min(100, Math.max(2, liveProgress))}%` }}
              />
            </div>
            <p className="text-xs text-slate-400 mt-2">
              {activeJob.job_id === 'external'
                ? `${liveMessage} (Sondeando cada 2.5s hasta que se libere el lockfile o finalice la tarea)`
                : liveMessage}
            </p>
          </div>

          {/* Consola de Eventos en Tiempo Real */}
          <div
            role="log"
            aria-live="polite"
            aria-label="Registro de telemetría del proceso"
            className="bg-[#090c12] border border-white/5 rounded-lg p-3 font-mono text-[11px] text-slate-400 max-h-36 overflow-y-auto flex flex-col gap-1"
          >
            {logs.length === 0 ? (
              <span className="italic text-slate-500">Esperando mensajes de telemetria…</span>
            ) : (
              logs.map((log, idx) => <span key={idx}>{log}</span>)
            )}
          </div>
        </div>
      ) : (
        /* VISTA 2: FORMULARIO DE INGESTA */
        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          {/* Fila Asignatura y Tema */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label htmlFor="lf-input-materia" className="block text-xs font-medium text-slate-300 mb-1.5 cursor-pointer">
                Asignatura (materia):
              </label>
              <input
                id="lf-input-materia"
                name="materia"
                type="text"
                autoComplete="off"
                spellCheck={false}
                placeholder="Ej. IPE, Entornos, Programacion"
                value={materia}
                onChange={(e) => setMateria(e.target.value)}
                disabled={submitting}
                className="w-full px-3.5 py-2 bg-[#0f121d] border border-white/10 rounded-lg text-slate-100 text-sm focus:outline-none focus:border-indigo-500/50 transition-colors"
              />
            </div>
            <div>
              <label htmlFor="lf-input-tema" className="block text-xs font-medium text-slate-300 mb-1.5 cursor-pointer">
                Nombre del tema o clase:
              </label>
              <input
                id="lf-input-tema"
                name="tema"
                type="text"
                autoComplete="off"
                spellCheck={false}
                placeholder="Ej. Tema 2 Factores de riesgo"
                value={tema}
                onChange={(e) => setTema(e.target.value)}
                disabled={submitting}
                className="w-full px-3.5 py-2 bg-[#0f121d] border border-white/10 rounded-lg text-slate-100 text-sm focus:outline-none focus:border-indigo-500/50 transition-colors"
              />
            </div>
          </div>

          {/* Selector de Tipo de Origen */}
          <div>
            <label className="block text-xs font-medium text-slate-300 mb-2">
              Fuente de ingesta:
            </label>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
              <button
                type="button"
                onClick={() => setTipoOrigen('url')}
                className={`flex items-center justify-center gap-2 p-2.5 rounded-lg text-xs font-medium border transition-colors ${
                  tipoOrigen === 'url'
                    ? 'bg-indigo-500/15 border-indigo-500/40 text-indigo-300'
                    : 'bg-[#0f121d] border-white/10 text-slate-400 hover:text-slate-200'
                }`}
              >
                <LinkIcon size={14} />
                URL remota (YouTube / Collaborate)
              </button>
              <button
                type="button"
                onClick={() => setTipoOrigen('upload')}
                className={`flex items-center justify-center gap-2 p-2.5 rounded-lg text-xs font-medium border transition-colors ${
                  tipoOrigen === 'upload'
                    ? 'bg-indigo-500/15 border-indigo-500/40 text-indigo-300'
                    : 'bg-[#0f121d] border-white/10 text-slate-400 hover:text-slate-200'
                }`}
              >
                <Upload size={14} />
                Subir archivo (.mp4, .pptx, .pdf)
              </button>
            </div>
          </div>

          {/* Campo condicional segun origen */}
          {tipoOrigen === 'url' ? (
            <div>
              <label htmlFor="lf-input-url" className="block text-xs font-medium text-slate-300 mb-1.5 cursor-pointer">
                Enlace multimedia:
              </label>
              <input
                id="lf-input-url"
                name="url"
                type="url"
                autoComplete="url"
                spellCheck={false}
                placeholder="https://…"
                value={urlInput}
                onChange={(e) => setUrlInput(e.target.value)}
                disabled={submitting}
                className="w-full px-3.5 py-2 bg-[#0f121d] border border-white/10 rounded-lg text-slate-100 text-sm focus:outline-none focus:border-indigo-500/50 transition-colors"
              />
            </div>
          ) : (
            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1.5">
                Archivo local (multimedia, PPTX o PDF):
              </label>
              <div className="border border-dashed border-white/15 rounded-xl p-6 text-center bg-[#0f121d] hover:border-indigo-500/40 transition-colors">
                <input
                  type="file"
                  id="lf-file-upload"
                  accept=".mp4,.mkv,.mp3,.wav,.pptx,.pdf"
                  onChange={(e) => setArchivo(e.target.files?.[0] || null)}
                  className="hidden"
                />
                <label
                  htmlFor="lf-file-upload"
                  className="cursor-pointer flex flex-col items-center gap-2"
                >
                  {archivo ? (
                    <>
                      <FileCheck2 size={28} className="text-emerald-400" />
                      <span className="text-sm font-semibold text-emerald-400">{archivo.name}</span>
                      <span className="text-xs text-slate-400">
                        {(archivo.size / (1024 * 1024)).toFixed(2)} MB &bull; Clic para cambiar
                      </span>
                    </>
                  ) : (
                    <>
                      <Upload size={26} className="text-indigo-400" />
                      <span className="text-sm text-slate-300 font-medium">
                        Selecciona o arrastra un archivo (.mp4, .pptx, .pdf)
                      </span>
                      <span className="text-xs text-slate-500 max-w-sm">
                        Soporte directo para presentaciones PowerPoint (.pptx), documentos PDF (.pdf) y audio o video.
                      </span>
                    </>
                  )}
                </label>
              </div>
            </div>
          )}

          {/* Opciones adicionales */}
          <div className="flex items-center gap-4 text-xs text-slate-300 mt-1">
            <label className="flex items-center gap-2 cursor-pointer select-none">
              <input
                type="checkbox"
                checked={exportarNotion}
                onChange={(e) => setExportarNotion(e.target.checked)}
                className="rounded border-white/20 bg-[#0f121d] text-indigo-500 focus:ring-0"
              />
              <span>Exportar automaticamente a Notion</span>
            </label>
          </div>

          {/* Boton de Inicio */}
          <button
            type="submit"
            disabled={submitting}
            className="w-full inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-semibold text-sm transition-colors shadow-lg shadow-indigo-600/25 disabled:opacity-50 disabled:cursor-not-allowed mt-2"
          >
            {submitting ? <RefreshCw size={15} className="animate-spin" /> : <Play size={15} />}
            <span>{submitting ? 'Lanzando pipeline…' : 'Iniciar procesamiento de clase'}</span>
          </button>
        </form>
      )}
    </div>
  )
}
