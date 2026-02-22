import { Checkbox } from '@/components/ui/checkbox'
import { StatusLabel } from './StatusLabel'
import { useTaskProgress } from '@/hooks/useTaskProgress'
import type { Task } from '@/types/task'
import { parseBackendDate } from '@/utils/dateTime'

const backendBaseUrl = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000'

function resolveAssetUrl(pathValue: string | null): string | null {
  if (!pathValue) {
    return null
  }

  const normalized = pathValue.trim()
  if (!normalized) {
    return null
  }

  if (normalized.startsWith('http://') || normalized.startsWith('https://')) {
    return normalized
  }

  const withLeadingSlash = normalized.startsWith('/') ? normalized : `/${normalized}`
  return `${backendBaseUrl}${withLeadingSlash}`
}

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
  const { progress, status, totalScenes } = useTaskProgress(task.id, task.status)

  const liveStatus = status || task.status
  const displayProgress = Math.min(100, Math.max(progress ?? 0, task.progress ?? 0))
  const shotsCount = totalScenes ?? task.shotsCount ?? task.totalScenes
  const showProgress = ['PROCESSING', 'QUEUED', 'DETECTING', 'SPLITTING'].includes(liveStatus)

  const previewUrl = resolveAssetUrl(task.previewThumbnailPath ?? null)
  const isBusy = isProcessing || isDeleting

  return (
    <div
      className={`grid grid-cols-[32px_2.8fr_1.2fr_0.6fr_0.9fr_1fr] items-center gap-x-3 border-b border-[#27272a] px-3 py-2.5 transition-colors hover:bg-[#1c1c1f] ${
        selected ? 'bg-[rgba(47,140,255,0.08)]' : 'bg-[#18181b]'
      }`}
    >
      <div className="flex items-center justify-center">
        <Checkbox
          checked={selected}
          onChange={(event) => onSelectChange(event.target.checked)}
          aria-label={`选择任务 ${task.displayName}`}
        />
      </div>

      <div className="min-w-0 pr-4">
        <div className="flex min-w-0 items-center gap-3">
        <div className="h-[45px] w-20 flex-shrink-0 overflow-hidden rounded-md border border-[#27272a] bg-[#27272a]">
          {previewUrl ? (
            <img
              src={previewUrl}
              alt={task.displayName}
              className="h-full w-full object-cover"
              loading="lazy"
            />
          ) : (
            <div className="flex h-full w-full items-center justify-center text-[#71717a]">
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
          <div className="truncate text-sm font-semibold text-[#d4d4d8]" title={task.displayName}>
            {task.displayName}
          </div>
          <div className="mt-0.5 flex items-center gap-2 text-xs text-[#71717a]">
            <span>{formatFileSize(task.fileSize)}</span>
          </div>
        </div>
        </div>
      </div>

      <div className="min-w-0 text-sm">
        <StatusLabel status={liveStatus} className="text-sm" />
        {showProgress && (
          <div className="mt-1 flex items-center gap-2">
            <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-[#27272a]">
              <div
                className="h-full rounded-full bg-primary transition-all duration-300"
                style={{ width: `${displayProgress}%` }}
              />
            </div>
            <span className="w-11 text-right text-xs tabular-nums text-[#71717a]">
              {displayProgress.toFixed(0)}%
            </span>
          </div>
        )}
      </div>

      <div className="text-sm text-[#71717a]">
        {shotsCount ?? '--'}
      </div>

      <div className="text-sm text-[#71717a]">
        {formatUploadTime(task.createdAt)}
      </div>

      <div className="min-w-0 text-sm" onClick={(event) => event.stopPropagation()}>
        <div className="flex items-center gap-3 whitespace-nowrap text-[#d4d4d8]">
          {liveStatus === 'PENDING' && (
            <>
              <button
                type="button"
                onClick={() => onProcess(task.id)}
                disabled={isBusy}
                className="inline-flex h-7 items-center justify-center rounded-md border border-[#27272a] bg-[#18181b] px-3 text-sm font-medium text-[#d4d4d8] transition-colors hover:border-primary hover:bg-[rgba(47,140,255,0.08)] disabled:cursor-not-allowed disabled:opacity-50"
              >
                直接处理
              </button>
              <button
                type="button"
                onClick={() => onStartReview?.(task.id)}
                disabled={isBusy}
                className="inline-flex h-7 items-center justify-center rounded-md border border-[#27272a] bg-[#18181b] px-3 text-sm font-medium text-[#d4d4d8] transition-colors hover:border-primary hover:bg-[rgba(47,140,255,0.08)] disabled:cursor-not-allowed disabled:opacity-50"
              >
                检测并审核
              </button>
              <button
                type="button"
                onClick={() => onDelete(task.id)}
                disabled={isBusy}
                className="inline-flex h-7 items-center justify-center rounded-md border border-[#27272a] bg-[#18181b] px-3 text-sm font-medium text-danger transition-colors hover:border-danger hover:bg-[rgba(239,68,68,0.08)] disabled:cursor-not-allowed disabled:opacity-50"
              >
                删除
              </button>
            </>
          )}

          {(['QUEUED', 'PROCESSING', 'DETECTING', 'SPLITTING'] as const).includes(liveStatus as any) && (
            <button
              type="button"
              onClick={() => onDelete(task.id)}
              disabled={isBusy}
              className="inline-flex h-7 items-center justify-center rounded-md border border-[#27272a] bg-[#18181b] px-3 text-sm font-medium text-danger transition-colors hover:border-danger hover:bg-[rgba(239,68,68,0.08)] disabled:cursor-not-allowed disabled:opacity-50"
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
                className="inline-flex h-7 items-center justify-center rounded-md border border-[#27272a] bg-[#18181b] px-3 text-sm font-medium text-[#d4d4d8] transition-colors hover:border-primary hover:bg-[rgba(47,140,255,0.08)] disabled:cursor-not-allowed disabled:opacity-50"
              >
                查看并编辑
              </button>
              <button
                type="button"
                onClick={() => onDelete(task.id)}
                disabled={isBusy}
                className="inline-flex h-7 items-center justify-center rounded-md border border-[#27272a] bg-[#18181b] px-3 text-sm font-medium text-danger transition-colors hover:border-danger hover:bg-[rgba(239,68,68,0.08)] disabled:cursor-not-allowed disabled:opacity-50"
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
              className="inline-flex h-7 items-center justify-center rounded-md border border-[#27272a] bg-[#18181b] px-3 text-sm font-medium text-[#d4d4d8] transition-colors hover:border-primary hover:bg-[rgba(47,140,255,0.08)] disabled:cursor-not-allowed disabled:opacity-50"
            >
              查看工作台
            </button>
          )}

          {liveStatus === 'COMPLETED' && (
            <button
              type="button"
              onClick={() => onViewResult(task.id)}
              disabled={isBusy}
              className="inline-flex h-7 items-center justify-center rounded-md border border-[#27272a] bg-[#18181b] px-3 text-sm font-medium text-[#d4d4d8] transition-colors hover:border-primary hover:bg-[rgba(47,140,255,0.08)] disabled:cursor-not-allowed disabled:opacity-50"
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
                className="inline-flex h-7 items-center justify-center rounded-md border border-[#27272a] bg-[#18181b] px-3 text-sm font-medium text-[#d4d4d8] transition-colors hover:border-primary hover:bg-[rgba(47,140,255,0.08)] disabled:cursor-not-allowed disabled:opacity-50"
              >
                查看详情
              </button>
              <button
                type="button"
                onClick={() => onDelete(task.id)}
                disabled={isBusy}
                className="inline-flex h-7 items-center justify-center rounded-md border border-[#27272a] bg-[#18181b] px-3 text-sm font-medium text-danger transition-colors hover:border-danger hover:bg-[rgba(239,68,68,0.08)] disabled:cursor-not-allowed disabled:opacity-50"
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
