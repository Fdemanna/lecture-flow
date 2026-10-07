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

  // Estado para sesión interactiva de Active Recall (SM-2 Lite)
  const [showPracticeSession, setShowPracticeSession] = useState<boolean>(false)

  // Selección de clase activa
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
    <div style={{ minHeight: '100vh', backgroundColor: '#0f131d', color: '#f8fafc', display: 'flex', flexDirection: 'column' }}>
      {/* Top Navigation Bar */}
      <header
        style={{
          borderBottom: '1px solid rgba(255, 255, 255, 0.06)',
          backgroundColor: '#121622',
          position: 'sticky',
          top: 0,
          zIndex: 50,
          backdropFilter: 'blur(8px)',
        }}
      >
        <div
          style={{
            maxWidth: '1440px',
            margin: '0 auto',
            padding: '16px 24px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          {/* Logo y Branding */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <div
              style={{
                width: '40px',
                height: '40px',
                borderRadius: '10px',
                backgroundColor: 'rgba(128, 131, 255, 0.15)',
                border: '1px solid rgba(128, 131, 255, 0.3)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#8083ff',
              }}
            >
              <GraduationCap size={24} />
            </div>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span style={{ fontSize: '1.25rem', fontWeight: 700, letterSpacing: '-0.02em', color: '#f8fafc' }}>
                  LectureFlow
                </span>
                <span
                  style={{
                    fontSize: '0.7rem',
                    padding: '2px 8px',
                    borderRadius: '9999px',
                    backgroundColor: 'rgba(128, 131, 255, 0.15)',
                    color: '#c0c1ff',
                    border: '1px solid rgba(128, 131, 255, 0.25)',
                    fontWeight: 600,
                  }}
                >
                  DAW Suite
                </span>
              </div>
              <p style={{ margin: 0, fontSize: '0.8rem', color: '#94a3b8' }}>
                Asistente de Estudio y Síntesis Académica
              </p>
            </div>
          </div>

          {/* Estado de Salud y Controles */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
            {/* Badge de Conexión Backend */}
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                padding: '6px 14px',
                borderRadius: '9999px',
                backgroundColor: health ? 'rgba(78, 222, 163, 0.1)' : 'rgba(239, 68, 68, 0.1)',
                border: `1px solid ${health ? 'rgba(78, 222, 163, 0.25)' : 'rgba(239, 68, 68, 0.3)'}`,
                fontSize: '0.82rem',
                fontWeight: 500,
              }}
            >
              <span
                style={{
                  width: '8px',
                  height: '8px',
                  borderRadius: '50%',
                  backgroundColor: health ? '#4edea3' : '#ef4444',
                  boxShadow: health ? '0 0 8px rgba(78, 222, 163, 0.6)' : 'none',
                }}
              />
              <span style={{ color: health ? '#4edea3' : '#f87171' }}>
                {health ? 'Backend Online (:8000)' : 'Backend Desconectado'}
              </span>
            </div>

            {/* Lockfile en progreso si existe */}
            {health?.procesando && (
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                  padding: '6px 12px',
                  borderRadius: '9999px',
                  backgroundColor: 'rgba(251, 146, 60, 0.15)',
                  border: '1px solid rgba(251, 146, 60, 0.3)',
                  color: '#fb923c',
                  fontSize: '0.78rem',
                }}
              >
                <Sparkles size={14} />
                <span>Procesando: {health.clase_en_proceso}</span>
              </div>
            )}

            {/* Botón Práctica Diaria */}
            <button
              onClick={() => setShowPracticeSession((prev) => !prev)}
              style={{
                backgroundColor: showPracticeSession ? 'rgba(251, 146, 60, 0.25)' : 'rgba(251, 146, 60, 0.15)',
                border: '1px solid rgba(251, 146, 60, 0.35)',
                color: '#fb923c',
                borderRadius: '8px',
                padding: '7px 14px',
                fontSize: '0.82rem',
                fontWeight: 600,
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                transition: 'all 0.2s',
                boxShadow: showPracticeSession ? 'none' : '0 2px 10px rgba(251, 146, 60, 0.2)',
              }}
            >
              <Flame size={15} />
              <span>{showPracticeSession ? 'Cerrar Práctica' : '🔥 Práctica Diaria (SM-2)'}</span>
            </button>

            {/* Botón Nuevo Procesamiento */}
            <button
              onClick={() => setShowProcessingPanel((prev) => !prev)}
              style={{
                backgroundColor: showProcessingPanel ? 'rgba(128, 131, 255, 0.25)' : '#8083ff',
                border: showProcessingPanel ? '1px solid rgba(128, 131, 255, 0.4)' : 'none',
                color: '#ffffff',
                borderRadius: '8px',
                padding: '7px 14px',
                fontSize: '0.82rem',
                fontWeight: 600,
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                boxShadow: showProcessingPanel ? 'none' : '0 2px 10px rgba(128, 131, 255, 0.3)',
                transition: 'all 0.2s',
              }}
            >
              <Sparkles size={14} />
              <span>{showProcessingPanel ? 'Ocultar Ingesta' : '➕ Procesar Clase'}</span>
            </button>

            {/* Botón Refrescar */}
            <button
              onClick={() => cargarDatos(true)}
              disabled={refreshing}
              title="Recargar datos del servidor"
              style={{
                background: 'rgba(255, 255, 255, 0.05)',
                border: '1px solid rgba(255, 255, 255, 0.1)',
                borderRadius: '8px',
                color: '#94a3b8',
                padding: '8px',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                transition: 'all 0.2s',
              }}
            >
              <RefreshCw size={16} className={refreshing ? 'animate-spin' : ''} />
            </button>
          </div>
        </div>
      </header>

      {/* Layout Principal: Sidebar + Contenido Central */}
      <div style={{ display: 'flex', flex: 1, maxWidth: '1440px', width: '100%', margin: '0 auto' }}>
        {/* Sidebar con Acordeón y Gestión (Renombrar / Eliminar) */}
        <Sidebar
          classes={classes}
          selectedSubject={selectedSubject}
          selectedClass={selectedClass}
          onSelectClass={handleSelectClass}
          onRefresh={() => cargarDatos(true)}
          onNewProcessing={() => setShowProcessingPanel(true)}
          onOpenPractice={() => setShowPracticeSession(true)}
        />

        {/* Área Central de Contenido */}
        <main style={{ flex: 1, padding: '32px 36px', overflowY: 'auto' }}>
          {/* Módulo de Práctica Interactiva (Active Recall SM-2 Lite) */}
          {showPracticeSession && (
            <div style={{ marginBottom: '32px' }}>
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
          {/* Banner de Error si el backend está caído */}
          {error && (
            <div
              style={{
                marginBottom: '24px',
                padding: '16px 20px',
                borderRadius: '12px',
                backgroundColor: 'rgba(239, 68, 68, 0.12)',
                border: '1px solid rgba(239, 68, 68, 0.3)',
                color: '#fca5a5',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                gap: '12px',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <AlertCircle size={20} color="#ef4444" />
                <span style={{ fontSize: '0.9rem' }}>{error}</span>
              </div>
              <button
                onClick={() => cargarDatos()}
                style={{
                  backgroundColor: '#ef4444',
                  color: '#fff',
                  border: 'none',
                  padding: '6px 14px',
                  borderRadius: '6px',
                  fontSize: '0.8rem',
                  cursor: 'pointer',
                  fontWeight: 600,
                }}
              >
                Reintentar
              </button>
            </div>
          )}

          {/* Visor y Editor de Apuntes si hay clase seleccionada */}
          {activeClassData && activeSubjectData && (
            <div style={{ marginBottom: '32px' }}>
              <NotesEditor
                subject={activeSubjectData.materia}
                subjectName={activeSubjectData.materia_nombre}
                className={activeClassData.id}
                classReadableName={activeClassData.nombre}
                onClose={() => {
                  setSelectedSubject(null)
                  setSelectedClass(null)
                }}
              />
            </div>
          )}

          {/* 1. Widgets de Estadísticas y Gamificación */}
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
              gap: '16px',
              marginBottom: '32px',
            }}
          >
            {/* Card Racha */}
            <div
              onClick={() => setShowPracticeSession(true)}
              title="Haz clic para iniciar la Práctica Diaria"
              style={{
                backgroundColor: '#171b26',
                border: '1px solid rgba(251, 146, 60, 0.25)',
                borderRadius: '16px',
                padding: '20px',
                display: 'flex',
                alignItems: 'center',
                gap: '16px',
                cursor: 'pointer',
                transition: 'all 0.15s ease',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.borderColor = 'rgba(251, 146, 60, 0.5)'
                e.currentTarget.style.backgroundColor = 'rgba(251, 146, 60, 0.05)'
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.borderColor = 'rgba(251, 146, 60, 0.25)'
                e.currentTarget.style.backgroundColor = '#171b26'
              }}
            >
              <div
                style={{
                  width: '48px',
                  height: '48px',
                  borderRadius: '12px',
                  backgroundColor: 'rgba(251, 146, 60, 0.15)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: '#fb923c',
                }}
              >
                <Flame size={26} />
              </div>
              <div>
                <div style={{ fontSize: '0.78rem', color: '#94a3b8', fontWeight: 500 }}>Racha Diaria</div>
                <div style={{ fontSize: '1.5rem', fontWeight: 800, color: '#fb923c', lineHeight: 1.2 }}>
                  {racha} {racha === 1 ? 'Día' : 'Días'}
                </div>
                <div style={{ fontSize: '0.72rem', color: '#64748b', marginTop: '2px' }}>
                  {stats?.ultimo_dia_estudiado ? `Último: ${stats.ultimo_dia_estudiado}` : 'Sin repasos'}
                </div>
              </div>
            </div>

            {/* Card XP */}
            <div
              onClick={() => setShowPracticeSession(true)}
              title="Haz clic para iniciar la Práctica Diaria"
              style={{
                backgroundColor: '#171b26',
                border: '1px solid rgba(78, 222, 163, 0.25)',
                borderRadius: '16px',
                padding: '20px',
                display: 'flex',
                alignItems: 'center',
                gap: '16px',
                cursor: 'pointer',
                transition: 'all 0.15s ease',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.borderColor = 'rgba(78, 222, 163, 0.5)'
                e.currentTarget.style.backgroundColor = 'rgba(78, 222, 163, 0.05)'
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.borderColor = 'rgba(78, 222, 163, 0.25)'
                e.currentTarget.style.backgroundColor = '#171b26'
              }}
            >
              <div
                style={{
                  width: '48px',
                  height: '48px',
                  borderRadius: '12px',
                  backgroundColor: 'rgba(78, 222, 163, 0.15)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: '#4edea3',
                }}
              >
                <Zap size={26} />
              </div>
              <div>
                <div style={{ fontSize: '0.78rem', color: '#94a3b8', fontWeight: 500 }}>Experiencia</div>
                <div style={{ fontSize: '1.5rem', fontWeight: 800, color: '#4edea3', lineHeight: 1.2 }}>
                  ⚡ {xp} XP
                </div>
                <div style={{ fontSize: '0.72rem', color: '#64748b', marginTop: '2px' }}>
                  +10 XP por acierto
                </div>
              </div>
            </div>

            {/* Card SM-2 Preguntas */}
            <div
              onClick={() => setShowPracticeSession(true)}
              title="Haz clic para iniciar la Práctica Diaria"
              style={{
                backgroundColor: '#171b26',
                border: '1px solid rgba(128, 131, 255, 0.25)',
                borderRadius: '16px',
                padding: '20px',
                display: 'flex',
                alignItems: 'center',
                gap: '16px',
                cursor: 'pointer',
                transition: 'all 0.15s ease',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.borderColor = 'rgba(128, 131, 255, 0.5)'
                e.currentTarget.style.backgroundColor = 'rgba(128, 131, 255, 0.05)'
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.borderColor = 'rgba(128, 131, 255, 0.25)'
                e.currentTarget.style.backgroundColor = '#171b26'
              }}
            >
              <div
                style={{
                  width: '48px',
                  height: '48px',
                  borderRadius: '12px',
                  backgroundColor: 'rgba(128, 131, 255, 0.15)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: '#8083ff',
                }}
              >
                <Sparkles size={26} />
              </div>
              <div>
                <div style={{ fontSize: '0.78rem', color: '#94a3b8', fontWeight: 500 }}>Preguntas SM-2</div>
                <div style={{ fontSize: '1.5rem', fontWeight: 800, color: '#c0c1ff', lineHeight: 1.2 }}>
                  {totalPreguntas} ítems
                </div>
                <div style={{ fontSize: '0.72rem', color: '#64748b', marginTop: '2px' }}>
                  Repetición espaciada
                </div>
              </div>
            </div>

            {/* Card Clases */}
            <div
              style={{
                backgroundColor: '#171b26',
                border: '1px solid rgba(255, 255, 255, 0.08)',
                borderRadius: '16px',
                padding: '20px',
                display: 'flex',
                alignItems: 'center',
                gap: '16px',
              }}
            >
              <div
                style={{
                  width: '48px',
                  height: '48px',
                  borderRadius: '12px',
                  backgroundColor: 'rgba(255, 255, 255, 0.08)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: '#f8fafc',
                }}
              >
                <BookOpen size={26} />
              </div>
              <div>
                <div style={{ fontSize: '0.78rem', color: '#94a3b8', fontWeight: 500 }}>Total Clases</div>
                <div style={{ fontSize: '1.5rem', fontWeight: 800, color: '#f8fafc', lineHeight: 1.2 }}>
                  {totalClases}
                </div>
                <div style={{ fontSize: '0.72rem', color: '#64748b', marginTop: '2px' }}>
                  En {classes.length} asignaturas
                </div>
              </div>
            </div>
          </div>

          {/* 2. Sección Principal: Catálogo de Asignaturas */}
          <section>
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                marginBottom: '20px',
              }}
            >
              <div>
                <h2 style={{ fontSize: '1.35rem', fontWeight: 700, margin: 0, color: '#f8fafc' }}>
                  Catálogo General de Asignaturas
                </h2>
                <p style={{ margin: '4px 0 0', fontSize: '0.85rem', color: '#94a3b8' }}>
                  Usa el menú lateral para explorar temas o administrar materias existentes (renombrar/eliminar).
                </p>
              </div>
            </div>

            {loading ? (
              <div
                style={{
                  textAlign: 'center',
                  padding: '48px 0',
                  color: '#94a3b8',
                  backgroundColor: '#171b26',
                  borderRadius: '16px',
                  border: '1px solid rgba(255, 255, 255, 0.06)',
                }}
              >
                <RefreshCw size={24} className="animate-spin" style={{ margin: '0 auto 12px' }} />
                <p style={{ margin: 0 }}>Cargando catálogo desde FastAPI...</p>
              </div>
            ) : classes.length === 0 ? (
              <div
                style={{
                  textAlign: 'center',
                  padding: '48px 24px',
                  backgroundColor: '#171b26',
                  borderRadius: '16px',
                  border: '1px solid rgba(255, 255, 255, 0.06)',
                  color: '#94a3b8',
                }}
              >
                <Folder size={40} style={{ margin: '0 auto 12px', color: '#64748b' }} />
                <h3 style={{ margin: 0, color: '#f8fafc', fontSize: '1.1rem' }}>No hay asignaturas registradas</h3>
                <p style={{ margin: '6px 0 0', fontSize: '0.85rem' }}>
                  Procesa una nueva clase desde Streamlit para comenzar.
                </p>
              </div>
            ) : (
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))', gap: '20px' }}>
                {classes.map((subject) => (
                  <div
                    key={subject.materia}
                    style={{
                      backgroundColor: '#171b26',
                      borderRadius: '16px',
                      border: '1px solid rgba(255, 255, 255, 0.06)',
                      padding: '20px',
                      display: 'flex',
                      flexDirection: 'column',
                      gap: '16px',
                      transition: 'border-color 0.2s',
                    }}
                  >
                    {/* Encabezado de la Materia */}
                    <div
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        borderBottom: '1px solid rgba(255, 255, 255, 0.06)',
                        paddingBottom: '12px',
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                        <div
                          style={{
                            width: '36px',
                            height: '36px',
                            borderRadius: '8px',
                            backgroundColor: 'rgba(128, 131, 255, 0.12)',
                            color: '#8083ff',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                          }}
                        >
                          <Folder size={20} />
                        </div>
                        <div>
                          <h3 style={{ margin: 0, fontSize: '1.05rem', fontWeight: 600, color: '#f8fafc' }}>
                            {subject.materia_nombre}
                          </h3>
                          <span style={{ fontSize: '0.72rem', color: '#64748b' }}>
                            Carpeta: {subject.materia}
                          </span>
                        </div>
                      </div>
                      <span
                        style={{
                          fontSize: '0.75rem',
                          fontWeight: 600,
                          backgroundColor: 'rgba(255, 255, 255, 0.06)',
                          padding: '3px 9px',
                          borderRadius: '9999px',
                          color: '#c0c1ff',
                        }}
                      >
                        {subject.total_clases} {subject.total_clases === 1 ? 'clase' : 'clases'}
                      </span>
                    </div>

                    {/* Lista de Clases */}
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                      {subject.clases.length === 0 ? (
                        <div style={{ fontSize: '0.82rem', color: '#64748b', fontStyle: 'italic', padding: '8px 0' }}>
                          Sin temas procesados aún.
                        </div>
                      ) : (
                        subject.clases.map((clase) => (
                          <div
                            key={clase.id}
                            onClick={() => handleSelectClass(subject.materia, clase.id)}
                            style={{
                              backgroundColor: '#13161f',
                              borderRadius: '10px',
                              border:
                                selectedSubject === subject.materia && selectedClass === clase.id
                                  ? '1px solid rgba(128, 131, 255, 0.4)'
                                  : '1px solid rgba(255, 255, 255, 0.04)',
                              padding: '12px',
                              display: 'flex',
                              flexDirection: 'column',
                              gap: '6px',
                              cursor: 'pointer',
                              transition: 'all 0.15s',
                            }}
                          >
                            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', overflow: 'hidden' }}>
                                <FileText size={16} color="#94a3b8" style={{ flexShrink: 0 }} />
                                <span
                                  style={{
                                    fontSize: '0.88rem',
                                    fontWeight: 500,
                                    color: '#e2e8f0',
                                    whiteSpace: 'nowrap',
                                    overflow: 'hidden',
                                    textOverflow: 'ellipsis',
                                  }}
                                >
                                  {clase.nombre}
                                </span>
                              </div>
                              <ArrowRight size={14} color="#64748b" />
                            </div>

                            {/* Etiquetas */}
                            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', marginTop: '4px' }}>
                              {clase.tiene_apuntes && (
                                <span
                                  style={{
                                    display: 'inline-flex',
                                    alignItems: 'center',
                                    gap: '3px',
                                    fontSize: '0.68rem',
                                    padding: '2px 6px',
                                    borderRadius: '5px',
                                    backgroundColor: 'rgba(78, 222, 163, 0.12)',
                                    color: '#4edea3',
                                    fontWeight: 600,
                                  }}
                                >
                                  <CheckCircle2 size={11} />
                                  Apuntes
                                </span>
                              )}
                              {clase.tiene_preguntas && (
                                <span
                                  style={{
                                    display: 'inline-flex',
                                    alignItems: 'center',
                                    gap: '3px',
                                    fontSize: '0.68rem',
                                    padding: '2px 6px',
                                    borderRadius: '5px',
                                    backgroundColor: 'rgba(128, 131, 255, 0.12)',
                                    color: '#c0c1ff',
                                    fontWeight: 600,
                                  }}
                                >
                                  <HelpCircle size={11} />
                                  Quiz
                                </span>
                              )}
                            </div>
                          </div>
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
