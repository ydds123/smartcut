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
  const suspectCount = task.suspectSegments?.length ?? 0
  const qualityModeLabel = '手动参数'

  const previewUrl = resolveAssetUrl(task.previewThumbnailPath ?? null)
  const isBusy = isProcessing || isDeleting

  return (
    <div
      className={`grid grid-cols-[32px_2.8fr_1.2fr_0.6fr_0.9fr_1fr] items-center gap-x-3 border-b border-[#edf0f5] px-3 py-2.5 transition-colors hover:bg-[#f7f9fc] ${
        selected ? 'bg-[#f3f6ff]' : 'bg-white'
      }`}
    >
      <div className="flex items-center justify-center">
        <Checkbox
          checked={selected}
          onChange={(event) => onSelectChange(event.target.checked)}
          aria-label={`选择任务 ${task.displayName}`}
        />
      </div>

      <div className="min-w-0">
        <div className="flex min-w-0 items-center gap-3">
        <div className="h-[45px] w-20 flex-shrink-0 overflow-hidden rounded-md border border-[#e5e8ef] bg-[#f3f5f9]">
          {previewUrl ? (
            <img
              src={previewUrl}
              alt={task.displayName}
              className="h-full w-full object-cover"
              loading="lazy"
            />
          ) : (
            <div className="flex h-full w-full items-center justify-center text-[#99a2b3]">
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
          <div className="truncate text-sm font-semibold text-[#1f2329]" title={task.displayName}>
            {task.displayName}
          </div>
          <div className="mt-0.5 flex items-center gap-2 text-xs text-[#7b8495]">
            <span>{formatFileSize(task.fileSize)}</span>
            {liveStatus === 'COMPLETED' && (
              <>
                <span>·</span>
                <span>{qualityModeLabel}</span>
                <span>·</span>
                <span className={suspectCount > 0 ? 'text-[#cf5c36]' : 'text-[#4f7f3f]'}>
                  疑点 {suspectCount}
                </span>
              </>
            )}
          </div>
        </div>
        </div>
      </div>

      <div className="min-w-0 text-xs">
        <StatusLabel status={liveStatus} className="text-xs" />
        {showProgress && (
          <div className="mt-1 flex items-center gap-2">
            <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-[#e8edf7]">
              <div
                className="h-full rounded-full bg-[#4a78ff] transition-all duration-300"
                style={{ width: `${displayProgress}%` }}
              />
            </div>
            <span className="w-11 text-right text-xs tabular-nums text-[#556074]">
              {displayProgress.toFixed(0)}%
            </span>
          </div>
        )}
      </div>

      <div className="text-xs text-[#4e5969]">
        {shotsCount ?? '--'}
      </div>

      <div className="text-xs text-[#6b7383]">
        {formatUploadTime(task.createdAt)}
      </div>

      <div className="min-w-0 text-xs" onClick={(event) => event.stopPropagation()}>
        <div className="flex items-center gap-3 whitespace-nowrap text-[#1f2329]">
          {liveStatus === 'PENDING' && (
            <>
              <button
                type="button"
                onClick={() => onProcess(task.id)}
                disabled={isBusy}
                className="font-medium text-[#2557d6] transition-colors hover:text-[#1d46ad] disabled:cursor-not-allowed disabled:text-[#9aa3b5]"
              >
                直接处理
              </button>
              <button
                type="button"
                onClick={() => onStartReview?.(task.id)}
                disabled={isBusy}
                className="font-medium text-[#2557d6] transition-colors hover:text-[#1d46ad] disabled:cursor-not-allowed disabled:text-[#9aa3b5]"
              >
                检测并审核
              </button>
              <button
                type="button"
                onClick={() => onDelete(task.id)}
                disabled={isBusy}
                className="font-medium text-[#e04b59] transition-colors hover:text-[#c03d49] disabled:cursor-not-allowed disabled:text-[#9aa3b5]"
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
              className="font-medium text-[#e04b59] transition-colors hover:text-[#c03d49] disabled:cursor-not-allowed disabled:text-[#9aa3b5]"
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
                className="font-medium text-[#2557d6] transition-colors hover:text-[#1d46ad] disabled:cursor-not-allowed disabled:text-[#9aa3b5]"
              >
                查看并编辑
              </button>
              <button
                type="button"
                onClick={() => onDelete(task.id)}
                disabled={isBusy}
                className="font-medium text-[#e04b59] transition-colors hover:text-[#c03d49] disabled:cursor-not-allowed disabled:text-[#9aa3b5]"
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
              className="font-medium text-[#2557d6] transition-colors hover:text-[#1d46ad] disabled:cursor-not-allowed disabled:text-[#9aa3b5]"
            >
              查看工作台
            </button>
          )}

          {liveStatus === 'COMPLETED' && (
            <button
              type="button"
              onClick={() => onViewResult(task.id)}
              disabled={isBusy}
              className="font-medium text-[#2557d6] transition-colors hover:text-[#1d46ad] disabled:cursor-not-allowed disabled:text-[#9aa3b5]"
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
                className="font-medium text-[#2557d6] transition-colors hover:text-[#1d46ad] disabled:cursor-not-allowed disabled:text-[#9aa3b5]"
              >
                查看详情
              </button>
              <button
                type="button"
                onClick={() => onDelete(task.id)}
                disabled={isBusy}
                className="font-medium text-[#e04b59] transition-colors hover:text-[#c03d49] disabled:cursor-not-allowed disabled:text-[#9aa3b5]"
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
