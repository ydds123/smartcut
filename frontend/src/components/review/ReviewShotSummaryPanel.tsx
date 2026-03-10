import { useMemo, useState } from 'react'
import type { ReviewScene } from '@/types/task'
import { SceneListRail, type SceneListRailItem } from '@/components/shared/SceneListRail'
import { backendBase, formatMs } from './reviewUtils'

interface ReviewShotSummaryPanelProps {
  taskId: string
  scenes: ReviewScene[]
  selectedIndex: number | null
  isPlaying: boolean
  onSelect: (index: number) => void
}

function frameUrl(taskId: string, ms: number): string {
  return `${backendBase}/api/tasks/${taskId}/frame?t=${ms}`
}

export function ReviewShotSummaryPanel({
  taskId,
  scenes,
  selectedIndex,
  isPlaying,
  onSelect,
}: ReviewShotSummaryPanelProps) {
  const [forceCenterKey, setForceCenterKey] = useState(0)

  const items = useMemo<SceneListRailItem[]>(
    () =>
      scenes.map((scene, index) => {
        const middleMs = Math.max(scene.startMs, Math.floor((scene.startMs + scene.endMs) / 2))
        return {
          id: `review-${index}-${scene.startMs}-${scene.endMs}`,
          index,
          startMs: scene.startMs,
          endMs: scene.endMs,
          previewUrl: taskId ? frameUrl(taskId, middleMs) : null,
        }
      }),
    [scenes, taskId]
  )

  const canLocateCurrent = selectedIndex !== null && items.length > 0

  const handleLocateCurrent = () => {
    if (!canLocateCurrent) {
      return
    }
    setForceCenterKey((previous) => previous + 1)
  }

  return (
    <SceneListRail
      items={items}
      selectedIndex={selectedIndex}
      onSelect={onSelect}
      variant="review"
      density="comfortable"
      isPlaying={isPlaying}
      enableAutoScrollOnSelection
      autoScrollTrigger="always"
      manualScrollCooldownMs={2500}
      showDurationBadge
      showFooterTotalDuration
      listTestId="review-scenes-grid"
      formatTimeLabel={formatMs}
      forceCenterKey={forceCenterKey}
      headerAction={(
        <button
          type="button"
          onClick={handleLocateCurrent}
          disabled={!canLocateCurrent}
          className="sc-btn sc-btn-secondary h-7 px-2 text-[11px] disabled:cursor-not-allowed disabled:opacity-50"
        >
          定位当前镜头
        </button>
      )}
    />
  )
}
