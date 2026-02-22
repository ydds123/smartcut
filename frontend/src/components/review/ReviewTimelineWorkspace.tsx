import { forwardRef, useCallback, useEffect, useImperativeHandle, useMemo, useRef, useState } from 'react'
import type { ReviewScene } from '@/types/task'
import { backendBase, clamp, formatMs } from './reviewUtils'

interface ReviewTimelineWorkspaceProps {
  taskId: string
  scenes: ReviewScene[]
  durationMs: number
  playheadMs: number
  isPlaying: boolean
  pixelsPerSecond: number
  minPixelsPerSecond: number
  maxPixelsPerSecond: number
  zoomStepFactor?: number
  onPixelsPerSecondChange: (next: number) => void
  onViewportWidthChange?: (width: number) => void
  onAddBoundary: (ms: number) => void
  onDeleteBoundary: (sceneIndex: number) => void
  onSetPlayhead: (ms: number) => void
}

interface Tick {
  ms: number
  label: string
  major: boolean
}

interface ZoomAnchor {
  anchorMs: number
  viewportX: number
}

interface SceneFrameDescriptor {
  scene: ReviewScene
  index: number
  left: number
  width: number
  times: number[]
}

type TimelinePointerSource = 'content' | 'ruler'

export interface ReviewTimelineWorkspaceHandle {
  prepareExternalZoomAnchorByMs: (ms: number) => void
}

const DEFAULT_ZOOM_STEP_FACTOR = 1.08
const ZOOM_MIN_RANGE_EPSILON = 0.001
const PLAYHEAD_HIT_WIDTH = 14
const PLAYHEAD_HALF_HIT_WIDTH = Math.floor(PLAYHEAD_HIT_WIDTH / 2)

const FRAME_KEY_GRANULARITY_MS = 250
const SPARSE_PREWARM_STEP_MS = 1000
const FRAME_SLOT_MIN_PX = 42
const MAX_FRAMES_PER_SCENE = 90
const MAX_PREFETCH_TIMES = 320
const THUMB_PREFETCH_CONCURRENCY = 6
const THUMB_CACHE_LIMIT = 2000
const PREFETCH_BUFFER_VIEWPORTS = 1

const toFrameKey = (ms: number) => Math.max(0, Math.floor(ms / FRAME_KEY_GRANULARITY_MS) * FRAME_KEY_GRANULARITY_MS)

const resolveZoomExponent = (wheelDeltaY: number) => {
  const magnitude = Math.abs(wheelDeltaY)

  if (magnitude >= 220) {
    return 2.2
  }
  if (magnitude >= 120) {
    return 1.6
  }
  if (magnitude <= 20) {
    return 0.7
  }

  return 1
}

const resolveFrameStepMs = (pps: number) => {
  if (pps >= 150) {
    return 250
  }
  if (pps >= 90) {
    return 500
  }
  if (pps >= 40) {
    return 1000
  }
  return 2000
}

const capEvenly = (values: number[], cap: number) => {
  if (values.length <= cap) {
    return values
  }
  const result: number[] = []
  const step = values.length / cap
  for (let i = 0; i < cap; i += 1) {
    const index = Math.min(values.length - 1, Math.floor(i * step))
    result.push(values[index])
  }
  return result
}

export const ReviewTimelineWorkspace = forwardRef<ReviewTimelineWorkspaceHandle, ReviewTimelineWorkspaceProps>(
function ReviewTimelineWorkspace({
  taskId,
  scenes,
  durationMs,
  playheadMs,
  isPlaying,
  pixelsPerSecond,
  minPixelsPerSecond,
  maxPixelsPerSecond,
  zoomStepFactor = DEFAULT_ZOOM_STEP_FACTOR,
  onPixelsPerSecondChange,
  onViewportWidthChange,
  onAddBoundary,
  onDeleteBoundary,
  onSetPlayhead,
}, ref) {
  const contentRef = useRef<HTMLDivElement>(null)
  const rulerViewportRef = useRef<HTMLDivElement>(null)
  const dragPointerIdRef = useRef<number | null>(null)
  const rulerSeekPointerIdRef = useRef<number | null>(null)
  const pendingZoomAnchorRef = useRef<ZoomAnchor | null>(null)
  const inFlightThumbKeysRef = useRef<Set<number>>(new Set())
  const thumbUsageRef = useRef<Map<number, number>>(new Map())
  const lastManualMs = useRef(0)
  const isProgrammaticScrollRef = useRef(false)

  const [contentViewportWidth, setContentViewportWidth] = useState(0)
  const [scrollLeft, setScrollLeft] = useState(0)
  const [hoveredMs, setHoveredMs] = useState<number | null>(null)
  const [snapLineMs, setSnapLineMs] = useState<number | null>(null)
  const [thumbCache, setThumbCache] = useState<Record<number, string>>({})
  const [isDraggingPlayhead, setIsDraggingPlayhead] = useState(false)
  const [isSeekingByRuler, setIsSeekingByRuler] = useState(false)
  const [dragPlayheadMs, setDragPlayheadMs] = useState<number | null>(null)

  const trackHeight = 84
  const trackY = 20
  const canvasHeight = 160
  const safeMinPixelsPerSecond = Math.max(0.001, minPixelsPerSecond)
  const safeMaxPixelsPerSecond = Math.max(maxPixelsPerSecond, safeMinPixelsPerSecond + ZOOM_MIN_RANGE_EPSILON)
  const safeZoomStepFactor = zoomStepFactor > 1 ? zoomStepFactor : DEFAULT_ZOOM_STEP_FACTOR

  const totalWidth = useMemo(
    () => Math.max(900, Math.round((durationMs / 1000) * pixelsPerSecond)),
    [durationMs, pixelsPerSecond]
  )

  const msToX = useCallback((ms: number) => (durationMs <= 0 ? 0 : (ms / durationMs) * totalWidth), [durationMs, totalWidth])
  const xToMs = useCallback((x: number) => (totalWidth <= 0 ? 0 : Math.round((x / totalWidth) * durationMs)), [durationMs, totalWidth])

  const boundaryMsList = useMemo(() => scenes.slice(1).map((scene) => scene.startMs), [scenes])
  const effectivePlayheadMs = dragPlayheadMs ?? playheadMs
  const densityFrameStepMs = useMemo(() => resolveFrameStepMs(pixelsPerSecond), [pixelsPerSecond])

  useEffect(() => {
    const content = contentRef.current
    if (!content) {
      return
    }

    const refreshViewportWidth = () => setContentViewportWidth(content.clientWidth)
    refreshViewportWidth()

    const observer = new ResizeObserver(refreshViewportWidth)
    observer.observe(content)

    return () => observer.disconnect()
  }, [])

  useEffect(() => {
    if (!onViewportWidthChange || contentViewportWidth <= 0) {
      return
    }
    onViewportWidthChange(contentViewportWidth)
  }, [contentViewportWidth, onViewportWidthChange])

  const setPendingZoomAnchorByViewportX = (viewportX: number) => {
    if (durationMs <= 0 || !contentRef.current) {
      return
    }
    const normalizedViewportX = clamp(viewportX, 0, contentRef.current.clientWidth)
    const anchorX = clamp(normalizedViewportX + scrollLeft, 0, totalWidth)
    pendingZoomAnchorRef.current = { anchorMs: xToMs(anchorX), viewportX: normalizedViewportX }
  }

  useImperativeHandle(ref, () => ({
    prepareExternalZoomAnchorByMs: (ms: number) => {
      if (!contentRef.current || durationMs <= 0) {
        return
      }
      const targetMs = clamp(ms, 0, durationMs)
      const targetX = msToX(targetMs)
      setPendingZoomAnchorByViewportX(targetX - scrollLeft)
    },
  }), [durationMs, msToX, scrollLeft, totalWidth, xToMs])

  useEffect(() => {
    const pendingAnchor = pendingZoomAnchorRef.current
    const content = contentRef.current
    if (!pendingAnchor || !content || durationMs <= 0) {
      return
    }

    const anchorX = msToX(pendingAnchor.anchorMs)
    const rawScrollLeft = anchorX - pendingAnchor.viewportX
    const maxScrollLeft = Math.max(0, totalWidth - content.clientWidth)
    const nextScrollLeft = clamp(Math.round(rawScrollLeft), 0, maxScrollLeft)

    content.scrollLeft = nextScrollLeft
    setScrollLeft(nextScrollLeft)
    pendingZoomAnchorRef.current = null
  }, [durationMs, totalWidth, msToX])

  useEffect(() => {
    if (!isPlaying) return
    if (Date.now() - lastManualMs.current < 3000) return

    const content = contentRef.current
    if (!content || durationMs <= 0) return

    const playheadX = msToX(playheadMs)
    const targetScrollLeft = playheadX - content.clientWidth / 2
    const maxScrollLeft = Math.max(0, totalWidth - content.clientWidth)
    const clamped = Math.max(0, Math.min(targetScrollLeft, maxScrollLeft))

    isProgrammaticScrollRef.current = true
    content.scrollLeft = clamped
    requestAnimationFrame(() => {
      isProgrammaticScrollRef.current = false
    })
  }, [playheadMs, isPlaying, durationMs, msToX, totalWidth])

  const resolveTimelinePosition = (
    clientX: number,
    options: { includePlayhead: boolean; snapEnabled: boolean; source?: TimelinePointerSource }
  ): { targetMs: number; snapMs: number | null } => {
    if (durationMs <= 0) {
      return { targetMs: 0, snapMs: null }
    }

    const source = options.source ?? 'content'
    const sourceElement = source === 'ruler' ? rulerViewportRef.current : contentRef.current
    if (!sourceElement) {
      return { targetMs: 0, snapMs: null }
    }

    const rect = sourceElement.getBoundingClientRect()
    const x = clamp(clientX - rect.left + scrollLeft, 0, totalWidth)
    const candidateMs = xToMs(x)

    if (!options.snapEnabled) {
      return { targetMs: candidateMs, snapMs: null }
    }

    const boundarySnapThreshold = clamp(6 + pixelsPerSecond * 0.025, 7, 12)
    const tickSnapThreshold = clamp(4 + pixelsPerSecond * 0.015, 5, 9)

    const candidates: Array<{ ms: number; thresholdPx: number }> = []
    boundaryMsList.forEach((ms) => candidates.push({ ms, thresholdPx: boundarySnapThreshold }))
    majorTickMs.forEach((ms) => candidates.push({ ms, thresholdPx: tickSnapThreshold }))
    if (options.includePlayhead) {
      candidates.push({ ms: playheadMs, thresholdPx: boundarySnapThreshold })
    }

    let nearestMs: number | null = null
    let nearestDistPx = Number.POSITIVE_INFINITY

    candidates.forEach((candidate) => {
      const distPx = Math.abs(msToX(candidate.ms) - x)
      if (distPx <= candidate.thresholdPx && distPx < nearestDistPx) {
        nearestDistPx = distPx
        nearestMs = candidate.ms
      }
    })

    if (nearestMs !== null) {
      return { targetMs: nearestMs, snapMs: nearestMs }
    }

    return { targetMs: candidateMs, snapMs: null }
  }

  const ticks = useMemo<Tick[]>(() => {
    if (durationMs <= 0) {
      return []
    }

    let intervalSec = 20
    if (pixelsPerSecond >= 160) {
      intervalSec = 1
    } else if (pixelsPerSecond >= 100) {
      intervalSec = 2
    } else if (pixelsPerSecond >= 60) {
      intervalSec = 5
    } else if (pixelsPerSecond >= 30) {
      intervalSec = 10
    }

    const intervalMs = intervalSec * 1000
    const output: Tick[] = []
    for (let ms = 0; ms <= durationMs; ms += intervalMs) {
      output.push({ ms, label: formatMs(ms), major: true })
      const half = ms + intervalMs / 2
      if (half < durationMs) {
        output.push({ ms: half, label: '', major: false })
      }
    }

    return output
  }, [durationMs, pixelsPerSecond])

  const majorTickMs = useMemo(() => ticks.filter((tick) => tick.major).map((tick) => tick.ms), [ticks])

  const sceneFrameDescriptors = useMemo<SceneFrameDescriptor[]>(() => {
    return scenes.map((scene, index) => {
      const left = msToX(scene.startMs)
      const width = Math.max(6, msToX(scene.endMs) - left)
      const sceneDurationMs = Math.max(1, scene.endMs - scene.startMs)
      const maxFramesByWidth = clamp(Math.floor(width / FRAME_SLOT_MIN_PX), 1, MAX_FRAMES_PER_SCENE)
      const densityCount = Math.max(1, Math.ceil(sceneDurationMs / densityFrameStepMs))
      const frameCount = Math.max(1, Math.min(maxFramesByWidth, densityCount))
      const frameInterval = sceneDurationMs / frameCount

      const times: number[] = []
      for (let i = 0; i < frameCount; i += 1) {
        const frameMs = clamp(
          Math.round(scene.startMs + frameInterval * i),
          scene.startMs,
          Math.max(scene.startMs, scene.endMs - 1)
        )
        const key = toFrameKey(frameMs)
        if (!times.includes(key)) {
          times.push(key)
        }
      }

      if (times.length === 0) {
        times.push(toFrameKey(Math.floor((scene.startMs + scene.endMs) / 2)))
      }

      return { scene, index, left, width, times }
    })
  }, [scenes, msToX, densityFrameStepMs])

  const prefetchTimes = useMemo(() => {
    if (durationMs <= 0 || contentViewportWidth <= 0) {
      return [] as number[]
    }

    const visibleStartMs = xToMs(scrollLeft)
    const visibleEndMs = xToMs(scrollLeft + contentViewportWidth)
    const viewportRangeMs = Math.max(1000, visibleEndMs - visibleStartMs)
    const bufferMs = viewportRangeMs * PREFETCH_BUFFER_VIEWPORTS
    const requestStartMs = clamp(visibleStartMs - bufferMs, 0, durationMs)
    const requestEndMs = clamp(visibleEndMs + bufferMs, 0, durationMs)

    const denseTimes: number[] = []
    sceneFrameDescriptors.forEach((descriptor) => {
      const intersects = descriptor.scene.endMs > requestStartMs && descriptor.scene.startMs < requestEndMs
      if (!intersects) {
        return
      }
      descriptor.times.forEach((time) => {
        if (time >= requestStartMs && time <= requestEndMs) {
          denseTimes.push(time)
        }
      })
    })

    denseTimes.sort((a, b) => a - b)
    const denseCapped = capEvenly(denseTimes, Math.floor(MAX_PREFETCH_TIMES * 0.75))

    const sparseTimes: number[] = []
    for (let ms = requestStartMs; ms <= requestEndMs; ms += SPARSE_PREWARM_STEP_MS) {
      sparseTimes.push(toFrameKey(ms))
    }

    const ordered: number[] = []
    const seen = new Set<number>()

    denseCapped.forEach((time) => {
      if (!seen.has(time)) {
        seen.add(time)
        ordered.push(time)
      }
    })

    sparseTimes.forEach((time) => {
      if (ordered.length >= MAX_PREFETCH_TIMES) {
        return
      }
      if (!seen.has(time)) {
        seen.add(time)
        ordered.push(time)
      }
    })

    return ordered
  }, [durationMs, contentViewportWidth, xToMs, scrollLeft, sceneFrameDescriptors])

  useEffect(() => {
    const now = Date.now()
    prefetchTimes.forEach((ms) => {
      thumbUsageRef.current.set(ms, now)
    })
  }, [prefetchTimes])

  const preloadThumbnails = useCallback(async (times: number[]) => {
    const queue = times.filter((time) => !(time in thumbCache) && !inFlightThumbKeysRef.current.has(time))
    if (queue.length === 0) {
      return
    }

    const loaded: Record<number, string> = {}
    let cursor = 0

    const loadOne = (ms: number) => new Promise<boolean>((resolve) => {
      const url = `${backendBase}/api/tasks/${taskId}/frame?t=${ms}`
      const img = new Image()
      img.onload = () => {
        loaded[ms] = url
        resolve(true)
      }
      img.onerror = () => resolve(false)
      img.src = url
    })

    const workerCount = Math.min(THUMB_PREFETCH_CONCURRENCY, queue.length)
    const workers = Array.from({ length: workerCount }, async () => {
      while (cursor < queue.length) {
        const current = queue[cursor]
        cursor += 1
        inFlightThumbKeysRef.current.add(current)
        await loadOne(current)
        inFlightThumbKeysRef.current.delete(current)
      }
    })

    await Promise.all(workers)

    const loadedKeys = Object.keys(loaded)
    if (loadedKeys.length === 0) {
      return
    }

    setThumbCache((prev) => {
      const next = { ...prev, ...loaded }
      const now = Date.now()
      loadedKeys.forEach((keyText) => {
        thumbUsageRef.current.set(Number(keyText), now)
      })

      const keys = Object.keys(next).map(Number)
      if (keys.length <= THUMB_CACHE_LIMIT) {
        return next
      }

      keys.sort((a, b) => (thumbUsageRef.current.get(a) ?? 0) - (thumbUsageRef.current.get(b) ?? 0))
      const pruneCount = keys.length - THUMB_CACHE_LIMIT
      for (let i = 0; i < pruneCount; i += 1) {
        const key = keys[i]
        delete next[key]
        thumbUsageRef.current.delete(key)
      }
      return next
    })
  }, [taskId, thumbCache])

  useEffect(() => {
    void preloadThumbnails(prefetchTimes)
  }, [prefetchTimes, preloadThumbnails])

  const handleTrackClick = (event: React.MouseEvent<HTMLDivElement>) => {
    if (!contentRef.current || durationMs <= 0 || isDraggingPlayhead) {
      return
    }

    const targetMs = snapLineMs ?? resolveTimelinePosition(event.clientX, {
      includePlayhead: true,
      snapEnabled: false,
      source: 'content',
    }).targetMs
    onSetPlayhead(targetMs)
  }

  const handleTrackDoubleClick = (event: React.MouseEvent<HTMLDivElement>) => {
    if (!contentRef.current || durationMs <= 0 || isDraggingPlayhead) {
      return
    }

    const targetMs = snapLineMs ?? resolveTimelinePosition(event.clientX, {
      includePlayhead: true,
      snapEnabled: false,
      source: 'content',
    }).targetMs
    onAddBoundary(targetMs)
  }

  const handleMouseMove = (event: React.MouseEvent<HTMLDivElement>) => {
    if (!contentRef.current || durationMs <= 0 || isDraggingPlayhead || isSeekingByRuler) {
      return
    }

    const resolved = resolveTimelinePosition(event.clientX, {
      includePlayhead: true,
      snapEnabled: true,
      source: 'content',
    })
    setSnapLineMs(resolved.snapMs)
    setHoveredMs(resolved.targetMs)
  }

  const handleWheel = (event: React.WheelEvent<HTMLDivElement>) => {
    if (!(event.ctrlKey || event.metaKey) || durationMs <= 0 || !contentRef.current) {
      return
    }

    if (event.deltaY === 0) {
      return
    }

    event.preventDefault()

    const rect = contentRef.current.getBoundingClientRect()
    const viewportX = clamp(event.clientX - rect.left, 0, rect.width)
    const anchorX = clamp(viewportX + scrollLeft, 0, totalWidth)
    const anchorMs = xToMs(anchorX)
    const zoomExponent = resolveZoomExponent(event.deltaY)
    const zoomFactor = Math.pow(safeZoomStepFactor, zoomExponent)
    const nextPixelsPerSecondRaw =
      event.deltaY < 0 ? pixelsPerSecond * zoomFactor : pixelsPerSecond / zoomFactor
    const nextPixelsPerSecond = clamp(
      Math.round(nextPixelsPerSecondRaw * 100) / 100,
      safeMinPixelsPerSecond,
      safeMaxPixelsPerSecond
    )

    if (nextPixelsPerSecond === pixelsPerSecond) {
      return
    }

    pendingZoomAnchorRef.current = { anchorMs, viewportX }
    onPixelsPerSecondChange(nextPixelsPerSecond)
  }

  const seekWithRulerClientX = (clientX: number) => {
    const resolved = resolveTimelinePosition(clientX, {
      includePlayhead: false,
      snapEnabled: false,
      source: 'ruler',
    })
    setSnapLineMs(null)
    setHoveredMs(resolved.targetMs)
    onSetPlayhead(resolved.targetMs)
  }

  const handleRulerPointerDown = (event: React.PointerEvent<HTMLDivElement>) => {
    if (event.button !== 0 || durationMs <= 0) {
      return
    }

    event.preventDefault()
    event.stopPropagation()
    rulerSeekPointerIdRef.current = event.pointerId
    setIsSeekingByRuler(true)

    const target = event.currentTarget
    if (target.setPointerCapture) {
      target.setPointerCapture(event.pointerId)
    }

    seekWithRulerClientX(event.clientX)
  }

  const handleRulerPointerMove = (event: React.PointerEvent<HTMLDivElement>) => {
    if (!isSeekingByRuler || rulerSeekPointerIdRef.current !== event.pointerId) {
      return
    }
    event.preventDefault()
    seekWithRulerClientX(event.clientX)
  }

  const finishRulerSeek = (event: React.PointerEvent<HTMLDivElement>) => {
    if (rulerSeekPointerIdRef.current !== event.pointerId) {
      return
    }

    const target = event.currentTarget
    if (target.releasePointerCapture && target.hasPointerCapture(event.pointerId)) {
      target.releasePointerCapture(event.pointerId)
    }
    rulerSeekPointerIdRef.current = null
    setIsSeekingByRuler(false)
  }

  const handlePlayheadPointerDown = (event: React.PointerEvent<HTMLDivElement>) => {
    if (event.button !== 0 || durationMs <= 0) {
      return
    }

    event.preventDefault()
    event.stopPropagation()
    dragPointerIdRef.current = event.pointerId
    setIsDraggingPlayhead(true)

    const target = event.currentTarget
    if (target.setPointerCapture) {
      target.setPointerCapture(event.pointerId)
    }

    const resolved = resolveTimelinePosition(event.clientX, {
      includePlayhead: false,
      snapEnabled: true,
      source: 'content',
    })
    setDragPlayheadMs(resolved.targetMs)
    setSnapLineMs(resolved.snapMs)
    setHoveredMs(resolved.targetMs)
    onSetPlayhead(resolved.targetMs)
  }

  const handlePlayheadPointerMove = (event: React.PointerEvent<HTMLDivElement>) => {
    if (!isDraggingPlayhead || dragPointerIdRef.current !== event.pointerId) {
      return
    }

    event.preventDefault()
    const resolved = resolveTimelinePosition(event.clientX, {
      includePlayhead: false,
      snapEnabled: true,
      source: 'content',
    })
    setDragPlayheadMs(resolved.targetMs)
    setSnapLineMs(resolved.snapMs)
    setHoveredMs(resolved.targetMs)
    onSetPlayhead(resolved.targetMs)
  }

  const finishPlayheadDrag = (event: React.PointerEvent<HTMLDivElement>) => {
    if (dragPointerIdRef.current !== event.pointerId) {
      return
    }

    const target = event.currentTarget
    if (target.releasePointerCapture && target.hasPointerCapture(event.pointerId)) {
      target.releasePointerCapture(event.pointerId)
    }

    dragPointerIdRef.current = null
    setIsDraggingPlayhead(false)
    setDragPlayheadMs(null)
    setSnapLineMs(null)
  }

  return (
    <div className="relative grid h-full min-w-0 grid-rows-[32px_minmax(0,1fr)] overflow-hidden bg-[#09090b]">
        <div
          ref={rulerViewportRef}
          className="overflow-hidden border-b border-[#27272a] bg-[#0f0f0f]"
          onPointerDown={handleRulerPointerDown}
          onPointerMove={handleRulerPointerMove}
          onPointerUp={finishRulerSeek}
          onPointerCancel={finishRulerSeek}
          onLostPointerCapture={() => {
            rulerSeekPointerIdRef.current = null
            setIsSeekingByRuler(false)
          }}
        >
          <div
            className="relative h-8"
            style={{ width: totalWidth, marginLeft: -scrollLeft }}
          >
            {ticks.map((tick) => {
              const x = msToX(tick.ms)
              return (
                <div
                  key={`${tick.ms}-${tick.major ? 'major' : 'minor'}`}
                  className="absolute top-0 h-full"
                  style={{ left: x }}
                >
                  <div
                    className="absolute bottom-0 w-px"
                    style={{
                      height: tick.major ? 11 : 6,
                      backgroundColor: tick.major ? '#71717a' : '#3f3f46',
                    }}
                  />
                  {tick.label ? (
                    <span
                      className="absolute left-0 top-1 -translate-x-1/2 whitespace-nowrap text-[10px] text-[#a1a1aa]"
                    >
                      {tick.label}
                    </span>
                  ) : null}
                </div>
              )
            })}
          </div>
        </div>

        <div
          ref={contentRef}
          data-review-timeline-scroll="true"
          className="min-h-0 overflow-auto"
          onScroll={(event) => {
            if (!isProgrammaticScrollRef.current) {
              lastManualMs.current = Date.now()
            }
            setScrollLeft((event.target as HTMLDivElement).scrollLeft)
          }}
          onWheel={handleWheel}
          onMouseMove={handleMouseMove}
          onMouseLeave={() => {
            if (isDraggingPlayhead || isSeekingByRuler) {
              return
            }
            setHoveredMs(null)
            setSnapLineMs(null)
          }}
        >
          <div
            className="relative"
            style={{ width: totalWidth, height: canvasHeight }}
            onClick={handleTrackClick}
            onDoubleClick={handleTrackDoubleClick}
          >
            <div
              className="absolute inset-x-0 rounded-sm border border-[#232326] bg-[#0a1014]"
              style={{ top: trackY, height: trackHeight }}
            >
              {sceneFrameDescriptors.map((descriptor) => {
                const { scene, index, left, width, times } = descriptor
                const sceneDurationMs = Math.max(1, scene.endMs - scene.startMs)
                const active = effectivePlayheadMs >= scene.startMs && effectivePlayheadMs < scene.endMs

                return (
                  <div
                    key={`${scene.startMs}-${scene.endMs}-${index}`}
                    data-review-scene-block={index}
                    className="absolute top-0 overflow-hidden rounded-sm border"
                    style={{
                      left,
                      width,
                      height: trackHeight,
                      borderColor: active ? '#60a5fa' : '#3f3f46',
                      background: 'linear-gradient(180deg,#17171c 0%,#101015 100%)',
                    }}
                  >
                    {times.map((frameMs, frameIndex) => {
                      const frameStartRatio = (frameMs - scene.startMs) / sceneDurationMs
                      const nextFrameMs = times[frameIndex + 1] ?? scene.endMs
                      const frameEndRatio = (nextFrameMs - scene.startMs) / sceneDurationMs
                      const frameLeft = clamp(frameStartRatio, 0, 1) * width
                      const frameWidth = Math.max(8, (clamp(frameEndRatio, 0, 1) - clamp(frameStartRatio, 0, 1)) * width + 1)
                      const thumbUrl = thumbCache[frameMs]

                      return (
                        <div
                          key={`frame-${frameMs}-${frameIndex}`}
                          data-review-frame-slot={frameIndex}
                          data-review-frame-ms={frameMs}
                          className="absolute bottom-0 top-0 overflow-hidden"
                          style={{ left: frameLeft, width: frameWidth }}
                        >
                          {thumbUrl ? (
                            <img
                              src={thumbUrl}
                              alt=""
                              loading="lazy"
                              className="h-full w-full object-cover opacity-70"
                            />
                          ) : (
                            <div className="h-full w-full bg-gradient-to-br from-[#17171d] to-[#111118]" />
                          )}
                        </div>
                      )
                    })}

                    <div className="absolute inset-0 bg-gradient-to-b from-black/8 to-black/18" />

                    <div className="absolute left-1.5 top-1 rounded bg-black/55 px-1 py-0.5 text-[10px] text-white/85">
                      #{index + 1}
                    </div>
                    {width > 70 ? (
                      <div className="absolute bottom-1 left-1.5 rounded bg-black/45 px-1 py-0.5 font-mono text-[10px] text-white/80">
                        {formatMs(scene.startMs)}
                      </div>
                    ) : null}
                  </div>
                )
              })}

              {scenes.slice(1).map((scene, index) => {
                const x = msToX(scene.startMs)
                return (
                  <button
                    key={`boundary-${scene.startMs}-${index}`}
                    type="button"
                    className="absolute top-0 h-full w-[3px] bg-[#f43f5e]"
                    style={{ left: x - 1 }}
                    title={`删除切分点 ${formatMs(scene.startMs)}`}
                    onClick={(event) => {
                      event.stopPropagation()
                      onDeleteBoundary(index + 1)
                    }}
                  />
                )
              })}

              {snapLineMs !== null ? (
                <div
                  className="pointer-events-none absolute top-0 h-full w-[2px] bg-[#8b5cf6] opacity-60 transition-opacity"
                  style={{ left: msToX(snapLineMs) }}
                />
              ) : null}
            </div>

            <div className="absolute right-2 top-1 rounded bg-black/50 px-1.5 py-0.5 font-mono text-[10px] text-[#d4d4d8]">
              {hoveredMs === null ? formatMs(effectivePlayheadMs) : formatMs(hoveredMs)}
            </div>
          </div>
        </div>

        <div className="pointer-events-none absolute inset-0">
          <div
            className="pointer-events-auto absolute bottom-0 top-0 cursor-ew-resize"
            style={{
              left: msToX(effectivePlayheadMs) - scrollLeft - PLAYHEAD_HALF_HIT_WIDTH + 1,
              width: PLAYHEAD_HIT_WIDTH,
              transition: (isPlaying && !isDraggingPlayhead && !isSeekingByRuler) ? 'left 0.22s linear' : undefined,
            }}
            onPointerDown={handlePlayheadPointerDown}
            onPointerMove={handlePlayheadPointerMove}
            onPointerUp={finishPlayheadDrag}
            onPointerCancel={finishPlayheadDrag}
            onLostPointerCapture={() => {
              dragPointerIdRef.current = null
              setIsDraggingPlayhead(false)
              setDragPlayheadMs(null)
              setSnapLineMs(null)
            }}
            onClick={(event) => {
              event.preventDefault()
              event.stopPropagation()
            }}
          >
            <div
              className="absolute inset-y-0 left-1/2 -translate-x-1/2 bg-[#8b5cf6]"
              style={{
                width: isDraggingPlayhead ? 3 : 2,
                opacity: isDraggingPlayhead ? 0.95 : 0.85,
                boxShadow: isDraggingPlayhead
                  ? '0 0 8px 2px rgba(139, 92, 246, 0.36)'
                  : '0 0 6px 1px rgba(139, 92, 246, 0.25)',
              }}
            />
          </div>
        </div>
      </div>
  )
})

ReviewTimelineWorkspace.displayName = 'ReviewTimelineWorkspace'
