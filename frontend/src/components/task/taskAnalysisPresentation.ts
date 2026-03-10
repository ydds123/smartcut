import type { AnalysisRunStatus } from '@/types/analysis'

export interface TaskAnalysisPresentation {
  label: string
  textColor: string
  bgColor: string
  borderColor: string
  canOpen: boolean
}

function createPresentation(
  label: string,
  tone: 'info' | 'success' | 'danger' | 'warning',
  canOpen = false
): TaskAnalysisPresentation {
  return {
    label,
    textColor: `var(--sc-status-${tone}-text)`,
    bgColor: `var(--sc-status-${tone}-bg)`,
    borderColor: `var(--sc-status-${tone}-dot)`,
    canOpen,
  }
}

export function getTaskAnalysisPresentation(
  status: AnalysisRunStatus | undefined,
  isReady = true
): TaskAnalysisPresentation {
  if (!isReady) {
    return {
      label: '--',
      textColor: 'var(--sc-text-muted)',
      bgColor: 'transparent',
      borderColor: 'var(--sc-border-subtle)',
      canOpen: false,
    }
  }

  switch (status) {
    case 'NOT_CONFIGURED':
      return createPresentation('未配置', 'warning')
    case 'QUEUED':
      return createPresentation('排队中', 'info')
    case 'RUNNING':
      return createPresentation('分析中', 'info')
    case 'SUCCEEDED':
      return createPresentation('已完成', 'success', true)
    case 'FAILED':
      return createPresentation('失败', 'danger')
    case 'NOT_STARTED':
    default:
      return createPresentation('未开始', 'warning')
  }
}
