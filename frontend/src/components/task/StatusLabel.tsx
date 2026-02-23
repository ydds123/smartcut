import type { TaskStatus } from '@/types/task'

export interface StatusLabelProps {
  status: TaskStatus
  className?: string
}

export function StatusLabel({ status, className = '' }: StatusLabelProps) {
  const config = {
    PENDING: {
      label: '等待中',
      textColor: '#b4bdd0',
      bgColor: 'rgba(180, 189, 208, 0.14)',
      dotColor: '#9aa4ba',
    },
    QUEUED: {
      label: '排队中',
      textColor: '#9cc0ff',
      bgColor: 'rgba(91, 140, 255, 0.16)',
      dotColor: '#6e9cff',
    },
    PROCESSING: {
      label: '处理中',
      textColor: '#9cc0ff',
      bgColor: 'rgba(91, 140, 255, 0.16)',
      dotColor: '#5b8cff',
    },
    COMPLETED: {
      label: '已完成',
      textColor: '#a7ddb5',
      bgColor: 'rgba(82, 176, 113, 0.16)',
      dotColor: '#65c083',
    },
    FAILED: {
      label: '失败',
      textColor: '#ffb8bf',
      bgColor: 'rgba(244, 95, 108, 0.16)',
      dotColor: '#f45f6c',
    },
    DETECTING: {
      label: '检测中',
      textColor: '#9cc0ff',
      bgColor: 'rgba(91, 140, 255, 0.16)',
      dotColor: '#6e9cff',
    },
    REVIEW_PENDING: {
      label: '待审核',
      textColor: '#f6ca79',
      bgColor: 'rgba(230, 166, 62, 0.16)',
      dotColor: '#f0b24c',
    },
    REVIEW_APPROVED: {
      label: '已确认',
      textColor: '#98d7de',
      bgColor: 'rgba(70, 170, 178, 0.16)',
      dotColor: '#65bdc6',
    },
    SPLITTING: {
      label: '切分中',
      textColor: '#9cc0ff',
      bgColor: 'rgba(91, 140, 255, 0.16)',
      dotColor: '#5b8cff',
    },
    TIMELINE_READY: {
      label: '切分完成',
      textColor: '#a7ddb5',
      bgColor: 'rgba(82, 176, 113, 0.16)',
      dotColor: '#65c083',
    },
  }[status as TaskStatus]

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
