import React from 'react'
import type { TaskStatus } from '@/types/task'
import { statusConfig } from '@/styles/design-tokens'

export interface BadgeProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: 'default' | 'success' | 'warning' | 'danger' | 'info'
}

export function Badge({
  className = '',
  variant = 'default',
  children,
  ...props
}: BadgeProps) {
  const variantStyles = {
    default: 'border border-[var(--sc-border-subtle)] bg-[var(--sc-bg-surface)] text-[var(--sc-text-secondary)]',
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
  const typedStatus = status as TaskStatus
  const config = statusConfig[typedStatus]

  if (!config) {
    return <Badge variant="default" className={className}>{status}</Badge>
  }

  return (
    <div
      className={`inline-flex items-center rounded px-2.5 py-0.5 text-xs font-medium ${className}`}
      style={{ color: config.textColor, backgroundColor: config.bgColor }}
    >
      {config.label}
    </div>
  )
}
