import apiClient from './api'
import type {
  AnalysisOpenEnvFileResult,
  AnalysisSettings,
  AnalysisSettingsTestResult,
  AnalysisSettingsUpdatePayload,
  RetryAnalysisResponse,
  TaskAnalysisLatestBatchResponse,
  TaskAnalysisLatest,
} from '@/types/analysis'

function convertToCamelCase<T>(obj: any): T {
  if (!obj || typeof obj !== 'object') return obj

  const converted: any = Array.isArray(obj) ? [] : {}
  for (const key in obj) {
    if (!Object.prototype.hasOwnProperty.call(obj, key)) continue
    const camelKey = key.replace(/_([a-z])/g, (_, letter) => letter.toUpperCase())
    converted[camelKey] = convertToCamelCase(obj[key])
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
    if (value === undefined) return
    const snakeKey = key.replace(/[A-Z]/g, (letter) => `_${letter.toLowerCase()}`)
    converted[snakeKey] = convertToSnakeCase(value)
  })
  return converted
}

export const analysisService = {
  getSettings: async (): Promise<AnalysisSettings> => {
    const response = await apiClient.get('/api/analysis/settings')
    return convertToCamelCase<AnalysisSettings>(response.data)
  },

  updateSettings: async (payload: AnalysisSettingsUpdatePayload): Promise<AnalysisSettings> => {
    const response = await apiClient.put('/api/analysis/settings', convertToSnakeCase(payload))
    return convertToCamelCase<AnalysisSettings>(response.data)
  },

  testSettings: async (payload: AnalysisSettingsUpdatePayload): Promise<AnalysisSettingsTestResult> => {
    const response = await apiClient.post('/api/analysis/settings/test', convertToSnakeCase(payload))
    return convertToCamelCase<AnalysisSettingsTestResult>(response.data)
  },

  openEnvFile: async (): Promise<AnalysisOpenEnvFileResult> => {
    const response = await apiClient.post(
      '/api/analysis/settings/open-env-file',
      {},
      {
        headers: {
          'X-SmartCut-Local-Action': 'open-analysis-env-file',
        },
      }
    )
    return convertToCamelCase<AnalysisOpenEnvFileResult>(response.data)
  },

  getTaskLatest: async (taskId: string): Promise<TaskAnalysisLatest> => {
    const response = await apiClient.get(`/api/tasks/${taskId}/analysis/latest`)
    return convertToCamelCase<TaskAnalysisLatest>(response.data)
  },

  getLatestBatch: async (taskIds: string[]): Promise<TaskAnalysisLatestBatchResponse> => {
    const normalizedTaskIds = Array.from(
      new Set(taskIds.map((taskId) => taskId.trim()).filter((taskId) => Boolean(taskId)))
    )
    if (!normalizedTaskIds.length) {
      return { items: [] }
    }

    const chunkSize = 200
    const chunks: string[][] = []
    for (let index = 0; index < normalizedTaskIds.length; index += chunkSize) {
      chunks.push(normalizedTaskIds.slice(index, index + chunkSize))
    }

    const chunkResponses = await Promise.all(
      chunks.map(async (chunk) => {
        const response = await apiClient.post('/api/analysis/tasks/latest-batch', {
          task_ids: chunk,
        })
        return convertToCamelCase<TaskAnalysisLatestBatchResponse>(response.data)
      })
    )

    const itemMap = new Map(
      chunkResponses.flatMap((chunkResponse) => chunkResponse.items || []).map((item) => [item.taskId, item])
    )
    return {
      items: normalizedTaskIds
        .map((taskId) => itemMap.get(taskId))
        .filter((item): item is NonNullable<typeof item> => Boolean(item)),
    }
  },

  retryTaskAnalysis: async (taskId: string): Promise<RetryAnalysisResponse> => {
    const response = await apiClient.post(`/api/tasks/${taskId}/analysis/retry`)
    return convertToCamelCase<RetryAnalysisResponse>(response.data)
  },

  // backward-compatible aliases
  saveSettings: async (payload: AnalysisSettingsUpdatePayload): Promise<AnalysisSettings> => {
    return analysisService.updateSettings(payload)
  },
  getLatest: async (taskId: string): Promise<TaskAnalysisLatest> => {
    return analysisService.getTaskLatest(taskId)
  },
  retry: async (taskId: string): Promise<RetryAnalysisResponse> => {
    return analysisService.retryTaskAnalysis(taskId)
  },
}

export type AnalysisSettingsUpsertInput = AnalysisSettingsUpdatePayload
