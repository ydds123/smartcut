import type { TaskStatus } from '@/types/task'

export interface StatusLabelProps {
  status: TaskStatus
  className?: string
}

interface StatusLabelStyle {
  label: string
  textColor: string
  bgColor: string
  dotColor: string
}

const STATUS_LABEL_CONFIG: Record<TaskStatus, StatusLabelStyle> = {
  PENDING: {
    label: '等待中',
    textColor: 'var(--sc-status-neutral-text)',
    bgColor: 'var(--sc-status-neutral-bg)',
    dotColor: 'var(--sc-status-neutral-dot)',
  },
  QUEUED: {
    label: '排队中',
    textColor: 'var(--sc-status-info-text)',
    bgColor: 'var(--sc-status-info-bg)',
    dotColor: 'var(--sc-status-info-dot)',
  },
  PROCESSING: {
    label: '处理中',
    textColor: 'var(--sc-status-info-text)',
    bgColor: 'var(--sc-status-info-bg)',
    dotColor: 'var(--sc-status-info-dot)',
  },
  COMPLETED: {
    label: '已完成',
    textColor: 'var(--sc-status-success-text)',
    bgColor: 'var(--sc-status-success-bg)',
    dotColor: 'var(--sc-status-success-dot)',
  },
  FAILED: {
    label: '失败',
    textColor: 'var(--sc-status-danger-text)',
    bgColor: 'var(--sc-status-danger-bg)',
    dotColor: 'var(--sc-status-danger-dot)',
  },
  DETECTING: {
    label: '检测中',
    textColor: 'var(--sc-status-info-text)',
    bgColor: 'var(--sc-status-info-bg)',
    dotColor: 'var(--sc-status-info-dot)',
  },
  REVIEW_PENDING: {
    label: '待审核',
    textColor: 'var(--sc-status-warning-text)',
    bgColor: 'var(--sc-status-warning-bg)',
    dotColor: 'var(--sc-status-warning-dot)',
  },
  REVIEW_APPROVED: {
    label: '已确认',
    textColor: 'var(--sc-status-approved-text)',
    bgColor: 'var(--sc-status-approved-bg)',
    dotColor: 'var(--sc-status-approved-dot)',
  },
  SPLITTING: {
    label: '切分中',
    textColor: 'var(--sc-status-info-text)',
    bgColor: 'var(--sc-status-info-bg)',
    dotColor: 'var(--sc-status-info-dot)',
  },
  TIMELINE_READY: {
    label: '切分完成',
    textColor: 'var(--sc-status-success-text)',
    bgColor: 'var(--sc-status-success-bg)',
    dotColor: 'var(--sc-status-success-dot)',
  },
}

export function StatusLabel({ status, className = '' }: StatusLabelProps) {
  const config = STATUS_LABEL_CONFIG[status]

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded px-2 py-0.5 text-small ${className}`}
      style={{ color: config.textColor, backgroundColor: config.bgColor }}
    >
      <span
        className="w-1.5 h-1.5 rounded-full"
        style={{ backgroundColor: config.dotColor }}
      />
      {config.label}
    </span>
  )
}
