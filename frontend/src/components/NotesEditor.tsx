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
  Sparkles,
  ExternalLink,
  Send,
  Share2,
} from 'lucide-react'
import {
  getNotes,
  saveNotes,
  exportToNotion,
  sendTelegramNotification,
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

  useEffect(() => {
    let cancel = false

    async function cargarApuntes() {
      setLoading(true)
      setError(null)
      try {
        const res = await getNotes(subject, className)
        if (!cancel) {
          setContent(res.contenido || '')
          setSavedContent(res.contenido || '')
          setLastModified(res.ultima_modificacion || null)
        }
      } catch (err) {
        if (!cancel) {
          setError(err instanceof Error ? err.message : 'Error al cargar los apuntes.')
        }
      } finally {
        if (!cancel) {
          setLoading(false)
        }
      }
    }

    cargarApuntes()

    return () => {
      cancel = true
    }
  }, [subject, className])

  async function handleSave() {
    if (saving) return
    setSaving(true)
    setError(null)

    try {
      await saveNotes(subject, className, content)
      setSavedContent(content)
      const ahora = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      setSaveFeedback({
        message: 'Guardado correctamente',
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
      setToastMessage('Exportado con éxito a Notion')
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
      setToastMessage('Enviado a Telegram')
      setTimeout(() => {
        setToastMessage(null)
      }, 5000)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al notificar por Telegram.')
    } finally {
      setSendingTelegram(false)
    }
  }

  // Atajo de teclado: Ctrl+S o Cmd+S para guardar
  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if ((e.ctrlKey || e.metaKey) && e.key === 's') {
      e.preventDefault()
      handleSave()
    }
  }

  const hayCambiosSinGuardar = content !== savedContent

  return (
    <div
      style={{
        backgroundColor: '#171b26',
        border: '1px solid rgba(255, 255, 255, 0.08)',
        borderRadius: '18px',
        display: 'flex',
        flexDirection: 'column',
        boxShadow: '0 12px 36px rgba(0, 0, 0, 0.35)',
        overflow: 'hidden',
        minHeight: '680px',
      }}
    >
      {/* 1. Barra Superior / Cabecera */}
      <div
        style={{
          padding: '16px 24px',
          borderBottom: '1px solid rgba(255, 255, 255, 0.06)',
          backgroundColor: '#121622',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: '12px',
        }}
      >
        {/* Información de Clase y Materia */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span
                style={{
                  fontSize: '0.72rem',
                  fontWeight: 600,
                  backgroundColor: 'rgba(128, 131, 255, 0.15)',
                  color: '#c0c1ff',
                  padding: '2px 8px',
                  borderRadius: '6px',
                  border: '1px solid rgba(128, 131, 255, 0.25)',
                }}
              >
                {subjectName}
              </span>
              <h2 style={{ margin: 0, fontSize: '1.15rem', fontWeight: 700, color: '#f8fafc' }}>
                {classReadableName}
              </h2>
            </div>
            {lastModified && (
              <div style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '0.74rem', color: '#64748b', marginTop: '3px' }}>
                <Clock size={12} />
                <span>Última modificación en disco: {lastModified}</span>
              </div>
            )}
          </div>
        </div>

        {/* Controles de Modo y Acciones */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          {/* Selector Segmentado de Modo */}
          <div
            style={{
              backgroundColor: '#0f131d',
              border: '1px solid rgba(255, 255, 255, 0.08)',
              borderRadius: '8px',
              padding: '3px',
              display: 'flex',
              gap: '2px',
            }}
          >
            <button
              onClick={() => setMode('preview')}
              style={{
                backgroundColor: mode === 'preview' ? 'rgba(128, 131, 255, 0.2)' : 'transparent',
                color: mode === 'preview' ? '#c0c1ff' : '#94a3b8',
                border: mode === 'preview' ? '1px solid rgba(128, 131, 255, 0.3)' : '1px solid transparent',
                borderRadius: '6px',
                padding: '6px 12px',
                fontSize: '0.82rem',
                fontWeight: 600,
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                transition: 'all 0.15s',
              }}
            >
              <BookOpen size={14} />
              Modo Lectura
            </button>
            <button
              onClick={() => setMode('edit')}
              style={{
                backgroundColor: mode === 'edit' ? 'rgba(128, 131, 255, 0.2)' : 'transparent',
                color: mode === 'edit' ? '#c0c1ff' : '#94a3b8',
                border: mode === 'edit' ? '1px solid rgba(128, 131, 255, 0.3)' : '1px solid transparent',
                borderRadius: '6px',
                padding: '6px 12px',
                fontSize: '0.82rem',
                fontWeight: 600,
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                transition: 'all 0.15s',
              }}
            >
              <Edit3 size={14} />
              Modo Editor
            </button>
          </div>

          {/* Botón Exportar a Notion / Enlace Directo */}
          {notionUrl ? (
            <a
              href={notionUrl}
              target="_blank"
              rel="noopener noreferrer"
              style={{
                backgroundColor: 'rgba(128, 131, 255, 0.15)',
                border: '1px solid rgba(128, 131, 255, 0.35)',
                color: '#c0c1ff',
                borderRadius: '8px',
                padding: '6px 12px',
                fontSize: '0.82rem',
                fontWeight: 600,
                textDecoration: 'none',
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                transition: 'all 0.15s',
              }}
              title="Abrir página generada en Notion"
            >
              <ExternalLink size={14} color="#8083ff" />
              <span>Abrir en Notion ↗</span>
            </a>
          ) : (
            <button
              onClick={handleExportNotion}
              disabled={exportingNotion || !content.trim()}
              style={{
                backgroundColor: 'rgba(128, 131, 255, 0.1)',
                border: '1px solid rgba(128, 131, 255, 0.25)',
                color: '#c0c1ff',
                borderRadius: '8px',
                padding: '6px 12px',
                fontSize: '0.82rem',
                fontWeight: 600,
                cursor: exportingNotion || !content.trim() ? 'default' : 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                opacity: !content.trim() ? 0.6 : 1,
                transition: 'all 0.15s',
              }}
              title="Exportar apuntes directamente a Notion"
            >
              {exportingNotion ? (
                <RefreshCw size={14} className="animate-spin" />
              ) : (
                <Share2 size={14} />
              )}
              <span>{exportingNotion ? 'Exportando...' : '📤 Exportar a Notion'}</span>
            </button>
          )}

          {/* Botón Notificar Telegram */}
          <button
            onClick={handleSendTelegram}
            disabled={sendingTelegram}
            style={{
              backgroundColor: 'rgba(56, 189, 248, 0.1)',
              border: '1px solid rgba(56, 189, 248, 0.25)',
              color: '#38bdf8',
              borderRadius: '8px',
              padding: '6px 12px',
              fontSize: '0.82rem',
              fontWeight: 600,
              cursor: sendingTelegram ? 'default' : 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              transition: 'all 0.15s',
            }}
            title="Enviar notificación de la clase a tu canal/chat de Telegram"
          >
            {sendingTelegram ? (
              <RefreshCw size={14} className="animate-spin" />
            ) : (
              <Send size={14} />
            )}
            <span>{sendingTelegram ? 'Enviando...' : '📱 Notificar Telegram'}</span>
          </button>

          {/* Toast Feedback Temporal */}
          {toastMessage && (
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                fontSize: '0.78rem',
                color: '#4edea3',
                backgroundColor: 'rgba(78, 222, 163, 0.12)',
                border: '1px solid rgba(78, 222, 163, 0.25)',
                padding: '6px 10px',
                borderRadius: '6px',
              }}
            >
              <CheckCircle2 size={13} />
              <span>{toastMessage}</span>
            </div>
          )}

          {/* Feedback de Guardado */}
          {saveFeedback && (
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                fontSize: '0.78rem',
                color: '#4edea3',
                backgroundColor: 'rgba(78, 222, 163, 0.12)',
                border: '1px solid rgba(78, 222, 163, 0.25)',
                padding: '6px 10px',
                borderRadius: '6px',
              }}
            >
              <CheckCircle2 size={13} />
              <span>{saveFeedback.message} ({saveFeedback.timestamp})</span>
            </div>
          )}

          {/* Botón Guardar Cambios */}
          {mode === 'edit' && (
            <button
              onClick={handleSave}
              disabled={saving || !hayCambiosSinGuardar}
              style={{
                backgroundColor: hayCambiosSinGuardar ? '#8083ff' : 'rgba(255, 255, 255, 0.05)',
                color: hayCambiosSinGuardar ? '#ffffff' : '#64748b',
                border: hayCambiosSinGuardar ? '1px solid rgba(128, 131, 255, 0.4)' : '1px solid rgba(255, 255, 255, 0.08)',
                borderRadius: '8px',
                padding: '7px 16px',
                fontSize: '0.82rem',
                fontWeight: 600,
                cursor: hayCambiosSinGuardar && !saving ? 'pointer' : 'default',
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                boxShadow: hayCambiosSinGuardar ? '0 0 16px rgba(128, 131, 255, 0.3)' : 'none',
                transition: 'all 0.2s',
              }}
              title="Guardar apuntes (Ctrl+S / Cmd+S)"
            >
              {saving ? <RefreshCw size={14} className="animate-spin" /> : <Save size={14} />}
              {saving ? 'Guardando...' : hayCambiosSinGuardar ? 'Guardar Cambios *' : 'Al día'}
            </button>
          )}

          {/* Botón Cerrar Visor */}
          <button
            onClick={onClose}
            title="Cerrar visor"
            style={{
              backgroundColor: 'transparent',
              border: 'none',
              color: '#94a3b8',
              cursor: 'pointer',
              padding: '6px',
              borderRadius: '6px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <X size={18} />
          </button>
        </div>
      </div>

      {/* 2. Banner de Error si ocurre */}
      {error && (
        <div
          style={{
            margin: '12px 24px 0',
            padding: '12px 16px',
            borderRadius: '8px',
            backgroundColor: 'rgba(239, 68, 68, 0.12)',
            border: '1px solid rgba(239, 68, 68, 0.25)',
            color: '#fca5a5',
            fontSize: '0.85rem',
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
          }}
        >
          <AlertCircle size={16} />
          <span>{error}</span>
        </div>
      )}

      {/* 3. Área de Contenido (Lectura vs Editor) */}
      <div style={{ flex: 1, padding: '24px', display: 'flex', flexDirection: 'column' }}>
        {loading ? (
          <div
            style={{
              flex: 1,
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#94a3b8',
              padding: '80px 0',
            }}
          >
            <RefreshCw size={28} className="animate-spin" style={{ marginBottom: '12px', color: '#8083ff' }} />
            <p style={{ margin: 0, fontSize: '0.9rem' }}>Cargando apuntes desde el disco local...</p>
          </div>
        ) : mode === 'edit' ? (
          <div style={{ display: 'flex', flexDirection: 'column', flex: 1 }}>
            <textarea
              value={content}
              onChange={(e) => setContent(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="# Escribe aquí tus apuntes en formato Markdown..."
              style={{
                width: '100%',
                flex: 1,
                minHeight: '560px',
                backgroundColor: '#12151e',
                color: '#f8fafc',
                border: '1px solid rgba(255, 255, 255, 0.08)',
                borderRadius: '12px',
                padding: '20px',
                fontFamily: "ui-monospace, 'JetBrains Mono', SFMono-Regular, Menlo, Monaco, Consolas, monospace",
                fontSize: '0.9rem',
                lineHeight: 1.6,
                boxSizing: 'border-box',
                resize: 'vertical',
                outline: 'none',
              }}
            />
            <div style={{ marginTop: '8px', display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem', color: '#64748b' }}>
              <span>Consejo: pulsa <strong>Ctrl + S</strong> / <strong>Cmd + S</strong> para guardar rápidamente.</span>
              <span>{content.length} caracteres • {content.split(/\s+/).filter(Boolean).length} palabras</span>
            </div>
          </div>
        ) : (
          <div
            style={{
              backgroundColor: '#12151e',
              border: '1px solid rgba(255, 255, 255, 0.05)',
              borderRadius: '12px',
              padding: '32px 36px',
              color: '#e2e8f0',
              lineHeight: 1.7,
              fontSize: '0.96rem',
              overflowY: 'auto',
              maxHeight: '75vh',
            }}
          >
            {content.trim() ? (
              <ReactMarkdown
                components={{
                  h1: ({ children }) => (
                    <h1
                      style={{
                        fontSize: '1.65rem',
                        fontWeight: 800,
                        color: '#f8fafc',
                        borderBottom: '1px solid rgba(255, 255, 255, 0.08)',
                        paddingBottom: '10px',
                        marginTop: '16px',
                        marginBottom: '16px',
                      }}
                    >
                      {children}
                    </h1>
                  ),
                  h2: ({ children }) => (
                    <h2
                      style={{
                        fontSize: '1.3rem',
                        fontWeight: 700,
                        color: '#8083ff',
                        marginTop: '28px',
                        marginBottom: '12px',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '6px',
                      }}
                    >
                      {children}
                    </h2>
                  ),
                  h3: ({ children }) => (
                    <h3
                      style={{
                        fontSize: '1.1rem',
                        fontWeight: 600,
                        color: '#4edea3',
                        marginTop: '22px',
                        marginBottom: '8px',
                      }}
                    >
                      {children}
                    </h3>
                  ),
                  p: ({ children }) => (
                    <p style={{ margin: '0 0 14px', color: '#cbd5e1', lineHeight: 1.7 }}>
                      {children}
                    </p>
                  ),
                  ul: ({ children }) => (
                    <ul style={{ paddingLeft: '22px', margin: '0 0 16px', color: '#cbd5e1' }}>
                      {children}
                    </ul>
                  ),
                  ol: ({ children }) => (
                    <ol style={{ paddingLeft: '22px', margin: '0 0 16px', color: '#cbd5e1' }}>
                      {children}
                    </ol>
                  ),
                  li: ({ children }) => (
                    <li style={{ marginBottom: '6px' }}>{children}</li>
                  ),
                  blockquote: ({ children }) => (
                    <blockquote
                      style={{
                        margin: '18px 0',
                        padding: '14px 20px',
                        backgroundColor: 'rgba(128, 131, 255, 0.08)',
                        borderLeft: '4px solid #8083ff',
                        borderRadius: '0 8px 8px 0',
                        color: '#e2e8f0',
                        fontStyle: 'italic',
                      }}
                    >
                      {children}
                    </blockquote>
                  ),
                  code: ({ className, children }) => {
                    const isInline = !className
                    if (isInline) {
                      return (
                        <code
                          style={{
                            backgroundColor: 'rgba(255, 255, 255, 0.08)',
                            color: '#c0c1ff',
                            padding: '2px 6px',
                            borderRadius: '4px',
                            fontFamily: "ui-monospace, 'JetBrains Mono', monospace",
                            fontSize: '0.85em',
                          }}
                        >
                          {children}
                        </code>
                      )
                    }
                    return (
                      <pre
                        style={{
                          backgroundColor: '#0c0f17',
                          border: '1px solid rgba(255, 255, 255, 0.06)',
                          borderRadius: '8px',
                          padding: '16px',
                          overflowX: 'auto',
                          margin: '16px 0',
                          fontFamily: "ui-monospace, 'JetBrains Mono', monospace",
                          fontSize: '0.88rem',
                          color: '#f8fafc',
                        }}
                      >
                        <code>{children}</code>
                      </pre>
                    )
                  },
                }}
              >
                {content}
              </ReactMarkdown>
            ) : (
              <div style={{ textAlign: 'center', padding: '60px 20px', color: '#64748b' }}>
                <Sparkles size={36} style={{ margin: '0 auto 12px', color: '#8083ff' }} />
                <h3 style={{ margin: 0, color: '#f8fafc', fontSize: '1.1rem' }}>Apuntes vacíos</h3>
                <p style={{ margin: '8px 0 18px', fontSize: '0.85rem' }}>
                  Esta clase todavía no tiene contenido escrito en apuntes.md.
                </p>
                <button
                  onClick={() => setMode('edit')}
                  style={{
                    backgroundColor: '#8083ff',
                    border: 'none',
                    color: '#fff',
                    padding: '8px 16px',
                    borderRadius: '8px',
                    fontWeight: 600,
                    cursor: 'pointer',
                  }}
                >
                  Abrir Editor
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
