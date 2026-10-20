import { useEffect, useRef, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import {
  BookOpen,
  Edit3,
  Save,
  CheckCircle2,
  AlertCircle,
  RefreshCw,
  X,
  Clock,
  ExternalLink,
  Send,
  Share2,
  FileText,
  Sparkles,
} from 'lucide-react'
import {
  getNotes,
  saveNotes,
  exportToNotion,
  sendTelegramNotification,
  regenerateNotes,
  subscribeToJobEvents,
  cancelJob,
  getActiveJob,
  ApiError,
  type JobEvent,
  type JobState,
} from '../services/api'

interface NotesEditorProps {
  subject: string
  subjectName: string
  className: string
  classReadableName: string
  hasTranscription?: boolean
  onNotesGenerated?: () => void
  onClose: () => void
}

export function NotesEditor({
  subject,
  subjectName,
  className,
  classReadableName,
  hasTranscription = false,
  onNotesGenerated,
  onClose,
}: NotesEditorProps) {
  const [mode, setMode] = useState<'preview' | 'edit'>('preview')
  const [content, setContent] = useState<string>('')
  const [savedContent, setSavedContent] = useState<string>('')
  const [loading, setLoading] = useState<boolean>(true)
  const [saving, setSaving] = useState<boolean>(false)
  const [error, setError] = useState<string | null>(null)
  const [lastModified, setLastModified] = useState<string | null>(null)
  const [saveFeedback, setSaveFeedback] = useState<{ message: string; timestamp: string } | null>(null)

  // Estados de exportación
  const [exportingNotion, setExportingNotion] = useState<boolean>(false)
  const [notionUrl, setNotionUrl] = useState<string | null>(null)
  const [sendingTelegram, setSendingTelegram] = useState<boolean>(false)
  const [toastMessage, setToastMessage] = useState<string | null>(null)

  // Estados de regeneración
  const [regenerating, setRegenerating] = useState<boolean>(false)
  const [regenProgress, setRegenProgress] = useState<number>(0)
  const [regenMessage, setRegenMessage] = useState<string>('')

  // Estados de conflicto 409
  const [conflictingJob, setConflictingJob] = useState<JobState | null>(null)
  const [cancellingConflicting, setCancellingConflicting] = useState<boolean>(false)

  // Controladores de carreras, suscripciones y timeouts
  const activeAbortControllerRef = useRef<AbortController | null>(null)
  const unsubscribeRegenRef = useRef<(() => void) | null>(null)
  const timeoutIdsRef = useRef<number[]>([])

  function setSafeTimeout(fn: () => void, ms: number) {
    const id = window.setTimeout(() => {
      timeoutIdsRef.current = timeoutIdsRef.current.filter((t) => t !== id)
      fn()
    }, ms)
    timeoutIdsRef.current.push(id)
    return id
  }

  async function cargarApuntes(signal?: AbortSignal) {
    setLoading(true)
    setError(null)
    try {
      const res = await getNotes(subject, className, { signal })
      if (signal?.aborted) return
      setContent(res.contenido || '')
      setSavedContent(res.contenido || '')
      setLastModified(res.ultima_modificacion || null)
    } catch (err: any) {
      if (signal?.aborted || err?.name === 'AbortError') return
      const is404 =
        err?.status === 404 ||
        (err instanceof ApiError && err.status === 404) ||
        (typeof err?.message === 'string' && err.message.includes('404'))

      if (is404) {
        // La clase no tiene apuntes.md generados aún: estado vacío limpio, no es un error
        setContent('')
        setSavedContent('')
        setLastModified(null)
      } else {
        setError(err instanceof Error ? err.message : 'Error al cargar los apuntes desde el disco.')
      }
    } finally {
      if (!signal?.aborted) {
        setLoading(false)
      }
    }
  }

  // Carga reactiva con AbortController, reset de estado por clase y limpieza estricta
  useEffect(() => {
    activeAbortControllerRef.current?.abort()
    const controller = new AbortController()
    activeAbortControllerRef.current = controller

    unsubscribeRegenRef.current?.()
    unsubscribeRegenRef.current = null

    // Reset limpio de estado para evitar mezclas entre clases
    setContent('')
    setSavedContent('')
    setLastModified(null)
    setNotionUrl(null)
    setError(null)
    setToastMessage(null)
    setSaveFeedback(null)
    setRegenerating(false)
    setRegenProgress(0)
    setRegenMessage('')
    setConflictingJob(null)
    setMode('preview')

    cargarApuntes(controller.signal)

    return () => {
      controller.abort()
      unsubscribeRegenRef.current?.()
      timeoutIdsRef.current.forEach((id) => clearTimeout(id))
      timeoutIdsRef.current = []
    }
  }, [subject, className])

  function conectarAJob(job: JobState) {
    setConflictingJob(null)
    setError(null)
    setRegenerating(true)
    setRegenProgress(job.progress || 5)
    setRegenMessage(job.message || 'Procesando en segundo plano…')

    unsubscribeRegenRef.current?.()
    const unsubscribe = subscribeToJobEvents(
      job.job_id,
      (ev: JobEvent) => {
        setRegenProgress(ev.progress)
        setRegenMessage(ev.message)

        if (ev.status === 'completed') {
          setRegenerating(false)
          setToastMessage('Apuntes generados con éxito.')
          cargarApuntes(activeAbortControllerRef.current?.signal)
          setSafeTimeout(() => setToastMessage(null), 5000)
          unsubscribeRegenRef.current = null
          onNotesGenerated?.()
        } else if (ev.status === 'failed' || ev.status === 'cancelled') {
          setRegenerating(false)
          setError(ev.error || ev.message || 'La regeneración ha fallado.')
          unsubscribeRegenRef.current = null
        }
      },
      () => {
        setRegenMessage('Reconectando con el servidor de eventos…')
      }
    )
    unsubscribeRegenRef.current = unsubscribe
  }

  async function handleCancelarConflicto() {
    if (!conflictingJob) return
    const esExterno = conflictingJob.job_id === 'external' || Boolean(conflictingJob.es_externo)
    const confirmar = window.confirm(
      esExterno
        ? '¿Deseas forzar la liberación del archivo de bloqueo data/.procesando.lock?'
        : `¿Deseas detener el procesamiento activo de «${conflictingJob.materia} • ${conflictingJob.tema}»?`
    )
    if (!confirmar) return

    setCancellingConflicting(true)
    try {
      await cancelJob(conflictingJob.job_id)
      setConflictingJob(null)
      setError(null)
      setToastMessage(esExterno ? 'Bloqueo liberado. Ya puedes reintentar la generación.' : 'Procesamiento cancelado.')
      setSafeTimeout(() => setToastMessage(null), 4000)
    } catch (cErr) {
      setError(cErr instanceof Error ? cErr.message : 'Error al cancelar la tarea en conflicto.')
    } finally {
      setCancellingConflicting(false)
    }
  }

  async function handleRegenerate() {
    if (regenerating || saving) return

    const confirmar = window.confirm(
      '¿Regenerar apuntes usando el pipeline actual? Los apuntes actuales se respaldarán automáticamente en un archivo .bak.'
    )
    if (!confirmar) return

    setRegenerating(true)
    setRegenProgress(5)
    setRegenMessage('Iniciando tarea de regeneración…')
    setError(null)
    setConflictingJob(null)

    try {
      const res = await regenerateNotes(subject, className)
      conectarAJob({
        job_id: res.job_id,
        materia: subject,
        tema: className,
        status: 'running',
        phase: 'iniciando',
        progress: 5,
        message: 'Iniciando tarea de regeneración…',
      })
    } catch (err: any) {
      setRegenerating(false)
      if (err instanceof ApiError && err.status === 409) {
        let jobActivo = err.activeJob
        if (!jobActivo) {
          try {
            jobActivo = await getActiveJob()
          } catch {}
        }

        if (jobActivo) {
          const mismaMateria = jobActivo.materia === subject
          const mismaClase = jobActivo.tema === className || jobActivo.tema === classReadableName

          if (mismaMateria && mismaClase && jobActivo.job_id !== 'external') {
            conectarAJob(jobActivo)
            return
          }

          setConflictingJob(jobActivo)
          setError(
            err.message ||
              `Conflicto (409): Ya existe una tarea activa (${jobActivo.materia} • ${jobActivo.tema}).`
          )
          return
        }

        setError(err.message || 'Conflicto (409): Ya hay una tarea en curso o existe un archivo de bloqueo pendiente.')
      } else {
        setError(err instanceof Error ? err.message : String(err))
      }
    }
  }

  async function handleSave() {
    if (saving) return
    setSaving(true)
    setError(null)

    try {
      await saveNotes(subject, className, content)
      setSavedContent(content)
      const ahora = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      setSaveFeedback({
        message: 'Guardado correctamente en disco',
        timestamp: ahora,
      })
      setSafeTimeout(() => {
        setSaveFeedback(null)
      }, 4000)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al guardar los apuntes.')
    } finally {
      setSaving(false)
    }
  }

  async function handleExportNotion() {
    if (exportingNotion) return
    setExportingNotion(true)
    setError(null)

    try {
      const res = await exportToNotion(subject, className)
      setNotionUrl(res.url_notion)
      setToastMessage('Exportado con éxito a la base de datos de Notion.')
      setSafeTimeout(() => {
        setToastMessage(null)
      }, 5000)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al exportar a Notion.')
    } finally {
      setExportingNotion(false)
    }
  }

  async function handleSendTelegram() {
    if (sendingTelegram) return
    setSendingTelegram(true)
    setError(null)

    try {
      await sendTelegramNotification(subject, className, notionUrl || undefined)
      setToastMessage('Notificación enviada a Telegram.')
      setSafeTimeout(() => {
        setToastMessage(null)
      }, 5000)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al notificar por Telegram.')
    } finally {
      setSendingTelegram(false)
    }
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if ((e.ctrlKey || e.metaKey) && e.key === 's') {
      e.preventDefault()
      handleSave()
    }
  }

  const hayCambiosSinGuardar = content !== savedContent

  function handleClose() {
    if (hayCambiosSinGuardar) {
      const descartar = window.confirm(
        'Tienes cambios sin guardar en los apuntes de esta clase. ¿Deseas descartarlos y cerrar?'
      )
      if (!descartar) return
    }
    onClose()
  }

  // Advertir al usuario antes de cerrar o recargar pestaña si hay cambios sin guardar
  useEffect(() => {
    function handleBeforeUnload(e: BeforeUnloadEvent) {
      if (hayCambiosSinGuardar) {
        e.preventDefault()
      }
    }

    window.addEventListener('beforeunload', handleBeforeUnload)
    return () => {
      window.removeEventListener('beforeunload', handleBeforeUnload)
    }
  }, [hayCambiosSinGuardar])

  return (
    <div className="bg-[#141824] border border-white/7 rounded-2xl flex flex-col shadow-2xl overflow-hidden min-h-[700px]">
      {/* 1. Barra Superior y Breadcrumb */}
      <header className="px-6 py-4 border-b border-white/6 bg-[#0f131d] flex items-center justify-between flex-wrap gap-4">
        {/* Metadatos de la clase */}
        <div className="flex items-center gap-3">
          <div>
            <div className="flex items-center gap-2">
              <span className="text-xs font-medium text-slate-400 bg-white/5 border border-white/8 px-2 py-0.5 rounded">
                {subjectName}
              </span>
              <span className="text-slate-600 text-xs">/</span>
              <h2 className="text-base font-semibold text-slate-100 m-0">
                {classReadableName}
              </h2>
            </div>
            {lastModified && (
              <div className="flex items-center gap-1.5 text-xs text-slate-500 mt-1 font-mono">
                <Clock size={12} className="text-slate-500" />
                <span>Modificado: {lastModified}</span>
              </div>
            )}
          </div>
        </div>

        {/* Acciones y selector de modo */}
        <div className="flex items-center gap-3 flex-wrap">
          {/* Segmented Control de modo Lectura / Editor */}
          <div className="bg-[#0b0e14] border border-white/8 p-0.5 rounded-lg flex items-center gap-1">
            <button
              onClick={() => setMode('preview')}
              className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-md transition-colors cursor-pointer ${
                mode === 'preview'
                  ? 'bg-[#1a2030] text-[#e2e8f0] shadow-sm'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <BookOpen size={13} className={mode === 'preview' ? 'text-[#4f6bff]' : 'text-slate-400'} />
              <span>Lectura</span>
            </button>
            <button
              onClick={() => setMode('edit')}
              className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-md transition-colors cursor-pointer ${
                mode === 'edit'
                  ? 'bg-[#1a2030] text-[#e2e8f0] shadow-sm'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <Edit3 size={13} className={mode === 'edit' ? 'text-[#4f6bff]' : 'text-slate-400'} />
              <span>Editor</span>
            </button>
          </div>

          {/* Exportación a Notion */}
          {notionUrl ? (
            <a
              href={notionUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg bg-[#4f6bff]/10 border border-[#4f6bff]/30 text-[#8083ff] hover:bg-[#4f6bff]/20 transition-colors"
            >
              <ExternalLink size={13} />
              <span>Abrir en Notion</span>
            </a>
          ) : (
            <button
              onClick={handleExportNotion}
              disabled={exportingNotion || !content.trim()}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg bg-white/5 border border-white/8 text-slate-300 hover:bg-white/10 transition-colors disabled:opacity-40 cursor-pointer"
            >
              {exportingNotion ? (
                <RefreshCw size={13} className="animate-spin text-slate-400" />
              ) : (
                <Share2 size={13} className="text-slate-400" />
              )}
              <span>{exportingNotion ? 'Exportando…' : 'Exportar a Notion'}</span>
            </button>
          )}

          {/* Notificar por Telegram */}
          <button
            onClick={handleSendTelegram}
            disabled={sendingTelegram || regenerating}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg bg-white/5 border border-white/8 text-slate-300 hover:bg-white/10 transition-colors disabled:opacity-40 cursor-pointer"
            title="Enviar notificación de la clase a Telegram"
          >
            {sendingTelegram ? (
              <RefreshCw size={13} className="animate-spin text-slate-400" />
            ) : (
              <Send size={13} className="text-slate-400" />
            )}
            <span>{sendingTelegram ? 'Enviando…' : 'Notificar Telegram'}</span>
          </button>

          {/* Regenerar apuntes */}
          <button
            onClick={handleRegenerate}
            disabled={regenerating || saving || loading}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg bg-white/5 border border-white/8 text-slate-300 hover:bg-white/10 transition-colors disabled:opacity-40 cursor-pointer"
            title="Regenerar apuntes a partir de transcripcion.txt"
          >
            <RefreshCw size={13} className={regenerating ? 'animate-spin text-[#4f6bff]' : 'text-slate-400'} />
            <span>{regenerating ? 'Regenerando…' : 'Regenerar'}</span>
          </button>

          {/* Guardar cambios (modo edición) */}
          {mode === 'edit' && (
            <button
              onClick={handleSave}
              disabled={saving || !hayCambiosSinGuardar}
              className={`inline-flex items-center gap-1.5 px-3.5 py-1.5 text-xs font-medium rounded-lg transition-colors cursor-pointer ${
                hayCambiosSinGuardar
                  ? 'bg-[#4f6bff] text-white hover:bg-[#637eff] shadow-sm'
                  : 'bg-white/5 text-slate-500 border border-white/5'
              }`}
            >
              {saving ? <RefreshCw size={13} className="animate-spin" /> : <Save size={13} />}
              <span>{saving ? 'Guardando…' : hayCambiosSinGuardar ? 'Guardar cambios' : 'Al día'}</span>
            </button>
          )}

          {/* Botón cerrar */}
          <button
            onClick={handleClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-white/5 transition-colors cursor-pointer"
            title="Cerrar visor"
            aria-label="Cerrar visor de apuntes"
          >
            <X size={16} aria-hidden="true" />
          </button>
        </div>
      </header>

      {/* 2. Banners de feedback y progreso */}
      {toastMessage && (
        <div role="status" aria-live="polite" className="mx-6 mt-4 p-3 rounded-lg bg-[#34d399]/10 border border-[#34d399]/25 text-[#34d399] text-xs flex items-center gap-2">
          <CheckCircle2 size={14} aria-hidden="true" />
          <span>{toastMessage}</span>
        </div>
      )}

      {saveFeedback && (
        <div role="status" aria-live="polite" className="mx-6 mt-4 p-3 rounded-lg bg-[#34d399]/10 border border-[#34d399]/25 text-[#34d399] text-xs flex items-center gap-2">
          <CheckCircle2 size={14} aria-hidden="true" />
          <span>{saveFeedback.message} ({saveFeedback.timestamp})</span>
        </div>
      )}

      {regenerating && (
        <div role="status" aria-live="polite" className="mx-6 mt-4 p-3.5 rounded-lg bg-[#4f6bff]/10 border border-[#4f6bff]/25 text-slate-200 text-xs flex flex-col gap-2">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 font-medium">
              <RefreshCw size={13} className="animate-spin text-[#4f6bff]" aria-hidden="true" />
              <span>{regenMessage || 'Regenerando apuntes en segundo plano…'}</span>
            </div>
            <span className="font-mono font-semibold text-[#8083ff] tabular-nums">{regenProgress}%</span>
          </div>
          <div className="w-full h-1.5 bg-white/10 rounded-full overflow-hidden">
            <div
              className="h-full bg-[#4f6bff] transition-[width] duration-300 ease-out rounded-full"
              style={{ width: `${regenProgress}%` }}
            />
          </div>
        </div>
      )}

      {/* Banner interactivo de conflicto 409 si hay tarea en curso */}
      {conflictingJob && (
        <div role="alert" aria-live="polite" className="mx-6 mt-4 p-4 rounded-xl bg-amber-500/10 border border-amber-500/30 text-amber-300 text-xs flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
          <div className="flex items-start gap-2.5">
            <AlertCircle size={16} className="text-amber-400 shrink-0 mt-0.5" aria-hidden="true" />
            <div>
              <span className="font-semibold block text-slate-200">
                Tarea activa detectada: {conflictingJob.materia} &bull; {conflictingJob.tema}
              </span>
              <span className="text-[11px] text-amber-400/80 mt-0.5 block">
                {conflictingJob.job_id === 'external'
                  ? 'Existe un archivo de bloqueo pendiente en disco (data/.procesando.lock).'
                  : `Fase actual: ${conflictingJob.phase} (${conflictingJob.progress}%)`}
              </span>
            </div>
          </div>

          <div className="flex items-center gap-2 self-end sm:self-auto shrink-0">
            {conflictingJob.job_id !== 'external' && (
              <button
                type="button"
                onClick={() => conectarAJob(conflictingJob)}
                className="px-3 py-1.5 rounded-lg bg-amber-500/20 hover:bg-amber-500/30 text-amber-200 font-medium transition-colors cursor-pointer border border-amber-500/40 text-xs"
              >
                Ver progreso
              </button>
            )}
            <button
              type="button"
              onClick={handleCancelarConflicto}
              disabled={cancellingConflicting}
              className="px-3 py-1.5 rounded-lg bg-rose-500/20 hover:bg-rose-500/30 text-rose-300 font-medium transition-colors cursor-pointer border border-rose-500/40 text-xs disabled:opacity-50"
            >
              {cancellingConflicting ? 'Liberando…' : conflictingJob.job_id === 'external' ? 'Liberar bloqueo' : 'Detener tarea'}
            </button>
          </div>
        </div>
      )}

      {error && !conflictingJob && (
        <div role="alert" aria-live="assertive" className="mx-6 mt-4 p-3.5 rounded-lg bg-[#f87171]/10 border border-[#f87171]/25 text-[#f87171] text-xs flex items-center gap-2">
          <AlertCircle size={15} className="shrink-0" aria-hidden="true" />
          <span>{error}</span>
        </div>
      )}

      {/* 3. Área de Lectura y Edición */}
      <main className="flex-1 p-6 flex flex-col overflow-y-auto">
        {loading ? (
          <div className="flex-1 flex flex-col items-center justify-center text-slate-400 py-24">
            <RefreshCw size={24} className="animate-spin text-[#4f6bff] mb-3" aria-hidden="true" />
            <p className="text-sm m-0">Leyendo apuntes desde el disco local…</p>
          </div>
        ) : mode === 'edit' ? (
          <div className="flex flex-col flex-1">
            <textarea
              value={content}
              onChange={(e) => setContent(e.target.value)}
              onKeyDown={handleKeyDown}
              aria-label="Editor de apuntes Markdown"
              placeholder="Escribe aquí tus apuntes en formato Markdown…"
              className="w-full flex-1 min-h-[560px] bg-[#0b0e14] text-[#e2e8f0] border border-white/8 rounded-xl p-5 font-mono text-sm leading-relaxed outline-none focus:border-[#4f6bff]/60 resize-y"
            />
            <footer className="mt-3 flex items-center justify-between text-xs text-slate-500 font-mono">
              <span>Atajo: pulsa Ctrl + S o Cmd + S para guardar los cambios.</span>
              <span>
                {content.length} caracteres • {content.split(/\s+/).filter(Boolean).length} palabras
              </span>
            </footer>
          </div>
        ) : (
          <article className="bg-[#0b0e14] border border-white/6 rounded-xl p-8 lg:p-12 text-[#e2e8f0] overflow-y-auto max-h-[75vh]">
            {content.trim() ? (
              <div className="reading-column markdown-body">
                <ReactMarkdown>{content}</ReactMarkdown>
              </div>
            ) : (
              <div className="text-center py-16 px-4 text-slate-400 max-w-md mx-auto">
                <div className="w-14 h-14 rounded-2xl bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 flex items-center justify-center mx-auto mb-4">
                  {hasTranscription ? <Sparkles size={26} /> : <FileText size={26} />}
                </div>
                <h3 className="text-base font-semibold text-slate-100 m-0">
                  {hasTranscription ? 'Apuntes pendientes de generación' : 'Apuntes no encontrados'}
                </h3>
                <p className="text-xs text-slate-400 mt-2 mb-6 leading-relaxed">
                  {hasTranscription
                    ? 'Esta clase dispone de archivo de transcripción local. Puedes iniciar la extracción estructurada de apuntes y preguntas con el pipeline de IA.'
                    : 'Esta clase aún no cuenta con archivo de apuntes.md en disco. Puedes abrir el editor para comenzar a redactar tus notas.'}
                </p>

                <div className="flex items-center justify-center gap-3 flex-wrap">
                  {hasTranscription && (
                    <button
                      onClick={handleRegenerate}
                      disabled={regenerating || loading}
                      className="inline-flex items-center gap-2 px-4 py-2 text-xs font-semibold rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white shadow-md shadow-indigo-600/20 transition-all cursor-pointer disabled:opacity-50"
                    >
                      {regenerating ? (
                        <RefreshCw size={14} className="animate-spin text-white" />
                      ) : (
                        <Sparkles size={14} />
                      )}
                      <span>{regenerating ? 'Generando apuntes…' : 'Generar apuntes con IA'}</span>
                    </button>
                  )}
                  <button
                    onClick={() => setMode('edit')}
                    className="inline-flex items-center gap-1.5 px-4 py-2 text-xs font-medium rounded-lg bg-white/5 hover:bg-white/10 text-slate-300 border border-white/10 transition-colors cursor-pointer"
                  >
                    <Edit3 size={14} />
                    <span>{hasTranscription ? 'Escribir manualmente' : 'Abrir editor'}</span>
                  </button>
                </div>
              </div>
            )}
          </article>
        )}
      </main>
    </div>
  )
}
