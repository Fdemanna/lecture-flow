import { useEffect, useState } from 'react'
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
} from 'lucide-react'
import {
  getNotes,
  saveNotes,
  exportToNotion,
  sendTelegramNotification,
  regenerateNotes,
  subscribeToJobEvents,
  type JobEvent,
} from '../services/api'

interface NotesEditorProps {
  subject: string
  subjectName: string
  className: string
  classReadableName: string
  onClose: () => void
}

export function NotesEditor({
  subject,
  subjectName,
  className,
  classReadableName,
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

  async function cargarApuntes() {
    setLoading(true)
    setError(null)
    try {
      const res = await getNotes(subject, className)
      setContent(res.contenido || '')
      setSavedContent(res.contenido || '')
      setLastModified(res.ultima_modificacion || null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al cargar los apuntes desde el disco.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    cargarApuntes()
  }, [subject, className])

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

    try {
      const res = await regenerateNotes(subject, className)
      subscribeToJobEvents(
        res.job_id,
        (ev: JobEvent) => {
          setRegenProgress(ev.progress)
          setRegenMessage(ev.message)

          if (ev.status === 'completed') {
            setRegenerating(false)
            setToastMessage('Apuntes regenerados con éxito.')
            cargarApuntes()
            setTimeout(() => setToastMessage(null), 5000)
          } else if (ev.status === 'failed' || ev.status === 'cancelled') {
            setRegenerating(false)
            setError(ev.error || ev.message || 'La regeneración ha fallado.')
          }
        },
        () => {
          setRegenMessage('Reconectando con el servidor de eventos…')
        }
      )
    } catch (err: any) {
      setRegenerating(false)
      const is409 =
        err?.status === 409 ||
        err?.response?.status === 409 ||
        (err instanceof Error &&
          (err.message.includes('409') ||
            err.message.toLowerCase().includes('conflicto') ||
            err.message.toLowerCase().includes('conflict') ||
            err.message.toLowerCase().includes('en curso')))

      if (is409) {
        setError(
          'Conflicto (409): Ya hay una tarea de procesamiento en curso o existe un archivo de bloqueo pendiente.'
        )
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
      setTimeout(() => {
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
      setTimeout(() => {
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
      setTimeout(() => {
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

  // Advertir al usuario antes de salir si hay cambios sin guardar
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
            onClick={onClose}
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

      {error && (
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
              <div className="text-center py-20 text-slate-500">
                <FileText size={32} className="mx-auto mb-3 text-slate-600" />
                <h3 className="text-base font-semibold text-slate-300 m-0">Apuntes vacíos</h3>
                <p className="text-xs text-slate-500 mt-1 mb-4">
                  Esta clase no contiene texto generado en apuntes.md.
                </p>
                <button
                  onClick={() => setMode('edit')}
                  className="px-4 py-2 text-xs font-medium rounded-lg bg-[#4f6bff] text-white hover:bg-[#637eff] transition-colors cursor-pointer"
                >
                  Abrir editor
                </button>
              </div>
            )}
          </article>
        )}
      </main>
    </div>
  )
}
