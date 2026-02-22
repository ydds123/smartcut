import { useEffect, useMemo, useRef, useState } from 'react'
import type { ReviewScene } from '@/types/task'
import { backendBase, formatMs } from './reviewUtils'

interface ReviewShotSummaryPanelProps {
  taskId: string
  scenes: ReviewScene[]
  selectedIndex: number | null
  isPlaying: boolean
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
  isPlaying,
  onSelect,
}: ReviewShotSummaryPanelProps) {
  const [failedThumbIndexes, setFailedThumbIndexes] = useState<Set<number>>(new Set())

  const scrollContainerRef = useRef<HTMLDivElement>(null)
  const itemRefs = useRef(new Map<number, HTMLDivElement>())
  const lastManualMs = useRef(0)

  const visibleEntries = useMemo<SceneEntry[]>(
    () => scenes.map((scene, index) => ({ scene, index })),
    [scenes]
  )

  const handleThumbError = (index: number) => {
    setFailedThumbIndexes((previous) => {
      const next = new Set(previous)
      next.add(index)
      return next
    })
  }

  useEffect(() => {
    if (!isPlaying) return
    if (selectedIndex === null) return
    if (Date.now() - lastManualMs.current < 3000) return

    const container = scrollContainerRef.current
    const item = itemRefs.current.get(selectedIndex)
    if (!container || !item) return

    const targetScrollTop = item.offsetTop - container.clientHeight / 2 + item.clientHeight / 2
    container.scrollTo({ top: targetScrollTop, behavior: 'smooth' })
  }, [selectedIndex, isPlaying])

  return (
    <div className="flex h-full flex-col border border-[#27272a] bg-[#09090b] p-2">
      <div className="mb-2 rounded-md border border-[#27272a] bg-[#18181b] px-2 py-1.5 text-xs text-[#71717a]">
        <div className="font-medium text-[#d4d4d8]">镜头 {scenes.length}</div>
      </div>

      <div
        ref={scrollContainerRef}
        onScroll={() => { lastManualMs.current = Date.now() }}
        data-testid="review-scenes-grid"
        className="relative min-h-0 flex-1 overflow-y-auto pr-0.5"
      >
        <div className="relative space-y-2">
          {visibleEntries.length > 0 ? (
            <span className="pointer-events-none absolute bottom-0 left-[10px] top-0 w-px bg-[#3f3f46]" />
          ) : null}
          {visibleEntries.map(({ scene, index }) => {
            const durationSec = ((scene.endMs - scene.startMs) / 1000).toFixed(1)
            const selected = selectedIndex === index
            const hasThumb = taskId && !failedThumbIndexes.has(index)
            const middleMs = Math.max(scene.startMs, Math.floor((scene.startMs + scene.endMs) / 2))

            return (
              <div
                key={`${scene.startMs}-${scene.endMs}-${index}`}
                ref={(el) => {
                  if (el) itemRefs.current.set(index, el)
                  else itemRefs.current.delete(index)
                }}
                className="flex items-stretch gap-2"
                onClick={() => {
                  lastManualMs.current = Date.now()
                  onSelect(index)
                }}
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
                      selected ? 'border-[#2f8cff] bg-[#2f8cff]' : 'border-[#2f8cff] bg-[#09090b]'
                    }`}
                  />
                </div>

                <div
                  className={`flex-1 rounded-[10px] border p-1.5 transition-colors ${
                    selected
                      ? 'border-[#2f8cff] bg-[rgba(47,140,255,0.12)] shadow-[inset_0_0_0_1px_rgba(47,140,255,0.2)]'
                      : 'border-[#27272a] bg-[#18181b] hover:bg-[#1c1c1f]'
                  }`}
                >
                  <div className="relative aspect-[8/5] w-full overflow-hidden rounded-md border border-[#27272a] bg-[#0f0f0f]">
                    {hasThumb ? (
                      <img
                        src={frameUrl(taskId, middleMs)}
                        alt={`镜头 ${index + 1}`}
                        loading="lazy"
                        className="h-full w-full object-cover"
                        onError={() => handleThumbError(index)}
                      />
                    ) : (
                      <div className="flex h-full w-full items-center justify-center text-[10px] text-[#71717a]">
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
            <div className="mx-1 rounded-md border border-[#27272a] bg-[#18181b] px-3 py-4 text-center text-xs text-[#71717a]">
              当前没有匹配镜头
            </div>
          ) : null}
        </div>
      </div>

      <div className="mt-2 border-t border-[#27272a] px-1 pt-1.5 text-[11px] text-[#71717a]">
        总时长 {scenes.length > 0 ? formatMs(scenes[scenes.length - 1].endMs) : formatMs(0)}
      </div>
    </div>
  )
}
