import { useState } from 'react'
import {
  Folder,
  FileText,
  ChevronDown,
  ChevronRight,
  Pencil,
  Trash2,
  CheckCircle2,
  HelpCircle,
  X,
  AlertTriangle,
  FolderOpen,
  Flame,
} from 'lucide-react'
import {
  type SubjectTree,
  renameClass,
  deleteClass,
} from '../services/api'

interface SidebarProps {
  classes: SubjectTree[]
  selectedSubject: string | null
  selectedClass: string | null
  onSelectClass: (subjectId: string, classId: string) => void
  onRefresh: () => Promise<void>
  onNewProcessing?: () => void
  onOpenPractice?: () => void
}

export function Sidebar({
  classes,
  selectedSubject,
  selectedClass,
  onSelectClass,
  onRefresh,
  onNewProcessing,
  onOpenPractice,
}: SidebarProps) {
  // Estado para acordeones expandidos por defecto
  const [expanded, setExpanded] = useState<Record<string, boolean>>(() => {
    const init: Record<string, boolean> = {}
    classes.forEach((c) => {
      init[c.materia] = true
    })
    return init
  })

  // Modal de renombrar
  const [renamingSubject, setRenamingSubject] = useState<SubjectTree | null>(null)
  const [newNameInput, setNewNameInput] = useState<string>('')
  const [renameLoading, setRenameLoading] = useState<boolean>(false)
  const [renameError, setRenameError] = useState<string | null>(null)

  // Modal de eliminar
  const [deletingSubject, setDeletingSubject] = useState<SubjectTree | null>(null)
  const [deleteLoading, setDeleteLoading] = useState<boolean>(false)
  const [deleteError, setDeleteError] = useState<string | null>(null)

  function toggleAccordion(materiaId: string) {
    setExpanded((prev) => ({
      ...prev,
      [materiaId]: !prev[materiaId],
    }))
  }

  function abrirRenombrar(e: React.MouseEvent, subject: SubjectTree) {
    e.stopPropagation()
    setRenamingSubject(subject)
    setNewNameInput(subject.materia_nombre)
    setRenameError(null)
  }

  function abrirEliminar(e: React.MouseEvent, subject: SubjectTree) {
    e.stopPropagation()
    setDeletingSubject(subject)
    setDeleteError(null)
  }

  async function handleConfirmRename(e: React.FormEvent) {
    e.preventDefault()
    if (!renamingSubject) return

    const trimmed = newNameInput.trim()
    if (!trimmed) {
      setRenameError('El nuevo nombre no puede estar vacío.')
      return
    }

    setRenameLoading(true)
    setRenameError(null)
    try {
      await renameClass(renamingSubject.materia, trimmed)
      setRenamingSubject(null)
      await onRefresh()
    } catch (err) {
      setRenameError(err instanceof Error ? err.message : 'Error al renombrar la asignatura.')
    } finally {
      setRenameLoading(false)
    }
  }

  async function handleConfirmDelete() {
    if (!deletingSubject) return

    setDeleteLoading(true)
    setDeleteError(null)
    try {
      await deleteClass(deletingSubject.materia)
      setDeletingSubject(null)
      await onRefresh()
    } catch (err) {
      setDeleteError(err instanceof Error ? err.message : 'Error al eliminar la asignatura.')
    } finally {
      setDeleteLoading(false)
    }
  }

  return (
    <aside
      style={{
        width: '320px',
        flexShrink: 0,
        backgroundColor: '#121622',
        borderRight: '1px solid rgba(255, 255, 255, 0.06)',
        display: 'flex',
        flexDirection: 'column',
        height: 'calc(100vh - 73px)',
        position: 'sticky',
        top: '73px',
      }}
    >
      {/* Cabecera del Sidebar */}
      <div
        style={{
          padding: '16px 20px',
          borderBottom: '1px solid rgba(255, 255, 255, 0.06)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <FolderOpen size={18} color="#8083ff" />
          <span style={{ fontSize: '0.9rem', fontWeight: 700, color: '#f8fafc' }}>
            Explorador de Clases
          </span>
        </div>
        <span
          style={{
            fontSize: '0.72rem',
            color: '#94a3b8',
            backgroundColor: 'rgba(255, 255, 255, 0.05)',
            padding: '2px 8px',
            borderRadius: '9999px',
          }}
        >
          {classes.length} materias
        </span>
      </div>

      {/* Botones de Acción Rápida: Práctica Diaria e Ingesta */}
      <div
        style={{
          padding: '10px 14px',
          borderBottom: '1px solid rgba(255, 255, 255, 0.04)',
          display: 'flex',
          flexDirection: 'column',
          gap: '8px',
        }}
      >
        {onOpenPractice && (
          <button
            onClick={onOpenPractice}
            style={{
              width: '100%',
              backgroundColor: 'rgba(251, 146, 60, 0.12)',
              border: '1px solid rgba(251, 146, 60, 0.3)',
              color: '#fb923c',
              borderRadius: '8px',
              padding: '8px 12px',
              fontSize: '0.82rem',
              fontWeight: 600,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '6px',
              transition: 'all 0.2s',
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.backgroundColor = 'rgba(251, 146, 60, 0.2)'
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.backgroundColor = 'rgba(251, 146, 60, 0.12)'
            }}
          >
            <Flame size={15} color="#fb923c" />
            <span>🔥 Práctica Diaria (SM-2)</span>
          </button>
        )}

        {onNewProcessing && (
          <button
            onClick={onNewProcessing}
            style={{
              width: '100%',
              backgroundColor: 'rgba(128, 131, 255, 0.12)',
              border: '1px solid rgba(128, 131, 255, 0.28)',
              color: '#c0c1ff',
              borderRadius: '8px',
              padding: '8px 12px',
              fontSize: '0.82rem',
              fontWeight: 600,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '6px',
              transition: 'background-color 0.2s',
            }}
          >
            <span>➕ Nueva Clase / Ingesta</span>
          </button>
        )}
      </div>

      {/* Lista Desplazable de Asignaturas y Temas */}
      <div
        style={{
          flex: 1,
          overflowY: 'auto',
          padding: '12px 10px',
          display: 'flex',
          flexDirection: 'column',
          gap: '8px',
        }}
      >
        {classes.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '32px 16px', color: '#64748b', fontSize: '0.85rem' }}>
            No hay asignaturas creadas en clases/.
          </div>
        ) : (
          classes.map((subject) => {
            const isExpanded = expanded[subject.materia] ?? true

            return (
              <div
                key={subject.materia}
                style={{
                  backgroundColor: '#171b26',
                  borderRadius: '10px',
                  border: '1px solid rgba(255, 255, 255, 0.04)',
                  overflow: 'hidden',
                }}
              >
                {/* Cabecera de Asignatura (Acordeón) */}
                <div
                  onClick={() => toggleAccordion(subject.materia)}
                  style={{
                    padding: '10px 12px',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    cursor: 'pointer',
                    userSelect: 'none',
                    backgroundColor: isExpanded ? 'rgba(255, 255, 255, 0.02)' : 'transparent',
                    transition: 'background-color 0.2s',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', overflow: 'hidden' }}>
                    {isExpanded ? (
                      <ChevronDown size={15} color="#94a3b8" />
                    ) : (
                      <ChevronRight size={15} color="#94a3b8" />
                    )}
                    <Folder size={16} color="#8083ff" style={{ flexShrink: 0 }} />
                    <span
                      style={{
                        fontSize: '0.86rem',
                        fontWeight: 600,
                        color: '#f8fafc',
                        whiteSpace: 'nowrap',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                      }}
                      title={subject.materia_nombre}
                    >
                      {subject.materia_nombre}
                    </span>
                  </div>

                  {/* Acciones de la Materia */}
                  <div style={{ display: 'flex', alignItems: 'center', gap: '4px', flexShrink: 0 }}>
                    <button
                      onClick={(e) => abrirRenombrar(e, subject)}
                      title={`Renombrar ${subject.materia_nombre}`}
                      style={{
                        background: 'transparent',
                        border: 'none',
                        color: '#94a3b8',
                        padding: '4px',
                        borderRadius: '4px',
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                      }}
                      onMouseEnter={(e) => (e.currentTarget.style.color = '#c0c1ff')}
                      onMouseLeave={(e) => (e.currentTarget.style.color = '#94a3b8')}
                    >
                      <Pencil size={13} />
                    </button>
                    <button
                      onClick={(e) => abrirEliminar(e, subject)}
                      title={`Eliminar ${subject.materia_nombre}`}
                      style={{
                        background: 'transparent',
                        border: 'none',
                        color: '#94a3b8',
                        padding: '4px',
                        borderRadius: '4px',
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                      }}
                      onMouseEnter={(e) => (e.currentTarget.style.color = '#f87171')}
                      onMouseLeave={(e) => (e.currentTarget.style.color = '#94a3b8')}
                    >
                      <Trash2 size={13} />
                    </button>
                  </div>
                </div>

                {/* Sublista de Clases dentro del Acordeón */}
                {isExpanded && (
                  <div
                    style={{
                      padding: '4px 8px 8px 16px',
                      display: 'flex',
                      flexDirection: 'column',
                      gap: '4px',
                      borderTop: '1px solid rgba(255, 255, 255, 0.03)',
                    }}
                  >
                    {subject.clases.length === 0 ? (
                      <div style={{ padding: '6px 8px', fontSize: '0.78rem', color: '#64748b', fontStyle: 'italic' }}>
                        Sin temas registrados.
                      </div>
                    ) : (
                      subject.clases.map((c) => {
                        const isSelected =
                          selectedSubject === subject.materia && selectedClass === c.id

                        return (
                          <div
                            key={c.id}
                            onClick={() => onSelectClass(subject.materia, c.id)}
                            style={{
                              padding: '8px 10px',
                              borderRadius: '6px',
                              cursor: 'pointer',
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'space-between',
                              backgroundColor: isSelected
                                ? 'rgba(128, 131, 255, 0.15)'
                                : 'transparent',
                              border: isSelected
                                ? '1px solid rgba(128, 131, 255, 0.3)'
                                : '1px solid transparent',
                              transition: 'all 0.15s',
                            }}
                            onMouseEnter={(e) => {
                              if (!isSelected) {
                                e.currentTarget.style.backgroundColor = 'rgba(255, 255, 255, 0.03)'
                              }
                            }}
                            onMouseLeave={(e) => {
                              if (!isSelected) {
                                e.currentTarget.style.backgroundColor = 'transparent'
                              }
                            }}
                          >
                            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', overflow: 'hidden' }}>
                              <FileText
                                size={14}
                                color={isSelected ? '#8083ff' : '#94a3b8'}
                                style={{ flexShrink: 0 }}
                              />
                              <span
                                style={{
                                  fontSize: '0.8rem',
                                  color: isSelected ? '#f8fafc' : '#cbd5e1',
                                  whiteSpace: 'nowrap',
                                  overflow: 'hidden',
                                  textOverflow: 'ellipsis',
                                }}
                                title={c.nombre}
                              >
                                {c.nombre}
                              </span>
                            </div>

                            {/* Indicadores compactos */}
                            <div style={{ display: 'flex', alignItems: 'center', gap: '4px', flexShrink: 0 }}>
                              {c.tiene_apuntes && (
                                <span title="Apuntes generados">
                                  <CheckCircle2 size={12} color="#4edea3" />
                                </span>
                              )}
                              {c.tiene_preguntas && (
                                <span title="Quiz SM-2 activo">
                                  <HelpCircle size={12} color="#8083ff" />
                                </span>
                              )}
                            </div>
                          </div>
                        )
                      })
                    )}
                  </div>
                )}
              </div>
            )
          })
        )}
      </div>

      {/* MODAL DISCRETO: RENOMBRAR ASIGNATURA */}
      {renamingSubject && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            backgroundColor: 'rgba(0, 0, 0, 0.7)',
            backdropFilter: 'blur(4px)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 100,
            padding: '16px',
          }}
        >
          <div
            style={{
              backgroundColor: '#171b26',
              border: '1px solid rgba(128, 131, 255, 0.3)',
              borderRadius: '16px',
              padding: '24px',
              maxWidth: '420px',
              width: '100%',
              boxShadow: '0 20px 40px rgba(0, 0, 0, 0.5)',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Pencil size={18} color="#8083ff" />
                <h3 style={{ margin: 0, fontSize: '1.1rem', fontWeight: 600, color: '#f8fafc' }}>
                  Renombrar Asignatura
                </h3>
              </div>
              <button
                onClick={() => setRenamingSubject(null)}
                style={{ background: 'transparent', border: 'none', color: '#94a3b8', cursor: 'pointer' }}
              >
                <X size={18} />
              </button>
            </div>

            <form onSubmit={handleConfirmRename}>
              <label style={{ display: 'block', fontSize: '0.82rem', color: '#94a3b8', marginBottom: '6px' }}>
                Nuevo nombre para la carpeta:
              </label>
              <input
                type="text"
                value={newNameInput}
                onChange={(e) => setNewNameInput(e.target.value)}
                autoFocus
                disabled={renameLoading}
                style={{
                  width: '100%',
                  padding: '10px 14px',
                  backgroundColor: '#0f131d',
                  border: '1px solid rgba(255, 255, 255, 0.1)',
                  borderRadius: '8px',
                  color: '#f8fafc',
                  fontSize: '0.9rem',
                  outline: 'none',
                  boxSizing: 'border-box',
                  marginBottom: '16px',
                }}
              />

              {renameError && (
                <div style={{ color: '#f87171', fontSize: '0.8rem', marginBottom: '14px' }}>
                  {renameError}
                </div>
              )}

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
                <button
                  type="button"
                  onClick={() => setRenamingSubject(null)}
                  disabled={renameLoading}
                  style={{
                    backgroundColor: 'transparent',
                    border: '1px solid rgba(255, 255, 255, 0.1)',
                    color: '#94a3b8',
                    padding: '8px 16px',
                    borderRadius: '8px',
                    fontSize: '0.85rem',
                    cursor: 'pointer',
                  }}
                >
                  Cancelar
                </button>
                <button
                  type="submit"
                  disabled={renameLoading}
                  style={{
                    backgroundColor: '#8083ff',
                    border: 'none',
                    color: '#fff',
                    padding: '8px 18px',
                    borderRadius: '8px',
                    fontSize: '0.85rem',
                    fontWeight: 600,
                    cursor: 'pointer',
                  }}
                >
                  {renameLoading ? 'Guardando...' : 'Guardar Nombre'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* MODAL DISCRETO: CONFIRMAR ELIMINACIÓN */}
      {deletingSubject && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            backgroundColor: 'rgba(0, 0, 0, 0.7)',
            backdropFilter: 'blur(4px)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 100,
            padding: '16px',
          }}
        >
          <div
            style={{
              backgroundColor: '#171b26',
              border: '1px solid rgba(239, 68, 68, 0.3)',
              borderRadius: '16px',
              padding: '24px',
              maxWidth: '440px',
              width: '100%',
              boxShadow: '0 20px 40px rgba(0, 0, 0, 0.5)',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '14px' }}>
              <div
                style={{
                  width: '36px',
                  height: '36px',
                  borderRadius: '8px',
                  backgroundColor: 'rgba(239, 68, 68, 0.15)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: '#ef4444',
                }}
              >
                <AlertTriangle size={20} />
              </div>
              <div>
                <h3 style={{ margin: 0, fontSize: '1.1rem', fontWeight: 700, color: '#f8fafc' }}>
                  ¿Eliminar asignatura?
                </h3>
                <span style={{ fontSize: '0.78rem', color: '#94a3b8' }}>
                  {deletingSubject.materia_nombre}
                </span>
              </div>
            </div>

            <p style={{ margin: '0 0 16px', fontSize: '0.86rem', color: '#cbd5e1', lineHeight: 1.4 }}>
              Esta acción eliminará de forma permanente la carpeta{' '}
              <code style={{ color: '#fca5a5', backgroundColor: '#0f131d', padding: '2px 6px', borderRadius: '4px' }}>
                clases/{deletingSubject.materia}
              </code>{' '}
              junto con todos sus apuntes, audios y preguntas ({deletingSubject.total_clases} clases).
            </p>

            {deleteError && (
              <div style={{ color: '#f87171', fontSize: '0.8rem', marginBottom: '14px' }}>
                {deleteError}
              </div>
            )}

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
              <button
                type="button"
                onClick={() => setDeletingSubject(null)}
                disabled={deleteLoading}
                style={{
                  backgroundColor: 'transparent',
                  border: '1px solid rgba(255, 255, 255, 0.1)',
                  color: '#94a3b8',
                  padding: '8px 16px',
                  borderRadius: '8px',
                  fontSize: '0.85rem',
                  cursor: 'pointer',
                }}
              >
                Cancelar
              </button>
              <button
                type="button"
                onClick={handleConfirmDelete}
                disabled={deleteLoading}
                style={{
                  backgroundColor: '#ef4444',
                  border: 'none',
                  color: '#fff',
                  padding: '8px 18px',
                  borderRadius: '8px',
                  fontSize: '0.85rem',
                  fontWeight: 600,
                  cursor: 'pointer',
                }}
              >
                {deleteLoading ? 'Eliminando...' : 'Eliminar Permanentemente'}
              </button>
            </div>
          </div>
        </div>
      )}
    </aside>
  )
}
