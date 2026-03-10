import apiClient from './api'
import { incrementClientCounter } from '@/utils/telemetry'
import type {
  DetectionResult,
  LocalPrecisionPreviewRequest,
  LocalPrecisionPreviewResponse,
  ProgressStreamPayload,
  ProcessTaskOptions,
  ProcessTaskResult,
  ProcessingConfigMeta,
  ReviewScene,
  Task,
  TaskStatus,
  TaskDetail,
} from '@/types/task'

const SSE_BASE_URL = (import.meta.env.VITE_SSE_URL || import.meta.env.VITE_API_URL || '').trim()
const API_TOKEN = (import.meta.env.VITE_API_TOKEN || '').trim()

/**
 * 字段名转换：snake_case -> camelCase
 */
function convertToCamelCase<T>(obj: any): T {
  if (!obj || typeof obj !== 'object') return obj

  const converted: any = Array.isArray(obj) ? [] : {}

  for (const key in obj) {
    if (Object.prototype.hasOwnProperty.call(obj, key)) {
      const camelKey = key.replace(/_([a-z])/g, (_, letter) => letter.toUpperCase())
      converted[camelKey] = convertToCamelCase(obj[key])
    }
  }

  return converted as T
}

function convertToSnakeCase(obj: any): any {
  if (!obj || typeof obj !== 'object') {
    return obj
  }

  if (Array.isArray(obj)) {
    return obj.map((item) => convertToSnakeCase(item))
  }

  const converted: Record<string, unknown> = {}
  Object.keys(obj).forEach((key) => {
    const value = obj[key]
    if (value === undefined) {
      return
    }
    const snakeKey = key.replace(/[A-Z]/g, (letter) => `_${letter.toLowerCase()}`)
    converted[snakeKey] = convertToSnakeCase(value)
  })
  return converted
}

function snakeToCamelKey(value: string): string {
  return value.replace(/_([a-z])/g, (_, letter) => letter.toUpperCase())
}

function normalizeProcessingConfigMeta(payload: any): ProcessingConfigMeta {
  const meta = convertToCamelCase<ProcessingConfigMeta>(payload)
  return {
    ...meta,
    fields: (meta.fields || []).map((field) => ({
      ...field,
      key: snakeToCamelKey(String(field.key)) as any,
      boolScope: field.boolScope ? (snakeToCamelKey(String(field.boolScope)) as any) : null,
    })),
  }
}

function normalizeProcessTaskResult(payload: any): ProcessTaskResult {
  const result = convertToCamelCase<any>(payload)
  if (result.configMeta) {
    result.configMeta = normalizeProcessingConfigMeta(result.configMeta)
  }
  return result as ProcessTaskResult
}

/**
 * 任务进度更新回调
 */
export type TaskProgressCallback = (data: {
  type: 'progress' | 'terminal' | 'error'
  taskId: string
  progress?: number
  status?: TaskStatus
  totalScenes?: number | null
  timestamp: number
  errorCode?: string
  errorMessage?: string
}) => void

const VALID_TASK_STATUSES = new Set<TaskStatus>([
  'PENDING',
  'QUEUED',
  'PROCESSING',
  'COMPLETED',
  'FAILED',
  'ANALYZE_QUEUED',
  'ANALYZING',
  'ANALYZE_FAILED',
  'DETECTING',
  'REVIEW_PENDING',
  'REVIEW_APPROVED',
  'SPLITTING',
  'TIMELINE_READY',
])

function buildIdempotencyKey(operation: 'process' | 'review' | 'split', id: string): string {
  const entropy =
    typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function'
      ? crypto.randomUUID()
      : `${Date.now()}-${Math.random().toString(16).slice(2)}`
  return `${operation}:${id}:${entropy}`
}

function toProgressPayload(raw: any): ProgressStreamPayload | null {
  if (!raw || typeof raw !== 'object') {
    incrementClientCounter('sse_invalid_payload_total')
    return null
  }

  const rawTaskId = raw.task_id ?? raw.taskId
  const taskId = typeof rawTaskId === 'string' ? rawTaskId : ''
  const timestampRaw = raw.timestamp
  const timestamp = typeof timestampRaw === 'number' ? timestampRaw : Date.now() / 1000
  const eventTypeRaw = raw.type
  const eventType = typeof eventTypeRaw === 'string' ? eventTypeRaw : null

  if (eventType === 'error') {
    return {
      type: 'error',
      taskId,
      errorCode: String(raw.error_code ?? raw.errorCode ?? 'stream_error'),
      errorMessage: String(raw.error_message ?? raw.errorMessage ?? raw.error ?? 'stream error'),
      timestamp,
    }
  }

  const statusRaw = raw.status
  if (typeof statusRaw !== 'string' || !VALID_TASK_STATUSES.has(statusRaw as TaskStatus)) {
    if (typeof raw.error === 'string') {
      return {
        type: 'error',
        taskId,
        errorCode: 'stream_error',
        errorMessage: raw.error,
        timestamp,
      }
    }
    incrementClientCounter('sse_invalid_payload_total')
    return null
  }

  const progressRaw = raw.progress
  if (typeof progressRaw !== 'number' || Number.isNaN(progressRaw)) {
    incrementClientCounter('sse_invalid_payload_total')
    return null
  }
  const totalScenesRaw = raw.total_scenes ?? raw.totalScenes ?? null
  const totalScenes = typeof totalScenesRaw === 'number' || totalScenesRaw === null ? totalScenesRaw : null
  const fallbackType = ['COMPLETED', 'FAILED', 'ANALYZE_FAILED', 'REVIEW_PENDING', 'TIMELINE_READY'].includes(statusRaw)
    ? 'terminal'
    : 'progress'

  return {
    type: eventType === 'terminal' ? 'terminal' : eventType === 'progress' ? 'progress' : fallbackType,
    taskId,
    progress: progressRaw,
    status: statusRaw as TaskStatus,
    totalScenes,
    timestamp,
  }
}

/**
 * 任务服务
 */
export const taskService = {
  getAll: async (): Promise<Task[]> => {
    const response = await apiClient.get<any[]>('/api/tasks')
    return response.data.map((task) => convertToCamelCase<Task>(task))
  },

  getById: async (id: string): Promise<TaskDetail> => {
    const response = await apiClient.get<any>(`/api/tasks/${id}`)
    return convertToCamelCase<TaskDetail>(response.data)
  },

  delete: async (id: string): Promise<void> => {
    await apiClient.delete(`/api/tasks/${id}`)
  },

  process: async (id: string, options?: ProcessTaskOptions): Promise<ProcessTaskResult> => {
    const payload = options ? convertToSnakeCase(options) : undefined
    const response = await apiClient.post<any>(`/api/tasks/${id}/process`, payload, {
      headers: {
        'Idempotency-Key': buildIdempotencyKey('process', id),
      },
    })
    return normalizeProcessTaskResult(response.data)
  },

  getProcessingConfigMeta: async (): Promise<ProcessingConfigMeta> => {
    const response = await apiClient.get<any>('/api/config/processing-meta')
    return normalizeProcessingConfigMeta(response.data)
  },

  getResult: async (id: string): Promise<TaskDetail> => {
    const response = await apiClient.get<any>(`/api/tasks/${id}/result`)
    return convertToCamelCase<TaskDetail>(response.data)
  },

  download: async (id: string): Promise<Blob> => {
    const response = await apiClient.get(`/api/tasks/${id}/download`, {
      responseType: 'blob',
    })
    return response.data
  },

  listenProgress: (
    id: string,
    onProgress: TaskProgressCallback,
    onStreamError?: (error: Error) => void
  ): EventSource => {
    const query = API_TOKEN ? `?api_token=${encodeURIComponent(API_TOKEN)}` : ''
    const relativePath = `/api/tasks/${id}/progress${query}`
    const base = SSE_BASE_URL.replace(/\/$/, '')
    const eventSource = new EventSource(base ? `${base}${relativePath}` : relativePath)

    eventSource.onmessage = (event) => {
      try {
        const rawData = JSON.parse(event.data)
        const payload = toProgressPayload(rawData)
        if (!payload) {
          incrementClientCounter('sse_invalid_payload_total')
          console.warn('Ignored malformed progress event payload:', rawData)
          return
        }
        onProgress(payload)
      } catch (error) {
        incrementClientCounter('sse_invalid_payload_total')
        console.error('Failed to parse progress data:', error)
      }
    }

    eventSource.onerror = (_error) => {
      onStreamError?.(new Error(`SSE stream error for task ${id}`))
    }

    return eventSource
  },

  startReview: async (id: string, options?: ProcessTaskOptions): Promise<ProcessTaskResult> => {
    const payload = options ? convertToSnakeCase(options) : undefined
    const response = await apiClient.post<any>(`/api/tasks/${id}/review`, payload, {
      headers: {
        'Idempotency-Key': buildIdempotencyKey('review', id),
      },
    })
    return normalizeProcessTaskResult(response.data)
  },

  getReviewData: async (id: string): Promise<{
    taskId: string
    detectionResult: DetectionResult
    userEditedScenes: ReviewScene[] | null
    status: string
  }> => {
    const response = await apiClient.get<any>(`/api/tasks/${id}/review-data`)
    return convertToCamelCase(response.data)
  },

  saveReviewData: async (id: string, scenes: ReviewScene[]): Promise<void> => {
    await apiClient.put(`/api/tasks/${id}/review-data`, {
      scenes: scenes.map((s) => convertToSnakeCase(s)),
    })
  },

  localPrecisionPreview: async (
    id: string,
    payload: LocalPrecisionPreviewRequest
  ): Promise<LocalPrecisionPreviewResponse> => {
    const response = await apiClient.post<any>(
      `/api/tasks/${id}/review/local-precision-preview`,
      convertToSnakeCase(payload)
    )
    return convertToCamelCase(response.data)
  },

  resetReviewFromTimeline: async (
    id: string
  ): Promise<{ success: boolean; scenesCount: number; source: string }> => {
    const response = await apiClient.post<any>(`/api/tasks/${id}/review/reset-from-timeline`)
    return convertToCamelCase(response.data)
  },

  openSceneFolder: async (taskId: string, sceneId: string): Promise<{ success: boolean; folderPath: string }> => {
    const response = await apiClient.post<any>(`/api/tasks/${taskId}/scenes/${sceneId}/open-folder`)
    return convertToCamelCase(response.data)
  },

  approveReview: async (
    id: string,
    options?: ProcessTaskOptions
  ): Promise<{ status: string; jobId?: string; deduplicated?: boolean }> => {
    const payload = options ? convertToSnakeCase(options) : undefined
    const response = await apiClient.post<any>(`/api/tasks/${id}/approve`, payload, {
      headers: {
        'Idempotency-Key': buildIdempotencyKey('split', id),
      },
    })
    return convertToCamelCase(response.data)
  },
}
