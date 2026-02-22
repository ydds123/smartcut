import { useMemo, useState } from 'react'
import type { QualityFlags, ReviewScene, SuspectSegment } from '@/types/task'
import { backendBase, formatMs } from './reviewUtils'

interface ReviewShotSummaryPanelProps {
  taskId: string
  scenes: ReviewScene[]
  selectedIndex: number | null
  qualityFlags?: QualityFlags | null
  suspectSegments?: SuspectSegment[] | null
  onSelect: (index: number) => void
}

interface SceneEntry {
  index: number
  scene: ReviewScene
}

function frameUrl(taskId: string, ms: number): string {
  return `${backendBase}/api/tasks/${taskId}/frame?t=${ms}`
}

export function ReviewShotSummaryPanel({
  taskId,
  scenes,
  selectedIndex,
  qualityFlags,
  suspectSegments,
  onSelect,
}: ReviewShotSummaryPanelProps) {
  const [showSuspectsOnly, setShowSuspectsOnly] = useState(false)
  const [failedThumbIndexes, setFailedThumbIndexes] = useState<Set<number>>(new Set())
  const suspectCount = suspectSegments?.length ?? 0

  const suspectIndexSet = useMemo(() => {
    const segments = suspectSegments ?? []
    return new Set(
      segments
        .map((segment) => segment.sequenceIndex)
        .filter((value) => Number.isFinite(value) && value >= 0)
    )
  }, [suspectSegments])

  const visibleEntries = useMemo<SceneEntry[]>(
    () =>
      scenes
        .map((scene, index) => ({ scene, index }))
        .filter((entry) => !showSuspectsOnly || suspectIndexSet.has(entry.index)),
    [scenes, showSuspectsOnly, suspectIndexSet]
  )

  const handleThumbError = (index: number) => {
    setFailedThumbIndexes((previous) => {
      const next = new Set(previous)
      next.add(index)
      return next
    })
  }

  return (
    <div className="flex h-full flex-col border border-[#e2e7f0] bg-white p-2">
      <div className="mb-2 rounded-md border border-[#e7edf8] bg-[#f7f9fd] px-2 py-1.5 text-xs text-[#5f6a7f]">
        <div className="font-medium text-[#2d3648]">
          镜头 {scenes.length} · 疑点 {suspectCount}
        </div>
        <div className="mt-1 flex items-center justify-between gap-2">
          <span>
            过切: {qualityFlags?.overSegmented ? '是' : '否'} · 漏切: {qualityFlags?.underSegmented ? '是' : '否'}
          </span>
          <button
            type="button"
            onClick={() => setShowSuspectsOnly((value) => !value)}
            className="rounded bg-white px-2 py-0.5 text-[11px] text-[#3864ca] hover:bg-[#eef3ff]"
          >
            {showSuspectsOnly ? '显示全部' : '仅看疑点'}
          </button>
        </div>
      </div>

      <div data-testid="review-scenes-grid" className="relative min-h-0 flex-1 overflow-y-auto pr-0.5">
        <div className="relative space-y-2">
          {visibleEntries.length > 0 ? (
            <span className="pointer-events-none absolute bottom-0 left-[10px] top-0 w-px bg-[#b7d7ff]" />
          ) : null}
          {visibleEntries.map(({ scene, index }) => {
            const durationSec = ((scene.endMs - scene.startMs) / 1000).toFixed(1)
            const selected = selectedIndex === index
            const hasThumb = taskId && !failedThumbIndexes.has(index)
            const middleMs = Math.max(scene.startMs, Math.floor((scene.startMs + scene.endMs) / 2))

            return (
              <div
                key={`${scene.startMs}-${scene.endMs}-${index}`}
                className="flex items-stretch gap-2"
                onClick={() => onSelect(index)}
                role="button"
                tabIndex={0}
                onKeyDown={(event) => {
                  if (event.key === 'Enter' || event.key === ' ') {
                    event.preventDefault()
                    onSelect(index)
                  }
                }}
              >
                <div className="relative flex w-5 shrink-0 justify-center">
                  <span
                    className={`relative z-10 mt-3 h-3.5 w-3.5 rounded-full border-2 ${
                      selected ? 'border-[#2f8cff] bg-[#2f8cff]' : 'border-[#2f8cff] bg-white'
                    }`}
                  />
                </div>

                <div
                  className={`flex-1 rounded-[10px] border p-1.5 transition-colors ${
                    selected
                      ? 'border-[#2f8cff] bg-[#edf5ff] shadow-[inset_0_0_0_1px_rgba(47,140,255,0.2)]'
                      : 'border-[#e5e9f1] bg-white hover:bg-[#f8faff]'
                  }`}
                >
                  <div className="relative aspect-[8/5] w-full overflow-hidden rounded-md border border-[#2f8cff] bg-[#dfe9ff]">
                    {hasThumb ? (
                      <img
                        src={frameUrl(taskId, middleMs)}
                        alt={`镜头 ${index + 1}`}
                        loading="lazy"
                        className="h-full w-full object-cover"
                        onError={() => handleThumbError(index)}
                      />
                    ) : (
                      <div className="flex h-full w-full items-center justify-center text-[10px] text-[#9aa3b5]">
                        无预览
                      </div>
                    )}
                    <span className="absolute left-2 top-2 rounded bg-black/70 px-1.5 py-0.5 text-xs font-semibold text-white">
                      #{index + 1}
                    </span>
                    <span className="absolute bottom-2 left-2 rounded bg-black/70 px-1.5 py-0.5 text-[11px] text-white">
                      {formatMs(scene.startMs)} - {formatMs(scene.endMs)}
                    </span>
                    <span className="absolute bottom-2 right-2 rounded bg-black/70 px-1.5 py-0.5 text-[11px] text-white">
                      {durationSec}s
                    </span>
                  </div>
                </div>
              </div>
            )
          })}

          {visibleEntries.length === 0 ? (
            <div className="mx-1 rounded-md border border-[#e7edf8] bg-[#f7f9fd] px-3 py-4 text-center text-xs text-[#7b869a]">
              当前没有匹配镜头
            </div>
          ) : null}
        </div>
      </div>

      <div className="mt-2 border-t border-[#edf1f6] px-1 pt-1.5 text-[11px] text-[#6f7b90]">
        总时长 {scenes.length > 0 ? formatMs(scenes[scenes.length - 1].endMs) : formatMs(0)}
      </div>
    </div>
  )
}
