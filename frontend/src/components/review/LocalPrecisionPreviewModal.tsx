import type { LocalPrecisionProposal, ReviewScene } from '@/types/task'
import { formatMsAdaptive } from './reviewUtils'

interface LocalPrecisionPreviewModalProps {
  proposal: LocalPrecisionProposal | null
  isApplying: boolean
  onApply: () => void
  onClose: () => void
}

function SceneList({
  scenes,
  emptyText,
}: {
  scenes: ReviewScene[]
  emptyText: string
}) {
  if (scenes.length === 0) {
    return (
      <div className="rounded-md border border-dashed border-[var(--sc-border-subtle)] px-3 py-4 text-sm text-[var(--sc-text-muted)]">
        {emptyText}
      </div>
    )
  }

  return (
    <div className="space-y-2">
      {scenes.map((scene, index) => (
        <div
          key={`${scene.startMs}-${scene.endMs}-${index}`}
          className="rounded-md border border-[var(--sc-border-subtle)] bg-[var(--sc-bg-panel)] px-3 py-2"
        >
          <div className="text-sm font-medium text-[var(--sc-text-primary)]">镜头 {index + 1}</div>
          <div className="mt-1 text-xs text-[var(--sc-text-secondary)]">
            {formatMsAdaptive(scene.startMs)} - {formatMsAdaptive(scene.endMs)}
          </div>
        </div>
      ))}
    </div>
  )
}

export function LocalPrecisionPreviewModal({
  proposal,
  isApplying,
  onApply,
  onClose,
}: LocalPrecisionPreviewModalProps) {
  if (!proposal) {
    return null
  }

  const { originalScenes, proposedScenes, targetRange } = proposal

  return (
    <div className="fixed inset-0 z-[75] flex items-center justify-center bg-[var(--sc-modal-overlay)] p-4">
      <div className="sc-modal-shell flex max-h-[86vh] w-full max-w-5xl flex-col overflow-hidden">
        <div className="border-b border-[var(--sc-border-subtle)] px-5 py-4">
          <h3 className="text-base font-semibold text-[var(--sc-text-primary)]">局部高精度预览</h3>
          <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-[var(--sc-text-secondary)]">
            <span className="sc-tag sc-tag-warn">原局部镜头 {originalScenes.length}</span>
            <span className="sc-tag sc-tag-accent">新局部镜头 {proposedScenes.length}</span>
            <span>
              时间范围 {formatMsAdaptive(targetRange.startMs)} - {formatMsAdaptive(targetRange.endMs)}
            </span>
            <span>
              镜头窗口 {targetRange.startIndex + 1} - {targetRange.endIndex + 1}
            </span>
          </div>
        </div>

        <div className="grid flex-1 gap-4 overflow-y-auto px-5 py-4 md:grid-cols-2">
          <div className="min-h-0">
            <h4 className="mb-3 text-sm font-semibold text-[var(--sc-text-primary)]">原方案</h4>
            <SceneList scenes={originalScenes} emptyText="当前窗口没有原始镜头数据" />
          </div>

          <div className="min-h-0">
            <h4 className="mb-3 text-sm font-semibold text-[var(--sc-text-primary)]">新方案</h4>
            <SceneList scenes={proposedScenes} emptyText="高精度未返回可应用镜头" />
          </div>
        </div>

        <div className="flex items-center justify-end gap-2 border-t border-[var(--sc-border-subtle)] px-5 py-4">
          <button
            type="button"
            onClick={onClose}
            disabled={isApplying}
            className="sc-btn sc-btn-secondary h-8 px-3"
          >
            取消
          </button>
          <button
            type="button"
            onClick={onApply}
            disabled={isApplying}
            className="sc-btn sc-btn-primary h-8 px-3"
          >
            {isApplying ? '应用中...' : '应用到当前稿'}
          </button>
        </div>
      </div>
    </div>
  )
}
