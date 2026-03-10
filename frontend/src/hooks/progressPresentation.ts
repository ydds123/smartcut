import type { ProcessingConfig, TaskStatus } from '../types/task'

export const LONG_RUNNING_STAGE_MS = 6000

const ACTIVE_PRESENTATION_STATUSES = new Set<TaskStatus>([
  'QUEUED',
  'PROCESSING',
  'DETECTING',
  'REVIEW_APPROVED',
  'SPLITTING',
])

export interface ProgressPresentation {
  progress: number
  status: TaskStatus
  stageMessage: string | null
  isLongRunningStage: boolean
  totalScenes: number | null
  lastProgressAt: number
}

interface ProgressPresentationInput {
  progress: number
  status: TaskStatus
  resolvedConfig?: Partial<ProcessingConfig> | null
  totalScenes: number | null
  lastProgressAt: number
  nowMs: number
}

function isPrecisionTransnetStage(resolvedConfig?: Partial<ProcessingConfig> | null): boolean {
  return (
    resolvedConfig?.detectionMode === 'precision' &&
    resolvedConfig?.useTransnet === true
  )
}

export function getTaskStageMessage(
  status: TaskStatus,
  progress: number,
  resolvedConfig?: Partial<ProcessingConfig> | null
): string | null {
  if (status === 'QUEUED') {
    return '已进入队列，马上开始'
  }

  if (status === 'PROCESSING') {
    return '正在处理视频内容'
  }

  if (status === 'DETECTING') {
    if (progress < 35) {
      return '正在扫描镜头边界'
    }
    if (progress < 55) {
      return '正在整理候选镜头'
    }
    if (progress < 80) {
      if (isPrecisionTransnetStage(resolvedConfig)) {
        return '正在执行整片高精度复检，预计耗时更久'
      }
      return '正在验证镜头边界'
    }
    return '正在整理结果并准备预览'
  }

  if (status === 'SPLITTING') {
    return '正在输出片段与缩略图'
  }

  if (status === 'REVIEW_APPROVED') {
    return '已确认分镜，正在生成最终结果'
  }

  return null
}

export function buildProgressPresentation({
  progress,
  status,
  resolvedConfig,
  totalScenes,
  lastProgressAt,
  nowMs,
}: ProgressPresentationInput): ProgressPresentation {
  const normalizedProgress = Math.max(0, Math.min(100, Math.round(progress)))
  const stageMessage = getTaskStageMessage(status, normalizedProgress, resolvedConfig)
  const isLongRunningStage =
    ACTIVE_PRESENTATION_STATUSES.has(status) &&
    Boolean(stageMessage) &&
    nowMs - lastProgressAt >= LONG_RUNNING_STAGE_MS

  return {
    progress: normalizedProgress,
    status,
    stageMessage,
    isLongRunningStage,
    totalScenes,
    lastProgressAt,
  }
}
