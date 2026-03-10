import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { ReactNode } from 'react'

export interface SceneListRailItem {
  id: string
  index: number
  startMs: number
  endMs: number
  previewUrl: string | null
}

export interface SceneListRailProps {
  items: SceneListRailItem[]
  selectedIndex: number | null
  onSelect: (index: number) => void
  variant?: 'workspace' | 'review'
  density?: 'comfortable' | 'compact'
  isPlaying?: boolean
  enableAutoScrollOnSelection?: boolean
  autoScrollTrigger?: 'always' | 'playing'
  showDurationBadge?: boolean
  showFooterTotalDuration?: boolean
  manualScrollCooldownMs?: number
  emptyText?: string
  listTestId?: string
  formatTimeLabel?: (ms: number) => string
  onPreviewError?: (item: SceneListRailItem) => void
  forceCenterKey?: number
  headerAction?: ReactNode
}

function defaultFormatTimeLabel(ms: number): string {
  const totalSec = Math.floor(ms / 1000)
  const h = Math.floor(totalSec / 3600)
  const m = Math.floor((totalSec % 3600) / 60)
  const s = totalSec % 60

  if (h > 0) {
    return `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
  }

  return `${m}:${String(s).padStart(2, '0')}`
}

export function SceneListRail({
  items,
  selectedIndex,
  onSelect,
  variant = 'workspace',
  density = 'comfortable',
  isPlaying = false,
  enableAutoScrollOnSelection = false,
  autoScrollTrigger = 'playing',
  showDurationBadge = true,
  showFooterTotalDuration = true,
  manualScrollCooldownMs = 3000,
  emptyText = '当前没有匹配镜头',
  listTestId,
  formatTimeLabel = defaultFormatTimeLabel,
  onPreviewError,
  forceCenterKey,
  headerAction,
}: SceneListRailProps) {
  const [failedPreviewIds, setFailedPreviewIds] = useState<Set<string>>(new Set())
  const scrollContainerRef = useRef<HTMLDivElement>(null)
  const itemRefs = useRef(new Map<number, HTMLDivElement>())
  const manualOverrideUntilRef = useRef(0)
  const programmaticScrollUntilRef = useRef(0)

  const markManualOverride = useCallback(() => {
    if (manualScrollCooldownMs <= 0) {
      manualOverrideUntilRef.current = 0
      return
    }
    manualOverrideUntilRef.current = Date.now() + manualScrollCooldownMs
  }, [manualScrollCooldownMs])

  const markProgrammaticScroll = useCallback(() => {
    programmaticScrollUntilRef.current = Date.now() + 500
  }, [])

  const scrollIndexToCenter = useCallback(
    (index: number, behavior: ScrollBehavior = 'smooth') => {
      const container = scrollContainerRef.current
      const item = itemRefs.current.get(index)
      if (!container || !item) {
        return false
      }

      const targetScrollTop = item.offsetTop - container.clientHeight / 2 + item.clientHeight / 2
      markProgrammaticScroll()
      container.scrollTo({ top: targetScrollTop, behavior })
      return true
    },
    [markProgrammaticScroll]
  )

  useEffect(() => {
    setFailedPreviewIds((previous) => {
      if (previous.size === 0) {
        return previous
      }
      const visibleIds = new Set(items.map((item) => item.id))
      const next = new Set<string>()
      previous.forEach((id) => {
        if (visibleIds.has(id)) {
          next.add(id)
        }
      })
      return next
    })
  }, [items])

  useEffect(() => {
    if (!enableAutoScrollOnSelection || selectedIndex === null) {
      return
    }
    if (autoScrollTrigger === 'playing' && !isPlaying) {
      return
    }
    if (Date.now() < manualOverrideUntilRef.current) {
      return
    }
    scrollIndexToCenter(selectedIndex, 'smooth')
  }, [
    autoScrollTrigger,
    enableAutoScrollOnSelection,
    isPlaying,
    selectedIndex,
    scrollIndexToCenter,
  ])

  useEffect(() => {
    if (forceCenterKey === undefined || selectedIndex === null) {
      return
    }
    manualOverrideUntilRef.current = 0
    scrollIndexToCenter(selectedIndex, 'smooth')
  }, [forceCenterKey, selectedIndex, scrollIndexToCenter])

  const totalDurationMs = useMemo(
    () => (items.length > 0 ? items[items.length - 1].endMs : 0),
    [items]
  )
  const isCompact = density === 'compact'
  const isReviewVariant = variant === 'review'

  return (
    <div className="sc-panel flex h-full flex-col rounded-xl p-2.5">
      <div className="sc-surface mb-2 rounded-lg px-2.5 py-2 text-xs">
        <div className="flex items-start justify-between gap-2">
          <div>
            <div className="font-semibold text-[var(--sc-text-primary)]">镜头 {items.length}</div>
            <div className="mt-0.5 text-[11px] text-[var(--sc-text-muted)]">
              {isReviewVariant ? '审核视图镜头列表' : '时间轴镜头列表'}
            </div>
          </div>
          {headerAction ? <div className="shrink-0">{headerAction}</div> : null}
        </div>
      </div>

      <div
        ref={scrollContainerRef}
        onScroll={() => {
          if (Date.now() < programmaticScrollUntilRef.current) {
            return
          }
          markManualOverride()
        }}
        onWheel={markManualOverride}
        onTouchMove={markManualOverride}
        data-testid={listTestId}
        className="relative min-h-0 flex-1 overflow-y-auto pr-1"
      >
        <div className={`relative ${isCompact ? 'space-y-2' : 'space-y-2.5'}`}>
          {items.length > 0 ? (
            <span className="pointer-events-none absolute bottom-0 left-[10px] top-0 w-px bg-[var(--sc-border-strong)]" />
          ) : null}

          {items.map((item) => {
            const selected = selectedIndex === item.index
            const hasPreview = Boolean(item.previewUrl) && !failedPreviewIds.has(item.id)
            const durationSec = ((item.endMs - item.startMs) / 1000).toFixed(1)

            return (
              <div
                key={item.id}
                ref={(element) => {
                  if (element) {
                    itemRefs.current.set(item.index, element)
                  } else {
                    itemRefs.current.delete(item.index)
                  }
                }}
                className={`flex items-stretch ${isCompact ? 'gap-1.5' : 'gap-2'}`}
                onClick={() => onSelect(item.index)}
                role="button"
                tabIndex={0}
                onKeyDown={(event) => {
                  if (event.key === 'Enter' || event.key === ' ') {
                    event.preventDefault()
                    onSelect(item.index)
                  }
                }}
              >
                <div className="relative flex w-5 shrink-0 justify-center">
                  <span
                    className={`relative z-10 mt-3 h-3.5 w-3.5 rounded-full border-2 transition-colors ${
                      selected
                        ? 'border-[var(--sc-accent)] bg-[var(--sc-accent)] shadow-[0_0_0_3px_var(--sc-accent-soft)]'
                        : 'border-[var(--sc-border-strong)] bg-[var(--sc-bg-panel)]'
                    }`}
                  />
                </div>

                <div
                  className={`flex-1 rounded-[10px] border transition-[border-color,background-color,box-shadow] ${
                    selected
                      ? 'border-[var(--sc-accent)] bg-[var(--sc-accent-soft)] shadow-[inset_0_0_0_1px_var(--sc-accent-inset-ring)]'
                      : 'border-[var(--sc-border-subtle)] bg-[var(--sc-bg-surface)] hover:bg-[var(--sc-bg-elevated)]'
                  }`}
                >
                  <div
                    className={`relative aspect-[8/5] w-full overflow-hidden rounded-md border ${
                      selected
                        ? 'border-[var(--sc-accent)] bg-[var(--sc-accent-soft)]'
                        : 'border-[var(--sc-border-subtle)] bg-[var(--sc-bg-contrast)]'
                    } ${isCompact ? 'p-1' : 'p-1.5'}`}
                  >
                    {hasPreview ? (
                      <img
                        src={item.previewUrl!}
                        alt={`镜头 ${item.index + 1}`}
                        loading="lazy"
                        className="h-full w-full object-cover"
                        onError={() => {
                          setFailedPreviewIds((previous) => {
                            const next = new Set(previous)
                            next.add(item.id)
                            return next
                          })
                          onPreviewError?.(item)
                        }}
                      />
                    ) : (
                      <div className="flex h-full w-full items-center justify-center text-[10px] text-[var(--sc-text-muted)]">
                        无预览
                      </div>
                    )}

                    <span className="absolute left-2 top-2 rounded bg-black/65 px-1.5 py-0.5 text-xs font-semibold text-white">
                      #{item.index + 1}
                    </span>
                    <span className="absolute bottom-2 left-2 rounded bg-black/65 px-1.5 py-0.5 text-[11px] text-white/95">
                      {formatTimeLabel(item.startMs)} - {formatTimeLabel(item.endMs)}
                    </span>
                    {showDurationBadge ? (
                      <span className="absolute bottom-2 right-2 rounded bg-black/65 px-1.5 py-0.5 text-[11px] text-white/95">
                        {durationSec}s
                      </span>
                    ) : null}
                  </div>
                </div>
              </div>
            )
          })}

          {items.length === 0 ? (
            <div className="mx-1 rounded-md border border-[var(--sc-border-subtle)] bg-[var(--sc-bg-surface)] px-3 py-4 text-center text-xs text-[var(--sc-text-muted)]">
              {emptyText}
            </div>
          ) : null}
        </div>
      </div>

      {showFooterTotalDuration ? (
        <div className="mt-2 border-t border-[var(--sc-border-subtle)] px-1 pt-1.5 text-[11px] text-[var(--sc-text-muted)]">
          总时长 {formatTimeLabel(totalDurationMs)}
        </div>
      ) : null}
    </div>
  )
}
