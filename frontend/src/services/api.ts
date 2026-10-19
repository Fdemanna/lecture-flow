/**
 * Cliente de API tipado para comunicarse con el backend FastAPI de LectureFlow.
 */

export interface HealthStatus {
  status: string
  procesando: boolean
  clase_en_proceso: string | null
  lockfile_presente: boolean
}

export interface ClassItem {
  id: string
  nombre: string
  tiene_apuntes: boolean
  tiene_preguntas: boolean
  tiene_transcripcion: boolean
  ruta_relativa: string
}

export interface SubjectTree {
  materia: string
  materia_nombre: string
  total_clases: number
  clases: ClassItem[]
}

export interface StudyQuestionState {
  repeticiones?: number
  intervalo?: number
  intervalo_dias?: number
  aciertos?: number
  fallos?: number
  ultimo_repaso?: string | null
  proximo_repaso?: string | null
}

export interface StudyStats {
  racha_actual: number
  ultimo_dia_estudiado: string | null
  xp_total: number
  total_preguntas_registradas: number
  preguntas_dominadas: number
  historial_preguntas: Record<string, StudyQuestionState>
}

export interface ApiResponse {
  status: string
  mensaje: string
  [key: string]: any
}

const API_BASE_URL = '/api'

export class ApiError extends Error {
  status: number
  statusText: string
  data?: any

  constructor(message: string, status: number, statusText: string, data?: any) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.statusText = statusText
    this.data = data
    Object.setPrototypeOf(this, ApiError.prototype)
  }
}

/**
 * Formatea el campo detail devuelto por FastAPI (puede ser string, objeto o array de validaciones).
 * Garantiza texto limpio y nunca [object Object].
 */
export function formatApiErrorDetail(detail: any): string {
  if (!detail) return ''
  if (typeof detail === 'string') return detail

  if (Array.isArray(detail)) {
    return detail
      .map((item) => {
        if (typeof item === 'string') return item
        if (item && typeof item === 'object') {
          const loc = Array.isArray(item.loc)
            ? item.loc.filter((l: any) => l !== 'body').join('.')
            : item.loc
          const msg = item.msg || item.message || JSON.stringify(item)
          return loc ? `${loc}: ${msg}` : msg
        }
        return String(item)
      })
      .filter(Boolean)
      .join('; ')
  }

  if (typeof detail === 'object') {
    if (detail.message && typeof detail.message === 'string') {
      return detail.message
    }
    if (detail.msg && typeof detail.msg === 'string') {
      return detail.msg
    }
    if (detail.error && typeof detail.error === 'string') {
      return detail.error
    }
    try {
      return JSON.stringify(detail)
    } catch {
      return String(detail)
    }
  }

  return String(detail)
}

/**
 * Extrae un mensaje de error legible a partir de la respuesta HTTP.
 */
export function extractErrorMessage(
  status: number,
  statusText: string,
  data?: any
): string {
  if (status === 409) {
    return 'Conflicto (409): Ya hay una tarea en curso o existe un archivo de bloqueo pendiente. Revisa si hay un proceso activo.'
  }

  if (data) {
    const rawDetail = data.detail ?? data.message ?? data.error
    if (rawDetail !== undefined && rawDetail !== null) {
      const formatted = formatApiErrorDetail(rawDetail)
      if (formatted) return formatted
    }
    if (typeof data === 'string' && data.trim()) {
      return data
    }
  }

  return `Error en llamada API: ${status} ${statusText}`
}

async function request<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
  })

  if (!response.ok) {
    let errData: any = null
    try {
      errData = await response.json()
    } catch {
      try {
        errData = await response.text()
      } catch {}
    }
    const errorMsg = extractErrorMessage(response.status, response.statusText, errData)
    throw new ApiError(errorMsg, response.status, response.statusText, errData)
  }

  return response.json() as Promise<T>
}

export async function getHealth(): Promise<HealthStatus> {
  return request<HealthStatus>('/health')
}

export async function getClasses(): Promise<SubjectTree[]> {
  return request<SubjectTree[]>('/classes')
}

export async function getStudyStats(): Promise<StudyStats> {
  return request<StudyStats>('/study/stats')
}

export interface QuestionDto {
  id: string
  materia: string
  materia_nombre: string
  clase: string
  clase_nombre: string
  tipo: string
  pregunta: string
  codigo?: string
  opciones: string[]
}

export interface AnswerResultDto {
  correct: boolean
  correct_index: number
  explanation: string
  question_id: string
  stats: StudyStats
}

export async function getDueQuestions(limit: number = 5): Promise<QuestionDto[]> {
  return request<QuestionDto[]>(`/study/due?limit=${limit}`)
}

export async function submitAnswer(
  questionId: string,
  selectedOption: number
): Promise<AnswerResultDto> {
  return request<AnswerResultDto>('/study/answer', {
    method: 'POST',
    body: JSON.stringify({
      question_id: questionId,
      selected_option: selectedOption,
    }),
  })
}


export async function renameClass(subject: string, newName: string): Promise<ApiResponse> {
  return request<ApiResponse>(`/classes/${encodeURIComponent(subject)}`, {
    method: 'PATCH',
    body: JSON.stringify({ nuevo_nombre: newName }),
  })
}

export async function deleteClass(subject: string): Promise<ApiResponse> {
  return request<ApiResponse>(`/classes/${encodeURIComponent(subject)}`, {
    method: 'DELETE',
  })
}

export interface NotesResponse {
  contenido: string
  existe: boolean
  ultima_modificacion?: string | null
}

export async function getNotes(subject: string, className: string): Promise<NotesResponse> {
  return request<NotesResponse>(
    `/classes/${encodeURIComponent(subject)}/${encodeURIComponent(className)}/notes`
  )
}

export async function saveNotes(subject: string, className: string, contenido: string): Promise<ApiResponse> {
  return request<ApiResponse>(
    `/classes/${encodeURIComponent(subject)}/${encodeURIComponent(className)}/notes`,
    {
      method: 'PUT',
      body: JSON.stringify({ contenido }),
    }
  )
}

export interface NotionExportResponse {
  status: string
  url_notion: string
  mensaje: string
}

export async function exportToNotion(
  subject: string,
  className: string
): Promise<NotionExportResponse> {
  return request<NotionExportResponse>(
    `/classes/${encodeURIComponent(subject)}/${encodeURIComponent(className)}/export/notion`,
    {
      method: 'POST',
    }
  )
}

export async function sendTelegramNotification(
  subject: string,
  className: string,
  urlNotion?: string
): Promise<ApiResponse> {
  return request<ApiResponse>(
    `/classes/${encodeURIComponent(subject)}/${encodeURIComponent(className)}/export/telegram`,
    {
      method: 'POST',
      body: JSON.stringify({ url_notion: urlNotion || null }),
    }
  )
}

// Alias semánticos
export const renameSubject = renameClass
export const deleteSubject = deleteClass

// =============================================================================
// SERVICIOS DE JOBS EN SEGUNDO PLANO Y SERVER-SENT EVENTS (SSE)
// =============================================================================

export interface JobState {
  job_id: string
  materia: string
  tema: string
  status: 'running' | 'completed' | 'failed' | 'cancelled'
  phase: string
  progress: number
  message: string
  created_at?: string
  completed_at?: string
  error?: string | null
  es_externo?: boolean
}

export interface JobEvent {
  job_id: string
  status: 'running' | 'completed' | 'failed' | 'cancelled'
  phase: string
  progress: number
  message: string
  error?: string
}

export async function getActiveJob(): Promise<JobState | null> {
  return request<JobState | null>('/jobs/active')
}

export async function startJob(
  payload: FormData | Record<string, any>
): Promise<{ job_id: string; status: string; materia: string; tema: string }> {
  const isFormData = payload instanceof FormData
  const response = await fetch(`${API_BASE_URL}/jobs`, {
    method: 'POST',
    headers: isFormData ? undefined : { 'Content-Type': 'application/json' },
    body: isFormData ? payload : JSON.stringify(payload),
  })

  if (!response.ok) {
    let errData: any = null
    try {
      errData = await response.json()
    } catch {
      try {
        errData = await response.text()
      } catch {}
    }
    const errorMsg = extractErrorMessage(response.status, response.statusText, errData)
    throw new ApiError(errorMsg, response.status, response.statusText, errData)
  }

  return response.json()
}

export async function cancelJob(jobId: string): Promise<ApiResponse> {
  return request<ApiResponse>(`/jobs/${encodeURIComponent(jobId)}/cancel`, {
    method: 'POST',
  })
}

export function subscribeToJobEvents(
  jobId: string,
  onEvent: (event: JobEvent) => void,
  onError?: (err: Event) => void
): () => void {
  const eventSource = new EventSource(`${API_BASE_URL}/jobs/${encodeURIComponent(jobId)}/events`)

  eventSource.onmessage = (e) => {
    try {
      const data: JobEvent = JSON.parse(e.data)
      onEvent(data)
      if (['completed', 'failed', 'cancelled'].includes(data.status)) {
        eventSource.close()
      }
    } catch (err) {
      console.error('Error al procesar evento SSE:', err)
    }
  }

  eventSource.onerror = (err) => {
    if (onError) onError(err)
  }

  return () => {
    eventSource.close()
  }
}

export async function regenerateNotes(
  subject: string,
  className: string
): Promise<{ job_id: string; status: string }> {
  return request<{ job_id: string; status: string }>(
    `/classes/${encodeURIComponent(subject)}/${encodeURIComponent(className)}/regenerate`,
    {
      method: 'POST',
    }
  )
}


