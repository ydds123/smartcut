import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { analysisService } from '@/services/analysisService'
import type { AnalysisSettingsUpdatePayload, AnalysisRunStatus } from '@/types/analysis'

const ACTIVE_ANALYSIS_STATUS_SET = new Set<AnalysisRunStatus>(['QUEUED', 'RUNNING'])

export function useAnalysisSettings(enabled = true) {
  return useQuery({
    queryKey: ['analysis-settings'],
    queryFn: analysisService.getSettings,
    enabled,
  })
}

export function useUpdateAnalysisSettings() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: AnalysisSettingsUpdatePayload) => analysisService.updateSettings(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['analysis-settings'] })
    },
  })
}

export function useSaveAnalysisSettings() {
  return useUpdateAnalysisSettings()
}

export function useTestAnalysisSettings() {
  return useMutation({
    mutationFn: (payload: AnalysisSettingsUpdatePayload) => analysisService.testSettings(payload),
  })
}

export function useOpenAnalysisEnvFile() {
  return useMutation({
    mutationFn: () => analysisService.openEnvFile(),
  })
}

export function useTaskAnalysis(taskId: string, enabled: boolean) {
  return useQuery({
    queryKey: ['task-analysis', taskId, 'latest'],
    queryFn: () => analysisService.getTaskLatest(taskId),
    enabled: Boolean(taskId) && enabled,
    refetchInterval: (query) => {
      const status = query.state.data?.status
      return status && ACTIVE_ANALYSIS_STATUS_SET.has(status) ? 2500 : false
    },
    staleTime: 1000,
  })
}

export function useTaskAnalysisBatch(taskIds: string[], enabled: boolean) {
  return useQuery({
    queryKey: ['task-analysis', 'latest-batch', ...taskIds],
    queryFn: () => analysisService.getLatestBatch(taskIds),
    enabled: enabled && taskIds.length > 0,
    refetchInterval: (query) => {
      const items = query.state.data?.items || []
      const hasActive = items.some((item) => ACTIVE_ANALYSIS_STATUS_SET.has(item.status))
      return hasActive ? 2500 : false
    },
    staleTime: 1000,
  })
}

export function useRetryTaskAnalysis() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (taskId: string) => analysisService.retryTaskAnalysis(taskId),
    onSuccess: (_result, taskId) => {
      queryClient.invalidateQueries({ queryKey: ['task-analysis', taskId, 'latest'] })
      queryClient.invalidateQueries({ queryKey: ['task-analysis', 'latest-batch'] })
      queryClient.invalidateQueries({ queryKey: ['tasks'] })
    },
  })
}
