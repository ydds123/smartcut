import type { TaskAnalysisLatest } from '@/types/analysis'

interface StoryIntroModalProps {
  isOpen: boolean
  isLoading: boolean
  data: TaskAnalysisLatest | null | undefined
  isRetrying: boolean
  onClose: () => void
  onRetry: () => Promise<void>
}

function renderContent(
  data: TaskAnalysisLatest | null | undefined,
  isLoading: boolean,
  isRetrying: boolean,
  onRetry: () => Promise<void>
) {
  if (isLoading) {
    return <div className="text-sm text-[var(--sc-text-muted)]">加载分析状态中...</div>
  }

  if (!data || data.status === 'NOT_CONFIGURED') {
    return (
      <div className="space-y-2">
        <p className="text-sm text-[var(--sc-text-secondary)]">
          当前尚未完成分析配置，无法发起“故事介绍”分析。
        </p>
        <p className="text-xs text-[var(--sc-text-muted)]">
          请先在任务页打开“分析设置”，确认 API Key 已就绪并保存提示词。
        </p>
      </div>
    )
  }

  if (data.status === 'QUEUED' || data.status === 'RUNNING') {
    return (
      <div className="space-y-3">
        <p className="text-sm text-[var(--sc-text-secondary)]">正在分析中，请稍候...</p>
        <div className="h-2 w-full overflow-hidden rounded-full bg-[var(--sc-bg-contrast)]">
          <div className="h-full w-1/2 animate-pulse rounded-full bg-[var(--sc-accent)]" />
        </div>
      </div>
    )
  }

  if (data.status === 'FAILED') {
    return (
      <div className="space-y-3">
        <div className="rounded border border-[var(--sc-danger)]/30 bg-[var(--sc-danger)]/5 px-3 py-2 text-sm text-[var(--sc-danger)]">
          {data.errorMessage || '分析失败，请重试'}
        </div>
        <button
          type="button"
          onClick={() => {
            void onRetry()
          }}
          disabled={isRetrying}
          className="sc-btn sc-btn-primary h-8 px-3"
        >
          {isRetrying ? '重试中...' : '重试分析'}
        </button>
      </div>
    )
  }

  if (data.status === 'NOT_STARTED') {
    return (
      <div className="space-y-3">
        <p className="text-sm text-[var(--sc-text-secondary)]">尚未生成故事介绍分析结果。</p>
        <button
          type="button"
          onClick={() => {
            void onRetry()
          }}
          disabled={isRetrying}
          className="sc-btn sc-btn-primary h-8 px-3"
        >
          {isRetrying ? '提交中...' : '立即分析'}
        </button>
      </div>
    )
  }

  return (
    <div className="space-y-3">
      {data.summary ? (
        <div className="rounded border border-[var(--sc-border-subtle)] bg-[var(--sc-bg-contrast)] px-3 py-2 text-xs text-[var(--sc-text-secondary)]">
          {data.summary}
        </div>
      ) : null}
      <pre className="max-h-[55vh] overflow-auto whitespace-pre-wrap rounded border border-[var(--sc-border-subtle)] bg-[var(--sc-bg-contrast)] p-3 text-sm leading-6 text-[var(--sc-text-primary)]">
        {data.storyIntroMarkdown || '模型未返回可展示文本'}
      </pre>
    </div>
  )
}

export function StoryIntroModal({
  isOpen,
  isLoading,
  data,
  isRetrying,
  onClose,
  onRetry,
}: StoryIntroModalProps) {
  if (!isOpen) {
    return null
  }

  return (
    <div className="fixed inset-0 z-[90] flex items-center justify-center bg-[var(--sc-modal-overlay)] p-4">
      <div className="sc-modal-shell flex max-h-[86vh] w-full max-w-4xl flex-col overflow-hidden">
        <div className="sc-modal-header flex items-center justify-between">
          <h3 className="text-sm font-semibold text-[var(--sc-text-primary)]">故事介绍</h3>
          <button type="button" onClick={onClose} className="sc-btn sc-btn-ghost h-7 px-2">
            关闭
          </button>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto px-5 py-4">
          {renderContent(data, isLoading, isRetrying, onRetry)}
        </div>
      </div>
    </div>
  )
}
