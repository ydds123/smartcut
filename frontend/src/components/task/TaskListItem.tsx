import { Checkbox } from '@/components/ui/checkbox'
import { StatusLabel } from './StatusLabel'
import { useTaskProgress } from '@/hooks/useTaskProgress'
import type { Task } from '@/types/task'
import { parseBackendDate } from '@/utils/dateTime'
import { resolveAssetUrl } from '@/utils/assetUrl'

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

export interface TaskListItemProps {
  task: Task
  selected: boolean
  onSelectChange: (checked: boolean) => void
  onViewResult: (taskId: string) => void
  onDelete: (taskId: string) => void
  onProcess: (taskId: string) => void
  onStartReview?: (taskId: string) => void
  onOpenReview?: (taskId: string) => void
  isProcessing?: boolean
  isDeleting?: boolean
}

export function TaskListItem({
  task,
  selected,
  onSelectChange,
  onViewResult,
  onDelete,
  onProcess,
  onStartReview,
  onOpenReview,
  isProcessing = false,
  isDeleting = false,
}: TaskListItemProps) {
  const { progress, status, totalScenes } = useTaskProgress(task.id, task.status, task.progress)

  const liveStatus = status || task.status
  const displayProgress = Math.max(0, Math.min(100, progress ?? task.progress ?? 0))
  const shotsCount = totalScenes ?? task.shotsCount ?? task.totalScenes
  const showProgress = ['PROCESSING', 'QUEUED', 'DETECTING', 'SPLITTING', 'REVIEW_APPROVED'].includes(liveStatus)

  const previewUrl = resolveAssetUrl(task.previewThumbnailPath ?? null)
  const isBusy = isProcessing || isDeleting
  const actionBtnClass = 'sc-btn sc-btn-secondary h-7 px-3 text-sm'
  const dangerBtnClass = 'sc-btn sc-btn-danger h-7 px-3 text-sm'

  return (
    <div
      className={`sc-row grid grid-cols-[32px_2.5fr_1.2fr_80px_64px_0.9fr_1.8fr] items-center gap-x-2.5 px-3 py-2.5 ${
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
            {previewUrl ? (
              <img
                src={previewUrl}
                alt={task.displayName}
                className="h-full w-full object-cover"
                loading="lazy"
              />
            ) : (
              <div className="flex h-full w-full items-center justify-center text-[var(--sc-text-muted)]">
                <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor">
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth="2"
                    d="M4 7h16M4 12h16M4 17h16"
                  />
                </svg>
              </div>
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
        {showProgress && (
          <div className="mt-1 flex items-center gap-2">
            <div className="h-1.5 max-w-[140px] flex-1 overflow-hidden rounded-full bg-[var(--sc-bg-contrast)]">
              <div
                className="h-full rounded-full bg-[var(--sc-accent)] transition-all duration-300"
                style={{ width: `${displayProgress}%` }}
              />
            </div>
            <span className="w-11 text-right text-xs tabular-nums text-[var(--sc-text-muted)]">
              {displayProgress.toFixed(0)}%
            </span>
          </div>
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
          {liveStatus === 'PENDING' && (
            <>
              <button
                type="button"
                onClick={() => onProcess(task.id)}
                disabled={isBusy}
                className={actionBtnClass}
              >
                直接处理
              </button>
              <button
                type="button"
                onClick={() => onStartReview?.(task.id)}
                disabled={isBusy}
                className={actionBtnClass}
              >
                检测并审核
              </button>
              <button
                type="button"
                onClick={() => onDelete(task.id)}
                disabled={isBusy}
                className={dangerBtnClass}
              >
                删除
              </button>
            </>
          )}

          {(['QUEUED', 'PROCESSING', 'DETECTING', 'SPLITTING', 'REVIEW_APPROVED'] as const).includes(liveStatus as any) && (
            <button
              type="button"
              onClick={() => onDelete(task.id)}
              disabled={isBusy}
              className={dangerBtnClass}
            >
              删除
            </button>
          )}

          {liveStatus === 'REVIEW_PENDING' && (
            <>
              <button
                type="button"
                onClick={() => onOpenReview?.(task.id)}
                disabled={isBusy}
                className={actionBtnClass}
              >
                查看并编辑
              </button>
              <button
                type="button"
                onClick={() => onDelete(task.id)}
                disabled={isBusy}
                className={dangerBtnClass}
              >
                删除
              </button>
            </>
          )}

          {liveStatus === 'TIMELINE_READY' && (
            <button
              type="button"
              onClick={() => onViewResult(task.id)}
              disabled={isBusy}
              className={actionBtnClass}
            >
              查看工作台
            </button>
          )}

          {liveStatus === 'COMPLETED' && (
            <button
              type="button"
              onClick={() => onViewResult(task.id)}
              disabled={isBusy}
              className={actionBtnClass}
            >
              查看详情
            </button>
          )}

          {liveStatus === 'FAILED' && (
            <>
              <button
                type="button"
                onClick={() => onViewResult(task.id)}
                disabled={isBusy}
                className={actionBtnClass}
              >
                查看详情
              </button>
              <button
                type="button"
                onClick={() => onDelete(task.id)}
                disabled={isBusy}
                className={dangerBtnClass}
              >
                删除
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
