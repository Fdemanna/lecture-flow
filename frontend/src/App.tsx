import { useEffect, useState } from 'react'
import {
  Flame,
  Zap,
  BookOpen,
  Folder,
  FileText,
  Sparkles,
  RefreshCw,
  GraduationCap,
  AlertCircle,
  CheckCircle2,
  HelpCircle,
  ArrowRight,
  Menu,
} from 'lucide-react'
import {
  getHealth,
  getClasses,
  getStudyStats,
  type HealthStatus,
  type SubjectTree,
  type StudyStats,
} from './services/api'
import { Sidebar } from './components/Sidebar'
import { NotesEditor } from './components/NotesEditor'
import { ProcessingPanel } from './components/ProcessingPanel'
import { PracticeSession } from './components/PracticeSession'

export default function App() {
  const [health, setHealth] = useState<HealthStatus | null>(null)
  const [classes, setClasses] = useState<SubjectTree[]>([])
  const [stats, setStats] = useState<StudyStats | null>(null)
  const [loading, setLoading] = useState<boolean>(true)
  const [error, setError] = useState<string | null>(null)
  const [refreshing, setRefreshing] = useState<boolean>(false)

  // Estado para panel de procesamiento / ingesta
  const [showProcessingPanel, setShowProcessingPanel] = useState<boolean>(false)

  // Estado para sesion interactiva de Active Recall (SM-2 Lite)
  const [showPracticeSession, setShowPracticeSession] = useState<boolean>(false)

  // Estado para drawer responsivo del explorador de clases en movil/tablet
  const [isMobileSidebarOpen, setIsMobileSidebarOpen] = useState<boolean>(false)

  // Seleccion de clase activa
  const [selectedSubject, setSelectedSubject] = useState<string | null>(null)
  const [selectedClass, setSelectedClass] = useState<string | null>(null)

  async function cargarDatos(esRecarga: boolean = false) {
    if (esRecarga) {
      setRefreshing(true)
    } else {
      setLoading(true)
    }
    setError(null)

    try {
      const [resHealth, resClasses, resStats] = await Promise.all([
        getHealth().catch(() => null),
        getClasses().catch(() => []),
        getStudyStats().catch(() => null),
      ])

      setHealth(resHealth)
      setClasses(resClasses)
      setStats(resStats)

      if (!resHealth) {
        setError('No se pudo conectar con el backend de LectureFlow (FastAPI en :8000).')
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error desconocido al cargar datos')
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }

  useEffect(() => {
    cargarDatos()
  }, [])

  function handleSelectClass(materiaId: string, classId: string) {
    setSelectedSubject(materiaId)
    setSelectedClass(classId)
  }

  const racha = stats?.racha_actual ?? 0
  const xp = stats?.xp_total ?? 0
  const totalPreguntas = stats?.total_preguntas_registradas ?? 0
  const totalClases = classes.reduce((acc, curr) => acc + curr.total_clases, 0)

  // Materia seleccionada actualmente
  const activeSubjectData = classes.find((c) => c.materia === selectedSubject)
  const activeClassData = activeSubjectData?.clases.find((c) => c.id === selectedClass)

  return (
    <div className="min-h-screen bg-[#0b0e14] text-slate-100 flex flex-col font-sans">
      {/* Top Navigation Bar pegado a los extremos */}
      <header className="sticky top-0 z-50 border-b border-white/5 bg-[#10141f]/90 backdrop-blur w-full h-16 flex items-center">
        <div className="w-full px-4 sm:px-6 flex items-center justify-between gap-3 sm:gap-4">
          {/* Botón menú móvil y Branding */}
          <div className="flex items-center gap-2 sm:gap-3 min-w-0">
            <button
              onClick={() => setIsMobileSidebarOpen((prev) => !prev)}
              className="lg:hidden p-1.5 sm:p-2 rounded-lg bg-white/5 border border-white/10 text-slate-300 hover:text-white transition-colors shrink-0 cursor-pointer"
              aria-label={isMobileSidebarOpen ? 'Cerrar panel de clases' : 'Abrir explorador de clases'}
            >
              <Menu size={18} />
            </button>

            <div className="w-8 h-8 sm:w-9 sm:h-9 rounded-xl bg-indigo-500/15 border border-indigo-500/25 flex items-center justify-center text-indigo-400 shrink-0">
              <GraduationCap size={20} className="sm:hidden" />
              <GraduationCap size={22} className="hidden sm:block" />
            </div>
            <div className="min-w-0">
              <div className="flex items-center gap-1.5 sm:gap-2">
                <span className="text-sm sm:text-base font-bold tracking-tight text-white shrink-0">
                  LectureFlow
                </span>
                <span className="hidden xs:inline-block text-[10px] sm:text-[11px] px-1.5 sm:px-2 py-0.5 rounded-full bg-indigo-500/15 text-indigo-300 border border-indigo-500/25 font-semibold shrink-0">
                  DAW Suite
                </span>
              </div>
              <p className="text-[11px] sm:text-xs text-slate-400 truncate hidden xs:block">
                Asistente de estudio y sintesis academica
              </p>
            </div>
          </div>

          {/* Estado de Salud y Controles */}
          <div className="flex items-center gap-1.5 sm:gap-3 shrink-0">
            {/* Badge de Conexion Backend */}
            <div
              className={`hidden md:inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-medium border ${
                health
                  ? 'bg-emerald-500/10 border-emerald-500/25 text-emerald-400'
                  : 'bg-rose-500/10 border-rose-500/25 text-rose-400'
              }`}
            >
              <span
                className={`w-2 h-2 rounded-full ${
                  health ? 'bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.6)]' : 'bg-rose-500'
                }`}
              />
              <span>{health ? 'Backend en linea (:8000)' : 'Backend desconectado'}</span>
            </div>

            {/* Lockfile en progreso si existe */}
            {health?.procesando && (
              <div className="hidden sm:inline-flex items-center gap-1.5 px-2.5 sm:px-3 py-1 rounded-full bg-amber-500/15 border border-amber-500/30 text-amber-300 text-xs truncate max-w-[180px]">
                <Sparkles size={13} className="shrink-0" />
                <span className="truncate">{health.clase_en_proceso}</span>
              </div>
            )}

            {/* Boton Practica Diaria */}
            <button
              onClick={() => setShowPracticeSession((prev) => !prev)}
              className={`inline-flex items-center gap-1.5 px-2.5 sm:px-3.5 py-1.5 rounded-lg text-xs font-medium border transition-colors shrink-0 cursor-pointer ${
                showPracticeSession
                  ? 'bg-amber-500/25 border-amber-500/40 text-amber-300'
                  : 'bg-amber-500/15 border-amber-500/30 text-amber-400 hover:bg-amber-500/20'
              }`}
              aria-label={showPracticeSession ? 'Cerrar practica' : 'Practica diaria (SM-2)'}
            >
              <Flame size={14} className="shrink-0" />
              <span className="hidden sm:inline">{showPracticeSession ? 'Cerrar practica' : 'Practica diaria (SM-2)'}</span>
              <span className="sm:hidden">{showPracticeSession ? 'Cerrar' : 'Practica'}</span>
            </button>

            {/* Boton Nuevo Procesamiento */}
            <button
              onClick={() => setShowProcessingPanel((prev) => !prev)}
              className={`inline-flex items-center gap-1.5 px-2.5 sm:px-3.5 py-1.5 rounded-lg text-xs font-medium transition-colors shrink-0 cursor-pointer ${
                showProcessingPanel
                  ? 'bg-indigo-500/20 border border-indigo-500/40 text-indigo-300'
                  : 'bg-indigo-600 hover:bg-indigo-500 text-white shadow-md shadow-indigo-600/20'
              }`}
              aria-label={showProcessingPanel ? 'Ocultar ingesta' : 'Procesar clase'}
            >
              <Sparkles size={14} className="shrink-0" />
              <span className="hidden sm:inline">{showProcessingPanel ? 'Ocultar ingesta' : 'Procesar clase'}</span>
              <span className="sm:hidden">{showProcessingPanel ? 'Ocultar' : 'Procesar'}</span>
            </button>

            {/* Boton Refrescar */}
            <button
              onClick={() => cargarDatos(true)}
              disabled={refreshing}
              title="Recargar datos del servidor"
              aria-label="Recargar datos del servidor"
              className="p-1.5 sm:p-2 rounded-lg bg-white/5 border border-white/10 text-slate-400 hover:text-slate-200 transition-colors shrink-0 cursor-pointer"
            >
              <RefreshCw size={14} className={`sm:hidden ${refreshing ? 'animate-spin' : ''}`} />
              <RefreshCw size={15} className={`hidden sm:block ${refreshing ? 'animate-spin' : ''}`} />
            </button>
          </div>
        </div>
      </header>

      {/* Layout Principal: Sidebar pegado al borde izquierdo absoluto + Contenido Central fluido */}
      <div className="w-full flex-1 flex flex-col lg:grid lg:grid-cols-[280px_1fr] relative">
        {/* Sidebar con Acordeon pegado al tope izquierdo */}
        <Sidebar
          classes={classes}
          selectedSubject={selectedSubject}
          selectedClass={selectedClass}
          onSelectClass={handleSelectClass}
          onRefresh={() => cargarDatos(true)}
          onNewProcessing={() => setShowProcessingPanel(true)}
          onOpenPractice={() => setShowPracticeSession(true)}
          isOpenMobile={isMobileSidebarOpen}
          onCloseMobile={() => setIsMobileSidebarOpen(false)}
        />

        {/* Area Central de Contenido Adaptable */}
        <main className="min-w-0 p-6 lg:p-8 overflow-y-auto w-full">
          {/* Modulo de Practica Interactiva (Active Recall SM-2 Lite) */}
          {showPracticeSession && (
            <div className="mb-8">
              <PracticeSession
                onSessionCompleted={() => {
                  cargarDatos(true)
                }}
                onClose={() => setShowPracticeSession(false)}
              />
            </div>
          )}

          {/* Panel de Ingesta y Procesamiento SSE */}
          {showProcessingPanel && (
            <ProcessingPanel
              onJobFinished={() => {
                cargarDatos(true)
              }}
              onClose={() => setShowProcessingPanel(false)}
            />
          )}

          {/* Banner de Error si el backend esta caido */}
          {error && (
            <div role="alert" aria-live="assertive" className="mb-6 p-4 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 flex items-center justify-between gap-3">
              <div className="flex items-center gap-2.5">
                <AlertCircle size={18} className="text-rose-400 shrink-0" aria-hidden="true" />
                <span className="text-sm">{error}</span>
              </div>
              <button
                onClick={() => cargarDatos()}
                className="px-3 py-1.5 rounded-lg bg-rose-600 hover:bg-rose-500 text-white text-xs font-semibold transition-colors shrink-0"
              >
                Reintentar
              </button>
            </div>
          )}

          {/* Visor y Editor de Apuntes si hay clase seleccionada */}
          {activeClassData && activeSubjectData && (
            <div className="mb-8">
              <NotesEditor
                subject={activeSubjectData.materia}
                subjectName={activeSubjectData.materia_nombre}
                className={activeClassData.id}
                classReadableName={activeClassData.nombre}
                hasTranscription={Boolean(activeClassData.tiene_transcripcion)}
                onNotesGenerated={() => {
                  cargarDatos(true)
                }}
                onClose={() => {
                  setSelectedSubject(null)
                  setSelectedClass(null)
                }}
              />
            </div>
          )}

          {/* 1. Widgets de Estadisticas y Gamificacion */}
          <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-6 mb-8">
            {/* Card Racha */}
            <button
              type="button"
              onClick={() => setShowPracticeSession(true)}
              title="Haz clic para iniciar la practica diaria"
              aria-label={`Racha diaria: ${racha} ${racha === 1 ? 'día' : 'días'}. Haz clic para iniciar la práctica`}
              className="text-left bg-[#141824] border border-amber-500/20 hover:border-amber-500/40 rounded-2xl p-5 flex items-center gap-4 cursor-pointer transition-colors hover:bg-[#181d2c]"
            >
              <div className="w-12 h-12 rounded-xl bg-amber-500/15 flex items-center justify-center text-amber-400 shrink-0">
                <Flame size={24} aria-hidden="true" />
              </div>
              <div>
                <div className="text-xs text-slate-400 font-medium">Racha diaria</div>
                <div className="text-2xl font-bold text-amber-400 leading-tight tabular-nums">
                  {racha} {racha === 1 ? 'dia' : 'dias'}
                </div>
                <div className="text-[11px] text-slate-500 mt-0.5">
                  {stats?.ultimo_dia_estudiado ? `Ultimo: ${stats.ultimo_dia_estudiado}` : 'Sin repasos previos'}
                </div>
              </div>
            </button>

            {/* Card XP */}
            <button
              type="button"
              onClick={() => setShowPracticeSession(true)}
              title="Haz clic para iniciar la practica diaria"
              aria-label={`Experiencia: ${xp} XP. Haz clic para iniciar la práctica`}
              className="text-left bg-[#141824] border border-emerald-500/20 hover:border-emerald-500/40 rounded-2xl p-5 flex items-center gap-4 cursor-pointer transition-colors hover:bg-[#181d2c]"
            >
              <div className="w-12 h-12 rounded-xl bg-emerald-500/15 flex items-center justify-center text-emerald-400 shrink-0">
                <Zap size={24} aria-hidden="true" />
              </div>
              <div>
                <div className="text-xs text-slate-400 font-medium">Experiencia</div>
                <div className="text-2xl font-bold text-emerald-400 leading-tight tabular-nums">
                  {xp} XP
                </div>
                <div className="text-[11px] text-slate-500 mt-0.5">
                  +10 XP por acierto
                </div>
              </div>
            </button>

            {/* Card SM-2 Preguntas */}
            <button
              type="button"
              onClick={() => setShowPracticeSession(true)}
              title="Haz clic para iniciar la practica diaria"
              aria-label={`Preguntas SM-2: ${totalPreguntas} items. Haz clic para iniciar la práctica`}
              className="text-left bg-[#141824] border border-indigo-500/20 hover:border-indigo-500/40 rounded-2xl p-5 flex items-center gap-4 cursor-pointer transition-colors hover:bg-[#181d2c]"
            >
              <div className="w-12 h-12 rounded-xl bg-indigo-500/15 flex items-center justify-center text-indigo-400 shrink-0">
                <Sparkles size={24} aria-hidden="true" />
              </div>
              <div>
                <div className="text-xs text-slate-400 font-medium">Preguntas SM-2</div>
                <div className="text-2xl font-bold text-indigo-300 leading-tight tabular-nums">
                  {totalPreguntas} items
                </div>
                <div className="text-[11px] text-slate-500 mt-0.5">
                  Repeticion espaciada
                </div>
              </div>
            </button>

            {/* Card Clases */}
            <div className="bg-[#141824] border border-white/5 rounded-2xl p-5 flex items-center gap-4">
              <div className="w-12 h-12 rounded-xl bg-white/5 flex items-center justify-center text-slate-200 shrink-0">
                <BookOpen size={24} />
              </div>
              <div>
                <div className="text-xs text-slate-400 font-medium">Total de clases</div>
                <div className="text-2xl font-bold text-slate-100 leading-tight tabular-nums">
                  {totalClases}
                </div>
                <div className="text-[11px] text-slate-500 mt-0.5">
                  En {classes.length} asignaturas
                </div>
              </div>
            </div>
          </div>

          {/* 2. Seccion Principal: Catalogo de Asignaturas */}
          <section>
            <div className="flex items-center justify-between mb-5">
              <div>
                <h2 className="text-lg font-bold text-slate-100 text-balance">
                  Catalogo general de asignaturas
                </h2>
                <p className="text-xs text-slate-400 mt-0.5 text-pretty">
                  Usa el menu lateral para explorar temas o administrar materias existentes (renombrar o eliminar).
                </p>
              </div>
            </div>

            {loading ? (
              <div className="text-center py-12 text-slate-400 bg-[#141824] rounded-2xl border border-white/5">
                <RefreshCw size={22} className="animate-spin mx-auto mb-3" />
                <p className="text-xs">Cargando catalogo desde FastAPI…</p>
              </div>
            ) : classes.length === 0 ? (
              <div className="text-center py-12 px-6 bg-[#141824] rounded-2xl border border-white/5 text-slate-400">
                <Folder size={36} className="mx-auto mb-3 text-slate-500" />
                <h3 className="text-sm font-semibold text-slate-200 text-balance">No hay asignaturas registradas</h3>
                <p className="text-xs mt-1 text-pretty">
                  Procesa una nueva clase desde el panel superior para comenzar.
                </p>
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {classes.map((subject) => (
                  <div
                    key={subject.materia}
                    className="bg-[#141824] rounded-2xl border border-white/5 p-6 flex flex-col justify-between h-full hover:border-white/10 transition-colors shadow-sm"
                  >
                    {/* Encabezado de la Materia */}
                    <div className="flex items-center justify-between border-b border-white/5 pb-4 gap-3">
                      <div className="flex items-center gap-3 min-w-0 flex-1">
                        <div className="w-10 h-10 rounded-xl bg-indigo-500/10 text-indigo-400 flex items-center justify-center shrink-0">
                          <Folder size={20} />
                        </div>
                        <div className="min-w-0 flex-1">
                          <h3 className="text-base font-bold text-slate-100 truncate text-pretty" title={subject.materia_nombre}>
                            {subject.materia_nombre}
                          </h3>
                          <span className="text-xs text-slate-500 truncate block mt-0.5" title={`Carpeta: ${subject.materia}`}>
                            Carpeta: {subject.materia}
                          </span>
                        </div>
                      </div>
                      <span className="text-xs font-medium bg-white/5 px-2.5 py-1 rounded-full text-indigo-300 shrink-0 tabular-nums">
                        {subject.total_clases} {subject.total_clases === 1 ? 'clase' : 'clases'}
                      </span>
                    </div>

                    {/* Lista de Clases */}
                    <div className="flex flex-col gap-2.5 mt-4">
                      {subject.clases.length === 0 ? (
                        <div className="text-xs text-slate-500 italic py-2">
                          Sin temas procesados aun.
                        </div>
                      ) : (
                        subject.clases.map((clase) => (
                          <button
                            type="button"
                            key={clase.id}
                            onClick={() => handleSelectClass(subject.materia, clase.id)}
                            className={`w-full text-left rounded-xl p-3.5 flex flex-col gap-2 cursor-pointer transition-colors border ${
                              selectedSubject === subject.materia && selectedClass === clase.id
                                ? 'bg-[#181d2e] border-indigo-500/40'
                                : 'bg-[#0f121d] border-white/5 hover:border-white/10 hover:bg-[#131625]'
                            }`}
                          >
                            <div className="flex items-center justify-between gap-2">
                              <div className="flex items-center gap-2.5 min-w-0 flex-1 overflow-hidden">
                                <FileText size={16} className="text-slate-400 shrink-0" aria-hidden="true" />
                                <span className="text-sm font-medium text-slate-200 truncate min-w-0" title={clase.nombre}>
                                  {clase.nombre}
                                </span>
                              </div>
                              <ArrowRight size={14} className="text-slate-500 shrink-0" aria-hidden="true" />
                            </div>

                            {/* Etiquetas */}
                            <div className="flex flex-wrap gap-1.5 mt-1">
                              {clase.tiene_apuntes && (
                                <span className="inline-flex items-center gap-1 text-[10px] px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 font-medium">
                                  <CheckCircle2 size={10} aria-hidden="true" />
                                  Apuntes
                                </span>
                              )}
                              {clase.tiene_preguntas && (
                                <span className="inline-flex items-center gap-1 text-[10px] px-2 py-0.5 rounded bg-indigo-500/10 text-indigo-300 font-medium">
                                  <HelpCircle size={10} aria-hidden="true" />
                                  Quiz
                                </span>
                              )}
                            </div>
                          </button>
                        ))
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </section>
        </main>
      </div>
    </div>
  )
}
