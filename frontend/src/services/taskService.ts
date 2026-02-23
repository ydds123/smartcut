import apiClient from './api'
import type { DetectionResult, ProcessTaskOptions, ReviewScene, Task, TaskDetail } from '@/types/task'

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

/**
 * 任务进度更新回调
 */
export type TaskProgressCallback = (data: {
  task_id: string
  progress: number
  status: string
  total_scenes: number | null
}) => void

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

  process: async (
    id: string,
    options?: ProcessTaskOptions
  ): Promise<{ status: string; job_id?: string; resolved_config?: Record<string, unknown> }> => {
    const payload = options ? convertToSnakeCase(options) : undefined
    const response = await apiClient.post<{
      status: string
      job_id?: string
      resolved_config?: Record<string, unknown>
    }>(`/api/tasks/${id}/process`, payload)
    return response.data
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

  listenProgress: (id: string, onProgress: TaskProgressCallback): EventSource => {
    const eventSource = new EventSource(`/api/tasks/${id}/progress`)

    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        onProgress(data)
      } catch (error) {
        console.error('Failed to parse progress data:', error)
      }
    }

    eventSource.onerror = (_error) => {
      // 任务结束后 SSE 关闭是预期行为
    }

    return eventSource
  },

  startReview: async (
    id: string,
    options?: ProcessTaskOptions
  ): Promise<{ status: string; job_id?: string }> => {
    const payload = options ? convertToSnakeCase(options) : undefined
    const response = await apiClient.post<{ status: string; job_id?: string }>(
      `/api/tasks/${id}/review`,
      payload
    )
    return response.data
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

  approveReview: async (id: string): Promise<{ status: string; job_id?: string }> => {
    const response = await apiClient.post<{ status: string; job_id?: string }>(
      `/api/tasks/${id}/approve`
    )
    return response.data
  },
}
