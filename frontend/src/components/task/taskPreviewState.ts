import { PREVIEWABLE_TASK_STATUSES, type Task, type TaskStatus } from '@/types/task'

function hasSceneItems(value: unknown): boolean {
  return Array.isArray(value) && value.length > 0
}

function resolveSceneCount(task: Pick<Task, 'shotsCount' | 'totalScenes'>): number {
  const count = task.shotsCount ?? task.totalScenes ?? 0
  return typeof count === 'number' && Number.isFinite(count) ? count : 0
}

export function hasTaskPreviewData(
  task: Pick<Task, 'status' | 'detectionResult' | 'userEditedScenes' | 'shotsCount' | 'totalScenes'>,
  liveStatus: TaskStatus = task.status
): boolean {
  const detectedScenes =
    task.detectionResult && typeof task.detectionResult === 'object'
      ? (task.detectionResult as { scenes?: unknown }).scenes
      : undefined

  if (hasSceneItems(task.userEditedScenes) || hasSceneItems(detectedScenes)) {
    return true
  }

  const hasTimelineFallback =
    (liveStatus === 'TIMELINE_READY' || liveStatus === 'COMPLETED') && resolveSceneCount(task) > 0

  return hasTimelineFallback
}

export function canOpenTaskPreview(
  task: Pick<Task, 'status' | 'detectionResult' | 'userEditedScenes' | 'shotsCount' | 'totalScenes'>,
  liveStatus: TaskStatus = task.status
): boolean {
  return PREVIEWABLE_TASK_STATUSES.includes(liveStatus) && hasTaskPreviewData(task, liveStatus)
}

export function canRetryTaskPreview(
  task: Pick<Task, 'status' | 'detectionResult' | 'userEditedScenes' | 'shotsCount' | 'totalScenes'>,
  liveStatus: TaskStatus = task.status
): boolean {
  return liveStatus === 'FAILED' && !hasTaskPreviewData(task, liveStatus)
}
