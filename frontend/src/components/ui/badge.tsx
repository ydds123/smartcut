import React from 'react'

export interface BadgeProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: 'default' | 'success' | 'warning' | 'danger' | 'info'
}

const statusMap: Record<
  string,
  { variant: 'success' | 'warning' | 'danger' | 'info' | 'default'; label: string }
> = {
  PENDING: { variant: 'default', label: '待处理' },
  QUEUED: { variant: 'info', label: '队列中' },
  PROCESSING: { variant: 'info', label: '处理中' },
  COMPLETED: { variant: 'success', label: '已完成' },
  FAILED: { variant: 'danger', label: '失败' },
  DETECTING: { variant: 'info', label: '检测中' },
  REVIEW_PENDING: { variant: 'warning', label: '待审核' },
  REVIEW_APPROVED: { variant: 'info', label: '已确认' },
  SPLITTING: { variant: 'info', label: '切分中' },
  TIMELINE_READY: { variant: 'success', label: '切分完成' },
}

export function Badge({
  className = '',
  variant = 'default',
  children,
  ...props
}: BadgeProps) {
  const variantStyles = {
    default: 'bg-gray-100 text-gray-600',
    success: 'bg-success-bg text-success-text',
    warning: 'bg-warning-bg text-warning-text',
    danger: 'bg-danger-bg text-danger-text',
    info: 'bg-info-bg text-info-text',
  }

  return (
    <div
      className={`inline-flex items-center rounded px-2.5 py-0.5 text-xs font-medium ${variantStyles[variant]} ${className}`}
      {...props}
    >
      {children}
    </div>
  )
}

/**
 * 状态 Badge（自动映射任务状态）
 */
export interface StatusBadgeProps {
  status: string
  className?: string
}

export function StatusBadge({ status, className = '' }: StatusBadgeProps) {
  const config = statusMap[status] || { variant: 'default' as const, label: status }

  return <Badge variant={config.variant} className={className}>{config.label}</Badge>
}
