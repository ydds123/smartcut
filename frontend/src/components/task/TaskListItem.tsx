import { useEffect, useState } from 'react'

import { Checkbox } from '@/components/ui/checkbox'
import { StatusLabel } from './StatusLabel'
import { useTaskProgress } from '@/hooks/useTaskProgress'
import {
  DELETABLE_TASK_STATUSES,
  PROGRESS_VISIBLE_TASK_STATUSES,
  type Task,
} from '@/types/task'
import type { TaskAnalysisBatchItem } from '@/types/analysis'
import { parseBackendDate } from '@/utils/dateTime'
import { resolveAssetUrl } from '@/utils/assetUrl'
import { canOpenTaskPreview, canRetryTaskPreview } from './taskPreviewState'
import { getTaskAnalysisPresentation } from './taskAnalysisPresentation'
import { getTaskThumbnailPresentation } from './taskThumbnailPresentation'

function formatFileSize(bytes: number): string {
  if (bytes <= 0) {
    return '0 B'
  }
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.min(Math.floor(Math.log(bytes) / Math.log(k)), sizes.length - 1)
  return `${(bytes / Math.pow(k, i)).toFixed(1)} ${sizes[i]}`
}

function formatUploadTime(dateString: string): string {
  const date = parseBackendDate(dateString)
  if (Number.isNaN(date.getTime())) {
    return '--'
  }
  return date.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function formatDuration(durationMs?: number | null): string {
  if (!durationMs || durationMs <= 0) {
    return '--'
  }

  const totalSec = Math.floor(durationMs / 1000)
  const hours = Math.floor(totalSec / 3600)
  const minutes = Math.floor((totalSec % 3600) / 60)
  const seconds = totalSec % 60

  const mm = String(minutes).padStart(2, '0')
  const ss = String(seconds).padStart(2, '0')
  if (hours > 0) {
    return `${hours}:${mm}:${ss}`
  }
  return `${mm}:${ss}`
}

function TaskThumbnailPlaceholder() {
  return (
    <div
      className="flex h-full w-full items-center justify-center text-[var(--sc-text-muted)]"
      aria-hidden="true"
    >
      <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor">
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth="2"
          d="M4 7h16M4 12h16M4 17h16"
        />
      </svg>
    </div>
  )
}

export interface TaskListItemProps {
  task: Task
  analysisStatus?: TaskAnalysisBatchItem
  analysisStatusReady?: boolean
  selected: boolean
  onSelectChange: (checked: boolean) => void
  onDelete: (taskId: string) => void
  onStartReview?: (taskId: string) => void
  onOpenReview?: (taskId: string) => void
  onOpenStoryIntro?: (taskId: string) => void
  isProcessing?: boolean
  isDeleting?: boolean
}

export function TaskListItem({
  task,
  analysisStatus,
  analysisStatusReady = true,
  selected,
  onSelectChange,
  onDelete,
  onStartReview,
  onOpenReview,
  onOpenStoryIntro,
  isProcessing = false,
  isDeleting = false,
}: TaskListItemProps) {
  const {
    progress,
    status,
    totalScenes,
    stageMessage,
    isLongRunningStage,
  } = useTaskProgress(task.id, task.status, task.progress, task.resolvedConfig)

  const liveStatus = status || task.status
  const displayProgress = Math.max(0, Math.min(100, progress ?? task.progress ?? 0))
  const shotsCount = totalScenes ?? task.shotsCount ?? task.totalScenes
  const showProgress = PROGRESS_VISIBLE_TASK_STATUSES.includes(liveStatus)

  const previewUrl = resolveAssetUrl(task.previewThumbnailPath ?? null)
  const [thumbnailLoadFailed, setThumbnailLoadFailed] = useState(false)
  const isBusy = isProcessing || isDeleting
  const actionBtnClass = 'sc-btn sc-btn-secondary h-7 px-3 text-sm'
  const dangerBtnClass = 'sc-btn sc-btn-danger h-7 px-3 text-sm'
  const canPreviewScenes = canOpenTaskPreview(task, liveStatus)
  const canRetryPreview = canRetryTaskPreview(task, liveStatus)
  const canDelete = DELETABLE_TASK_STATUSES.includes(liveStatus)
  const analysisPresentation = getTaskAnalysisPresentation(
    analysisStatus?.status,
    analysisStatusReady
  )
  const canOpenStoryIntro = analysisPresentation.canOpen && Boolean(onOpenStoryIntro)
  const thumbnailPresentation = getTaskThumbnailPresentation(previewUrl, thumbnailLoadFailed)

  useEffect(() => {
    setThumbnailLoadFailed(false)
  }, [task.id, previewUrl])

  return (
    <div
      className={`sc-row grid grid-cols-[32px_minmax(0,2.4fr)_minmax(0,1.25fr)_minmax(0,0.95fr)_80px_64px_minmax(0,0.95fr)_minmax(0,1.8fr)] items-center gap-x-2.5 px-3 py-2.5 ${
        selected ? 'sc-row-selected' : ''
      }`}
    >
      <div className="flex items-center justify-center">
        <Checkbox
          checked={selected}
          onChange={(event) => onSelectChange(event.target.checked)}
          aria-label={`选择任务 ${task.displayName}`}
        />
      </div>

      <div className="min-w-0 px-1.5">
        <div className="flex min-w-0 items-center gap-3">
          <div className="h-[45px] w-20 flex-shrink-0 overflow-hidden rounded-md border border-[var(--sc-border-subtle)] bg-[var(--sc-bg-surface)]">
            {thumbnailPresentation.shouldRenderImage && previewUrl ? (
              <img
                src={previewUrl}
                alt={thumbnailPresentation.alt}
                aria-hidden="true"
                className="h-full w-full object-cover"
                loading="lazy"
                onError={() => setThumbnailLoadFailed(true)}
              />
            ) : (
              <TaskThumbnailPlaceholder />
            )}
          </div>

          <div className="min-w-0 flex-1">
            <div className="truncate text-sm font-semibold text-[var(--sc-text-primary)]" title={task.displayName}>
              {task.displayName}
            </div>
            <div className="mt-0.5 flex items-center gap-2 text-xs text-[var(--sc-text-muted)]">
              <span>{formatFileSize(task.fileSize)}</span>
            </div>
          </div>
        </div>
      </div>

      <div className="min-w-0 px-1.5 text-sm">
        <StatusLabel status={liveStatus} className="text-sm" />
        {stageMessage && (
          <div className="mt-1 text-xs leading-5 text-[var(--sc-text-secondary)]">
            {stageMessage}
          </div>
        )}
        {showProgress && (
          <div className="mt-1.5 flex items-center gap-2">
            <div
              className={`sc-progress-track h-1.5 max-w-[140px] flex-1 overflow-hidden rounded-full bg-[var(--sc-bg-contrast)] ${
                isLongRunningStage ? 'sc-progress-track-active' : ''
              }`}
            >
              <div
                className={`sc-progress-fill h-full rounded-full bg-[var(--sc-accent)] transition-all duration-300 ${
                  isLongRunningStage ? 'sc-progress-fill-active' : ''
                }`}
                style={{ width: `${displayProgress}%` }}
              />
            </div>
            <span className="w-11 text-right text-xs tabular-nums text-[var(--sc-text-muted)]">
              {displayProgress.toFixed(0)}%
            </span>
          </div>
        )}
        {isLongRunningStage && (
          <div className="mt-1 text-xs leading-5 text-[var(--sc-status-info-text)]">
            任务仍在正常进行
          </div>
        )}
      </div>

      <div className="min-w-0 px-1.5 text-sm" onClick={(event) => event.stopPropagation()}>
        {canOpenStoryIntro ? (
          <button
            type="button"
            onClick={() => onOpenStoryIntro?.(task.id)}
            disabled={isBusy}
            aria-label={`打开任务 ${task.displayName} 的故事介绍`}
            className="inline-flex max-w-full items-center gap-1.5 rounded px-2 py-0.5 text-small transition-opacity hover:opacity-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--sc-focus-ring)] disabled:cursor-not-allowed disabled:opacity-60"
            style={{
              color: analysisPresentation.textColor,
              backgroundColor: analysisPresentation.bgColor,
            }}
          >
            <span
              className="h-1.5 w-1.5 flex-shrink-0 rounded-full"
              style={{ backgroundColor: analysisPresentation.borderColor }}
              aria-hidden="true"
            />
            <span className="truncate">{analysisPresentation.label}</span>
          </button>
        ) : (
          <span
            className="inline-flex max-w-full items-center gap-1.5 rounded px-2 py-0.5 text-small"
            style={{
              color: analysisPresentation.textColor,
              backgroundColor: analysisPresentation.bgColor,
            }}
          >
            <span
              className="h-1.5 w-1.5 flex-shrink-0 rounded-full"
              style={{ backgroundColor: analysisPresentation.borderColor }}
              aria-hidden="true"
            />
            <span className="truncate">{analysisPresentation.label}</span>
          </span>
        )}
      </div>

      <div className="px-1.5 text-sm text-[var(--sc-text-secondary)]">
        {formatDuration(task.durationMs)}
      </div>

      <div className="px-1.5 text-sm text-[var(--sc-text-secondary)]">
        {shotsCount ?? '--'}
      </div>

      <div className="px-1.5 text-sm text-[var(--sc-text-secondary)]">
        {formatUploadTime(task.createdAt)}
      </div>

      <div className="min-w-0 px-1.5 text-sm" onClick={(event) => event.stopPropagation()}>
        <div className="flex items-center gap-3 whitespace-nowrap text-[var(--sc-text-primary)]">
          {canPreviewScenes && (
            <button
              type="button"
              onClick={() => onOpenReview?.(task.id)}
              disabled={isBusy}
              className={actionBtnClass}
            >
              预览分镜
            </button>
          )}

          {canRetryPreview && (
            <button
              type="button"
              onClick={() => onStartReview?.(task.id)}
              disabled={isBusy}
              className={actionBtnClass}
            >
              重试预览
            </button>
          )}

          {canDelete && (
            <button
              type="button"
              onClick={() => onDelete(task.id)}
              disabled={isBusy}
              className={dangerBtnClass}
            >
              删除
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
