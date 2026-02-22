import type { TaskStatus } from '@/types/task'
import { statusConfig } from '@/styles/design-tokens'

export interface StatusLabelProps {
  status: TaskStatus
  className?: string
}

/**
 * 飞书风格状态标签
 *
 * 特性：
 * - 圆点指示器
 * - 颜色编码
 * - 飞书风格配色
 */
export function StatusLabel({ status, className = '' }: StatusLabelProps) {
  const config = statusConfig[status]

  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-small ${config.textColor} ${config.bgColor} ${className}`}
    >
      <span className={`w-1.5 h-1.5 rounded-full ${config.dotColor}`} />
      {config.label}
    </span>
  )
}
