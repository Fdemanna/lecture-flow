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
  Sparkles,
  Plus,
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
  isOpenMobile?: boolean
  onCloseMobile?: () => void
}

export function Sidebar({
  classes,
  selectedSubject,
  selectedClass,
  onSelectClass,
  onRefresh,
  onNewProcessing,
  onOpenPractice,
  isOpenMobile = false,
  onCloseMobile,
}: SidebarProps) {
  // Estado para acordeones expandidos
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
    <>
      {/* Backdrop para pantallas móviles y tablets (< lg) */}
      {isOpenMobile && (
        <div
          onClick={onCloseMobile}
          className="fixed inset-0 bg-black/60 backdrop-blur-xs z-40 lg:hidden"
          aria-hidden="true"
        />
      )}

      <aside
        className={`fixed lg:sticky top-0 lg:top-16 inset-y-0 left-0 z-40 w-[280px] shrink-0 bg-[#0f131d] border-r border-white/6 flex flex-col h-full lg:h-[calc(100vh-4rem)] max-h-full lg:max-h-[calc(100vh-4rem)] box-border overflow-hidden transition-transform duration-300 ease-in-out lg:translate-x-0 ${
          isOpenMobile ? 'translate-x-0 shadow-2xl' : '-translate-x-full lg:translate-x-0'
        }`}
      >
        {/* Cabecera del explorador */}
        <div className="px-5 py-4 border-b border-white/6 flex items-center justify-between">
          <div className="flex items-center gap-2 text-slate-200">
            <FolderOpen size={16} className="text-[#4f6bff]" />
            <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-400 m-0 text-balance">
              Explorador de clases
            </h2>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-[11px] font-mono tabular-nums text-slate-500 bg-white/5 px-2 py-0.5 rounded-full border border-white/6">
              {classes.length} {classes.length === 1 ? 'materia' : ' materias'}
            </span>
            {onCloseMobile && (
              <button
                onClick={onCloseMobile}
                className="lg:hidden p-1 text-slate-400 hover:text-white rounded transition-colors"
                aria-label="Cerrar panel de clases"
              >
                <X size={16} />
              </button>
            )}
          </div>
        </div>

        {/* Botones de acción rápida: Práctica e Ingesta */}
        <div className="p-3 border-b border-white/5 flex flex-col gap-2">
          {onOpenPractice && (
            <button
              onClick={() => {
                onOpenPractice()
                if (onCloseMobile) onCloseMobile()
              }}
              className="w-full flex items-center justify-center gap-2 px-3 py-2 text-xs font-medium rounded-lg bg-[#e5a158]/10 border border-[#e5a158]/25 text-[#e5a158] hover:bg-[#e5a158]/20 transition-colors cursor-pointer"
            >
              <Sparkles size={14} />
              <span>Sesión de práctica diaria</span>
            </button>
          )}

          {onNewProcessing && (
            <button
              onClick={() => {
                onNewProcessing()
                if (onCloseMobile) onCloseMobile()
              }}
              className="w-full flex items-center justify-center gap-2 px-3 py-2 text-xs font-medium rounded-lg bg-white/5 border border-white/8 text-slate-300 hover:bg-white/10 hover:text-white transition-colors cursor-pointer"
            >
              <Plus size={14} className="text-[#4f6bff]" />
              <span>Nueva clase o ingesta</span>
            </button>
          )}
        </div>

      {/* Lista desplazable de asignaturas y temas */}
      <div className="sidebar-scrollable flex-1 min-h-0 overflow-y-auto p-2.5 flex flex-col gap-1.5">
        {classes.length === 0 ? (
          <div className="text-center py-12 px-4 text-slate-500 text-xs">
            No se han registrado asignaturas en el directorio clases/.
          </div>
        ) : (
          classes.map((subject) => {
            const isExpanded = expanded[subject.materia] ?? true

            return (
              <div
                key={subject.materia}
                className="bg-[#141824] rounded-lg border border-white/5 overflow-hidden transition-colors"
              >
                {/* Cabecera de materia (acordeón) */}
                <div
                  className={`px-3 py-2.5 flex items-center justify-between gap-2 transition-colors ${
                    isExpanded ? 'bg-white/[0.02]' : 'hover:bg-white/[0.02]'
                  }`}
                >
                  <button
                    type="button"
                    onClick={() => toggleAccordion(subject.materia)}
                    aria-expanded={isExpanded}
                    aria-label={`${subject.materia_nombre}, ${subject.total_clases} clases. ${isExpanded ? 'Plegar' : 'Desplegar'}`}
                    className="flex items-center gap-2 min-w-0 flex-1 overflow-hidden text-left cursor-pointer focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[#4f6bff]"
                  >
                    {isExpanded ? (
                      <ChevronDown size={14} className="text-slate-500 shrink-0" aria-hidden="true" />
                    ) : (
                      <ChevronRight size={14} className="text-slate-500 shrink-0" aria-hidden="true" />
                    )}
                    <Folder size={15} className="text-[#4f6bff] shrink-0" aria-hidden="true" />
                    <span
                      className="text-xs font-medium text-slate-200 truncate min-w-0"
                      title={subject.materia_nombre}
                    >
                      {subject.materia_nombre}
                    </span>
                  </button>

                  {/* Acciones de gestión para la materia */}
                  <div className="flex items-center gap-1 shrink-0">
                    <button
                      type="button"
                      onClick={(e) => abrirRenombrar(e, subject)}
                      title={`Renombrar ${subject.materia_nombre}`}
                      aria-label={`Renombrar asignatura ${subject.materia_nombre}`}
                      className="p-1 text-slate-500 hover:text-slate-300 rounded transition-colors cursor-pointer"
                    >
                      <Pencil size={12} aria-hidden="true" />
                    </button>
                    <button
                      type="button"
                      onClick={(e) => abrirEliminar(e, subject)}
                      title={`Eliminar ${subject.materia_nombre}`}
                      aria-label={`Eliminar asignatura ${subject.materia_nombre}`}
                      className="p-1 text-slate-500 hover:text-red-400 rounded transition-colors cursor-pointer"
                    >
                      <Trash2 size={12} aria-hidden="true" />
                    </button>
                  </div>
                </div>

                {/* Sublista de clases */}
                {isExpanded && (
                  <div className="px-2 pt-1 pb-2 flex flex-col gap-1 border-t border-white/[0.03]">
                    {subject.clases.length === 0 ? (
                      <div className="px-3 py-1.5 text-[11px] text-slate-500 italic">
                        Sin temas registrados.
                      </div>
                    ) : (
                      subject.clases.map((c) => {
                        const isSelected =
                          selectedSubject === subject.materia && selectedClass === c.id

                        return (
                          <button
                            type="button"
                            key={c.id}
                            onClick={() => {
                              onSelectClass(subject.materia, c.id)
                              if (onCloseMobile) onCloseMobile()
                            }}
                            className={`w-full text-left px-2.5 py-1.5 rounded-md cursor-pointer flex items-center justify-between gap-2 transition-colors ${
                              isSelected
                                ? 'bg-[#4f6bff]/15 border border-[#4f6bff]/30 text-white'
                                : 'text-slate-400 hover:bg-white/5 hover:text-slate-200 border border-transparent'
                            }`}
                          >
                            <div className="flex items-center gap-2 min-w-0 flex-1 overflow-hidden">
                              <FileText
                                size={13}
                                aria-hidden="true"
                                className={isSelected ? 'text-[#4f6bff] shrink-0' : 'text-slate-500 shrink-0'}
                              />
                              <span className="text-xs truncate min-w-0" title={c.nombre}>
                                {c.nombre}
                              </span>
                            </div>

                            {/* Indicadores de artefactos generados */}
                            <div className="flex items-center gap-1.5 shrink-0">
                              {c.tiene_apuntes && (
                                <span title="Apuntes generados">
                                  <CheckCircle2 size={12} className="text-[#34d399]" aria-hidden="true" />
                                </span>
                              )}
                              {c.tiene_preguntas && (
                                <span title="Banco de preguntas SM-2 disponible">
                                  <HelpCircle size={12} className="text-[#4f6bff]" aria-hidden="true" />
                                </span>
                              )}
                            </div>
                          </button>
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

      {/* Modal: Renombrar asignatura */}
      {renamingSubject && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="bg-[#141824] border border-[#4f6bff]/30 rounded-xl p-6 max-w-sm w-full shadow-2xl">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2 text-slate-100">
                <Pencil size={16} className="text-[#4f6bff]" />
                <h3 className="text-sm font-semibold m-0">Renombrar asignatura</h3>
              </div>
              <button
                onClick={() => setRenamingSubject(null)}
                className="text-slate-500 hover:text-slate-300 cursor-pointer"
              >
                <X size={16} />
              </button>
            </div>

            <form onSubmit={handleConfirmRename}>
              <label htmlFor="rename-subject-input" className="block text-xs text-slate-400 mb-2 cursor-pointer">
                Nuevo nombre para la carpeta en disco:
              </label>
              <input
                id="rename-subject-input"
                name="subjectName"
                type="text"
                autoComplete="off"
                spellCheck={false}
                value={newNameInput}
                onChange={(e) => setNewNameInput(e.target.value)}
                autoFocus
                disabled={renameLoading}
                className="w-full px-3 py-2 bg-[#0b0e14] border border-white/10 rounded-lg text-slate-100 text-xs outline-none focus:border-[#4f6bff] mb-3 font-mono"
              />

              {renameError && (
                <div className="text-red-400 text-xs mb-3">{renameError}</div>
              )}

              <div className="flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setRenamingSubject(null)}
                  disabled={renameLoading}
                  className="px-3 py-1.5 text-xs text-slate-400 hover:text-slate-200 border border-white/10 rounded-lg cursor-pointer"
                >
                  Cancelar
                </button>
                <button
                  type="submit"
                  disabled={renameLoading}
                  className="px-3.5 py-1.5 text-xs font-medium bg-[#4f6bff] text-white hover:bg-[#637eff] rounded-lg cursor-pointer transition-colors"
                >
                  {renameLoading ? 'Guardando…' : 'Guardar nombre'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal: Confirmar eliminación */}
      {deletingSubject && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="bg-[#141824] border border-red-500/30 rounded-xl p-6 max-w-md w-full shadow-2xl">
            <div className="flex items-center gap-3 mb-3">
              <div className="w-8 h-8 rounded-lg bg-red-500/10 flex items-center justify-center text-red-400 shrink-0">
                <AlertTriangle size={18} />
              </div>
              <div>
                <h3 className="text-sm font-semibold text-slate-100 m-0 text-balance">
                  ¿Eliminar asignatura de forma permanente?
                </h3>
                <span className="text-xs text-slate-400 font-mono">
                  {deletingSubject.materia_nombre}
                </span>
              </div>
            </div>

            <p className="text-xs text-slate-300 leading-relaxed mb-4 text-pretty">
              Esta acción eliminará del disco la carpeta{' '}
              <code className="text-red-300 bg-[#0b0e14] px-1.5 py-0.5 rounded border border-red-900/40">
                clases/{deletingSubject.materia}
              </code>{' '}
              junto con todos sus apuntes, grabaciones y preguntas ({deletingSubject.total_clases} clases).
            </p>

            {deleteError && (
              <div className="text-red-400 text-xs mb-3">{deleteError}</div>
            )}

            <div className="flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setDeletingSubject(null)}
                disabled={deleteLoading}
                className="px-3 py-1.5 text-xs text-slate-400 hover:text-slate-200 border border-white/10 rounded-lg cursor-pointer"
              >
                Cancelar
              </button>
              <button
                type="button"
                onClick={handleConfirmDelete}
                disabled={deleteLoading}
                className="px-3.5 py-1.5 text-xs font-medium bg-red-600 text-white hover:bg-red-500 rounded-lg cursor-pointer transition-colors"
              >
                {deleteLoading ? 'Eliminando…' : 'Eliminar carpeta'}
              </button>
            </div>
          </div>
        </div>
      )}
    </aside>
  </>
  )
}
