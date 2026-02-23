import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useUIStore } from '@/stores/uiStore'
import { useApproveReview, useReviewData, useSaveReviewData, useTask } from '@/hooks/useTasks'
import type { ReviewScene, SplitStats } from '@/types/task'
import { ReviewPlaybackControls } from './ReviewPlaybackControls'
import { ReviewShotSummaryPanel } from './ReviewShotSummaryPanel'
import { ReviewTimelineWorkspace, type ReviewTimelineWorkspaceHandle } from './ReviewTimelineWorkspace'
import { clamp, resolveAssetUrl } from './reviewUtils'

const ABS_MIN_PIXELS_PER_SECOND = 1
const ABS_MAX_PIXELS_PER_SECOND = 5000
const ZOOM_MIN_FACTOR_FROM_FIT = 0.25
const ZOOM_MAX_FACTOR_FROM_FIT = 40
const ZOOM_RANGE_EPSILON = 0.001
const DEFAULT_TIMELINE_VIEWPORT_WIDTH = 1200
const PLAYBACK_RATE_OPTIONS = [0.5, 0.75, 1, 1.25, 1.5, 2]

function formatElapsedMs(elapsedMs?: number): string {
  if (!Number.isFinite(elapsedMs) || elapsedMs === undefined || elapsedMs <= 0) {
    return '--'
  }
  if (elapsedMs >= 1000) {
    return `${(elapsedMs / 1000).toFixed(elapsedMs >= 10000 ? 0 : 1)}s`
  }
  return `${Math.round(elapsedMs)}ms`
}

function formatSplitStatsSummary(stats: SplitStats | null | undefined): string | null {
  if (!stats) {
    return null
  }
  const total = Math.max(0, stats.totalScenes ?? 0)
  const reused = Math.max(0, stats.reusedCount ?? 0)
  const rendered = Math.max(0, stats.renderedCount ?? 0)
  const fallback = stats.fallbackFullResplit ? '是' : '否'
  return `上次切分：复用 ${reused}/${total} · 重切 ${rendered} · 回退全量 ${fallback} · 耗时 ${formatElapsedMs(stats.totalElapsedMs)}`
}

interface ZoomBounds {
  minPps: number
  maxPps: number
}

function resolveFitPixelsPerSecond(durationMs: number, viewportWidth: number, bounds: ZoomBounds): number {
  const safeDurationSec = Math.max(durationMs / 1000, 1)
  const safeViewportWidth = Number.isFinite(viewportWidth) && viewportWidth > 0
    ? viewportWidth
    : DEFAULT_TIMELINE_VIEWPORT_WIDTH
  const fitPps = safeViewportWidth / safeDurationSec
  return clamp(fitPps, bounds.minPps, bounds.maxPps)
}

function resolveZoomBounds(durationMs: number, viewportWidth: number): ZoomBounds {
  const safeDurationSec = Math.max(durationMs / 1000, 1)
  const safeViewportWidth = Number.isFinite(viewportWidth) && viewportWidth > 0
    ? viewportWidth
    : DEFAULT_TIMELINE_VIEWPORT_WIDTH

  const fitPps = safeViewportWidth / safeDurationSec
  const minPps = clamp(
    fitPps * ZOOM_MIN_FACTOR_FROM_FIT,
    ABS_MIN_PIXELS_PER_SECOND,
    ABS_MAX_PIXELS_PER_SECOND
  )
  const maxPps = clamp(
    fitPps * ZOOM_MAX_FACTOR_FROM_FIT,
    minPps + ZOOM_RANGE_EPSILON,
    ABS_MAX_PIXELS_PER_SECOND
  )

  return { minPps, maxPps }
}

function normalizedToPixelsPerSecond(normalized: number, bounds: ZoomBounds): number {
  const min = Math.max(bounds.minPps, ABS_MIN_PIXELS_PER_SECOND)
  const max = Math.max(bounds.maxPps, min + ZOOM_RANGE_EPSILON)
  const t = clamp(normalized, 0, 1)

  if (max - min <= ZOOM_RANGE_EPSILON) {
    return min
  }

  return min * Math.pow(max / min, t)
}

function pixelsPerSecondToNormalized(pixelsPerSecond: number, bounds: ZoomBounds): number {
  const min = Math.max(bounds.minPps, ABS_MIN_PIXELS_PER_SECOND)
  const max = Math.max(bounds.maxPps, min + ZOOM_RANGE_EPSILON)
  const clampedPps = clamp(pixelsPerSecond, min, max)

  if (max - min <= ZOOM_RANGE_EPSILON) {
    return 0
  }

  return Math.log(clampedPps / min) / Math.log(max / min)
}

export function ReviewModal() {
  const { isReviewModalOpen, reviewTaskId, closeReviewModal, openTimeline, addToast } = useUIStore()

  const [scenes, setScenes] = useState<ReviewScene[]>([])
  const [isDirty, setIsDirty] = useState(false)
  const [selectedSceneIndex, setSelectedSceneIndex] = useState<number | null>(null)
  const [playheadMs, setPlayheadMs] = useState(0)
  const [isPlaying, setIsPlaying] = useState(false)
  const [playbackRate, setPlaybackRate] = useState(1)
  const [videoDurationMs, setVideoDurationMs] = useState(0)
  const [videoLoadFailed, setVideoLoadFailed] = useState(false)
  const [pixelsPerSecond, setPixelsPerSecond] = useState(50)
  const [timelineViewportWidth, setTimelineViewportWidth] = useState(DEFAULT_TIMELINE_VIEWPORT_WIDTH)
  const videoRef = useRef<HTMLVideoElement | null>(null)
  const timelineRef = useRef<ReviewTimelineWorkspaceHandle | null>(null)
  const initializedZoomTaskIdRef = useRef<string | null>(null)
  const metadataAdjustedTaskIdRef = useRef<string | null>(null)
  const userAdjustedZoomTaskIdRef = useRef<string | null>(null)

  const { data: taskDetail } = useTask(reviewTaskId ?? '')
  const { data, isLoading } = useReviewData(reviewTaskId ?? '', isReviewModalOpen && !!reviewTaskId)
  const saveReviewData = useSaveReviewData()
  const approveReview = useApproveReview()
  const splitStatsSummary = useMemo(
    () => formatSplitStatsSummary(taskDetail?.latestSplitStats),
    [taskDetail?.latestSplitStats]
  )

  const durationMs = data?.detectionResult?.durationMs ?? 0
  const isTimelineReady = data?.status === 'TIMELINE_READY'
  const sourceVideoUrl = useMemo(() => resolveAssetUrl(taskDetail?.filePath ?? null), [taskDetail?.filePath])
  const effectiveDurationMs = videoDurationMs > 0 ? videoDurationMs : durationMs
  const zoomBounds = useMemo(
    () => resolveZoomBounds(effectiveDurationMs, timelineViewportWidth),
    [effectiveDurationMs, timelineViewportWidth]
  )
  const zoomNormalized = useMemo(
    () => pixelsPerSecondToNormalized(pixelsPerSecond, zoomBounds),
    [pixelsPerSecond, zoomBounds]
  )

  useEffect(() => {
    setPixelsPerSecond((current) => {
      const next = clamp(current, zoomBounds.minPps, zoomBounds.maxPps)
      if (Math.abs(next - current) <= ZOOM_RANGE_EPSILON) {
        return current
      }
      return next
    })
  }, [zoomBounds])

  useEffect(() => {
    if (!isReviewModalOpen) {
      initializedZoomTaskIdRef.current = null
      metadataAdjustedTaskIdRef.current = null
      userAdjustedZoomTaskIdRef.current = null
      return
    }

    if (!reviewTaskId) {
      return
    }

    if (initializedZoomTaskIdRef.current === reviewTaskId) {
      return
    }

    const seedDurationMs = durationMs > 0 ? durationMs : videoDurationMs
    if (seedDurationMs <= 0) {
      return
    }

    const fitPps = resolveFitPixelsPerSecond(seedDurationMs, timelineViewportWidth, zoomBounds)
    setPixelsPerSecond(Math.round(fitPps * 100) / 100)
    initializedZoomTaskIdRef.current = reviewTaskId
    metadataAdjustedTaskIdRef.current = videoDurationMs > 0 ? reviewTaskId : null
    userAdjustedZoomTaskIdRef.current = null
  }, [
    durationMs,
    isReviewModalOpen,
    reviewTaskId,
    timelineViewportWidth,
    videoDurationMs,
    zoomBounds,
  ])

  useEffect(() => {
    if (!isReviewModalOpen || !reviewTaskId) {
      return
    }

    if (videoDurationMs <= 0) {
      return
    }

    if (initializedZoomTaskIdRef.current !== reviewTaskId) {
      return
    }

    if (metadataAdjustedTaskIdRef.current === reviewTaskId) {
      return
    }

    if (userAdjustedZoomTaskIdRef.current === reviewTaskId) {
      metadataAdjustedTaskIdRef.current = reviewTaskId
      return
    }

    const fitPps = resolveFitPixelsPerSecond(videoDurationMs, timelineViewportWidth, zoomBounds)
    setPixelsPerSecond((current) => {
      if (Math.abs(current - fitPps) <= ZOOM_RANGE_EPSILON) {
        return current
      }
      return Math.round(fitPps * 100) / 100
    })
    metadataAdjustedTaskIdRef.current = reviewTaskId
  }, [isReviewModalOpen, reviewTaskId, timelineViewportWidth, videoDurationMs, zoomBounds])

  useEffect(() => {
    if (!data) {
      return
    }

    const source = data.userEditedScenes ?? data.detectionResult?.scenes ?? []
    setScenes(source)
    setIsDirty(false)

    if (source.length > 0) {
      setSelectedSceneIndex(0)
      setPlayheadMs(source[0].startMs)
    } else {
      setSelectedSceneIndex(null)
      setPlayheadMs(0)
    }

    const video = videoRef.current
    if (video) {
      video.pause()
    }
    setIsPlaying(false)
  }, [data])

  useEffect(() => {
    if (!isReviewModalOpen) {
      const video = videoRef.current
      if (video) {
        video.pause()
      }
      setIsPlaying(false)
      setPlayheadMs(0)
      setSelectedSceneIndex(null)
    }
  }, [isReviewModalOpen])

  useEffect(() => {
    if (!isReviewModalOpen || !reviewTaskId) {
      return
    }
    setPlaybackRate(1)
  }, [isReviewModalOpen, reviewTaskId])

  useEffect(() => {
    setVideoDurationMs(0)
    setVideoLoadFailed(false)
    const video = videoRef.current
    if (video) {
      video.pause()
    }
    setIsPlaying(false)
  }, [sourceVideoUrl])

  useEffect(() => {
    const video = videoRef.current
    if (!video || !Number.isFinite(video.duration) || video.duration <= 0) {
      return
    }

    const targetSec = clamp(playheadMs / 1000, 0, video.duration)
    if (Math.abs(video.currentTime - targetSec) > 0.08) {
      video.currentTime = targetSec
    }
  }, [playheadMs, sourceVideoUrl])

  useEffect(() => {
    const video = videoRef.current
    if (!video) {
      return
    }
    video.playbackRate = playbackRate
  }, [playbackRate, sourceVideoUrl])

  useEffect(() => {
    if (scenes.length === 0) {
      setSelectedSceneIndex(null)
      return
    }

    const index = scenes.findIndex((scene) => playheadMs >= scene.startMs && playheadMs < scene.endMs)
    if (index >= 0) {
      setSelectedSceneIndex(index)
      return
    }

    if (playheadMs >= scenes[scenes.length - 1].endMs) {
      setSelectedSceneIndex(scenes.length - 1)
    }
  }, [playheadMs, scenes])

  const handleDeleteScene = useCallback((index: number) => {
    setScenes((prev) => {
      if (prev.length <= 1) {
        return prev
      }

      const next = [...prev]
      if (index === 0) {
        next.splice(0, 1)
        next[0] = { ...next[0], startMs: 0 }
      } else {
        next[index - 1] = { ...next[index - 1], endMs: next[index].endMs }
        next.splice(index, 1)
      }
      return next
    })

    setIsDirty(true)
  }, [])

  const handleDeleteBoundary = useCallback((sceneIndex: number) => {
    handleDeleteScene(sceneIndex)
  }, [handleDeleteScene])

  const handleAddBoundary = useCallback((ms: number) => {
    if (ms <= 0 || ms >= effectiveDurationMs) {
      return
    }

    setScenes((prev) => {
      const index = prev.findIndex((scene) => scene.startMs <= ms && ms < scene.endMs)
      if (index < 0) {
        return prev
      }

      const scene = prev[index]
      if (ms - scene.startMs < 500 || scene.endMs - ms < 500) {
        return prev
      }

      const next = [...prev]
      next.splice(index, 1, { startMs: scene.startMs, endMs: ms }, { startMs: ms, endMs: scene.endMs })
      return next
    })

    setIsDirty(true)
  }, [effectiveDurationMs])

  const seekPlayhead = useCallback((targetMs: number) => {
    const capped = clamp(targetMs, 0, effectiveDurationMs)
    const video = videoRef.current

    if (video) {
      const targetSec = capped / 1000
      if (Math.abs(video.currentTime - targetSec) > 0.08) {
        video.currentTime = targetSec
      }
    }

    setPlayheadMs(capped)
  }, [effectiveDurationMs])

  const stepPlayhead = useCallback((deltaMs: number) => {
    seekPlayhead(playheadMs + deltaMs)
  }, [playheadMs, seekPlayhead])

  const deleteBoundaryNearPlayhead = useCallback(() => {
    if (scenes.length <= 1) {
      return
    }

    let nearestIndex = -1
    let nearestDiff = Number.POSITIVE_INFINITY

    for (let index = 1; index < scenes.length; index += 1) {
      const diff = Math.abs(scenes[index].startMs - playheadMs)
      if (diff < nearestDiff) {
        nearestDiff = diff
        nearestIndex = index
      }
    }

    const thresholdMs = Math.max(220, Math.round(effectiveDurationMs * 0.004))
    if (nearestIndex > 0 && nearestDiff <= thresholdMs) {
      handleDeleteBoundary(nearestIndex)
    }
  }, [effectiveDurationMs, handleDeleteBoundary, playheadMs, scenes])

  const handleTogglePlayback = useCallback(async () => {
    const video = videoRef.current
    if (!video || !sourceVideoUrl || videoLoadFailed) {
      addToast({
        type: 'warning',
        message: '原视频暂不可播放，请检查视频源路径',
      })
      return
    }

    try {
      if (video.paused) {
        await video.play()
      } else {
        video.pause()
      }
    } catch (error) {
      console.error('Video playback failed:', error)
      addToast({
        type: 'warning',
        message: '播放失败，请手动重试',
      })
    }
  }, [addToast, sourceVideoUrl, videoLoadFailed])

  useEffect(() => {
    if (!isReviewModalOpen) {
      return
    }

    const onKeyDown = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null
      if (target?.isContentEditable) {
        return
      }

      if (target && (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA')) {
        const input = target as HTMLInputElement
        if (input.type !== 'range') {
          return
        }
      }

      if ((event.ctrlKey || event.metaKey) && (event.key === 'z' || event.key === 'y')) {
        event.preventDefault()
        return
      }

      if (event.key === ' ') {
        event.preventDefault()
        void handleTogglePlayback()
        return
      }

      if (event.key === 'ArrowLeft') {
        event.preventDefault()
        stepPlayhead(-1000)
        return
      }

      if (event.key === 'ArrowRight') {
        event.preventDefault()
        stepPlayhead(1000)
        return
      }

      if (event.key === 'Delete') {
        event.preventDefault()
        deleteBoundaryNearPlayhead()
      }
    }

    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [deleteBoundaryNearPlayhead, handleTogglePlayback, isReviewModalOpen, stepPlayhead])

  const handleVideoLoadedMetadata = () => {
    const video = videoRef.current
    if (!video || !Number.isFinite(video.duration) || video.duration <= 0) {
      return
    }

    const nextDurationMs = Math.round(video.duration * 1000)
    setVideoDurationMs(nextDurationMs)

    const normalizedPlayhead = clamp(playheadMs, 0, nextDurationMs)
    setPlayheadMs(normalizedPlayhead)

    const targetSec = normalizedPlayhead / 1000
    if (Math.abs(video.currentTime - targetSec) > 0.08) {
      video.currentTime = targetSec
    }
    video.playbackRate = playbackRate
  }

  const handleVideoTimeUpdate = () => {
    const video = videoRef.current
    if (!video) {
      return
    }
    setPlayheadMs(Math.round(video.currentTime * 1000))
  }

  const handleVideoError = () => {
    setVideoLoadFailed(true)
    setIsPlaying(false)
  }

  const handleConfirm = async () => {
    if (!reviewTaskId || scenes.length === 0) {
      return
    }

    try {
      if (isDirty) {
        await saveReviewData.mutateAsync({ id: reviewTaskId, scenes })
      }
      await approveReview.mutateAsync(reviewTaskId)

      const video = videoRef.current
      if (video) {
        video.pause()
      }

      setIsPlaying(false)
      closeReviewModal()
      addToast({
        type: 'success',
        message: isTimelineReady ? '已提交重新切分任务（覆盖旧切片）' : '已提交切分任务',
      })
    } catch (error) {
      console.error('Approve review failed:', error)
      addToast({
        type: 'error',
        message: '提交切分失败，请稍后重试',
      })
    }
  }

  const handleViewTimeline = () => {
    if (!reviewTaskId) {
      return
    }

    const video = videoRef.current
    if (video) {
      video.pause()
    }

    setIsPlaying(false)
    closeReviewModal()
    openTimeline(reviewTaskId)
  }

  const jumpToScene = (index: number) => {
    const scene = scenes[index]
    if (!scene) {
      return
    }

    const video = videoRef.current
    if (video) {
      video.pause()
    }
    setSelectedSceneIndex(index)
    setPlayheadMs(scene.startMs)
    setIsPlaying(false)
  }

  const prepareZoomAnchor = useCallback(() => {
    const timeline = timelineRef.current
    if (!timeline) {
      return
    }
    timeline.prepareExternalZoomAnchorByMs(playheadMs)
  }, [playheadMs])

  const handleTimelineViewportWidthChange = useCallback((width: number) => {
    if (!Number.isFinite(width) || width <= 0) {
      return
    }

    setTimelineViewportWidth((current) => {
      if (Math.abs(current - width) < 1) {
        return current
      }
      return width
    })
  }, [])

  const handlePixelsPerSecondChange = useCallback((nextPixelsPerSecond: number) => {
    if (reviewTaskId) {
      userAdjustedZoomTaskIdRef.current = reviewTaskId
    }
    const clamped = clamp(nextPixelsPerSecond, zoomBounds.minPps, zoomBounds.maxPps)
    setPixelsPerSecond(Math.round(clamped * 100) / 100)
  }, [reviewTaskId, zoomBounds])

  const handleZoomSliderChange = useCallback((event: React.ChangeEvent<HTMLInputElement>) => {
    if (reviewTaskId) {
      userAdjustedZoomTaskIdRef.current = reviewTaskId
    }
    prepareZoomAnchor()
    const normalized = clamp(Number(event.target.value) / 100, 0, 1)
    const mapped = normalizedToPixelsPerSecond(normalized, zoomBounds)
    setPixelsPerSecond(Math.round(mapped * 100) / 100)
  }, [prepareZoomAnchor, reviewTaskId, zoomBounds])

  const handleZoomReset = useCallback(() => {
    if (effectiveDurationMs <= 0) {
      addToast({
        type: 'warning',
        message: '暂无可用时间轴数据，无法重置缩放',
      })
      return
    }

    if (reviewTaskId) {
      userAdjustedZoomTaskIdRef.current = reviewTaskId
    }

    const fitPps = resolveFitPixelsPerSecond(effectiveDurationMs, timelineViewportWidth, zoomBounds)
    if (Math.abs(pixelsPerSecond - fitPps) <= ZOOM_RANGE_EPSILON) {
      addToast({
        type: 'info',
        message: '已是默认缩放',
      })
      return
    }

    prepareZoomAnchor()
    setPixelsPerSecond(Math.round(fitPps * 100) / 100)
  }, [
    addToast,
    effectiveDurationMs,
    pixelsPerSecond,
    prepareZoomAnchor,
    reviewTaskId,
    timelineViewportWidth,
    zoomBounds,
  ])

  if (!isReviewModalOpen) {
    return null
  }

  const isConfirming = saveReviewData.isPending || approveReview.isPending
  const confirmLabel = isTimelineReady ? '重新切分并覆盖' : '确认并切分'

  return (
    <div className="fixed inset-0 z-50 flex flex-col bg-[var(--sc-bg-app)] text-[var(--sc-text-primary)]">
      <div className="flex items-center justify-between border-b border-[var(--sc-border-subtle)] bg-[var(--sc-bg-panel)] px-4 py-2.5">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <h2 className="text-sm font-semibold text-[var(--sc-text-primary)]">场景预览确认</h2>
              {isDirty ? (
                <span
                  className="rounded px-1.5 py-0.5 text-xs text-[#f6c15f]"
                  style={{ boxShadow: 'inset 0 0 0 1px rgba(246, 193, 95, 0.45)' }}
                >
                  已修改
                </span>
              ) : null}
              {isTimelineReady ? (
                <span
                  className="rounded px-1.5 py-0.5 text-xs text-[var(--sc-accent)]"
                  style={{ boxShadow: 'inset 0 0 0 1px rgba(91, 140, 255, 0.45)' }}
                >
                  已切分，可继续调整
                </span>
              ) : null}
            </div>
            {splitStatsSummary ? (
              <p className="mt-0.5 text-xs text-[var(--sc-text-muted)]">{splitStatsSummary}</p>
            ) : null}
          </div>

        <div className="flex items-center gap-2">
          {isTimelineReady ? (
            <button
              type="button"
              onClick={handleViewTimeline}
              className="sc-btn sc-btn-secondary h-8 px-3"
            >
              查看工作台
            </button>
          ) : null}

          <button
            type="button"
            onClick={handleConfirm}
            disabled={isConfirming || scenes.length === 0}
            className="sc-btn sc-btn-primary h-8 px-3"
          >
            {isConfirming ? '提交中...' : confirmLabel}
          </button>

          <button
            type="button"
            onClick={closeReviewModal}
            className="sc-btn sc-btn-ghost sc-btn-icon"
            aria-label="关闭"
          >
            ✕
          </button>
        </div>
      </div>

      {isLoading ? (
        <div className="flex flex-1 items-center justify-center text-[var(--sc-text-muted)]">加载审核数据中...</div>
      ) : (
        <div className="grid min-h-0 flex-1 grid-cols-[minmax(0,1fr)_320px] overflow-hidden">
          <div className="flex min-h-0 min-w-0 flex-col bg-[var(--sc-bg-contrast)]">
            <div className="grid min-h-0 flex-1 grid-rows-[minmax(260px,8fr)_56px_48px_minmax(160px,3fr)]">
              <div className="border-b border-[var(--sc-border-subtle)] bg-[var(--sc-bg-surface)] p-4">
                <div className="h-full overflow-hidden rounded-lg border border-[var(--sc-border-subtle)] bg-black">
                  {sourceVideoUrl && !videoLoadFailed ? (
                    <video
                      ref={videoRef}
                      key={sourceVideoUrl}
                      src={sourceVideoUrl}
                      preload="metadata"
                      playsInline
                      className="h-full w-full bg-black object-contain"
                      onLoadedMetadata={handleVideoLoadedMetadata}
                      onTimeUpdate={handleVideoTimeUpdate}
                      onPlay={() => setIsPlaying(true)}
                      onPause={() => setIsPlaying(false)}
                      onEnded={() => setIsPlaying(false)}
                      onError={handleVideoError}
                    />
                  ) : (
                    <div className="flex h-full items-center justify-center text-sm text-[var(--sc-text-muted)]">
                      {sourceVideoUrl ? '原视频加载失败，无法播放' : '未找到原视频源'}
                    </div>
                  )}
                </div>
              </div>

              <ReviewPlaybackControls
                playheadMs={playheadMs}
                durationMs={effectiveDurationMs}
                isPlaying={isPlaying}
                playbackRate={playbackRate}
                playbackRateOptions={PLAYBACK_RATE_OPTIONS}
                onSeek={seekPlayhead}
                onStepSecondBack={() => stepPlayhead(-1000)}
                onStepSecondForward={() => stepPlayhead(1000)}
                onTogglePlay={() => {
                  void handleTogglePlayback()
                }}
                onPlaybackRateChange={(rate) => {
                  if (!PLAYBACK_RATE_OPTIONS.includes(rate)) {
                    return
                  }
                  setPlaybackRate(rate)
                }}
              />

              <div className="flex items-center justify-between border-b border-[var(--sc-border-subtle)] bg-[var(--sc-bg-surface)] px-4 text-xs text-[var(--sc-text-muted)]">
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => handleAddBoundary(playheadMs)}
                    className="sc-btn sc-btn-secondary h-7 px-2"
                  >
                    添加切分点
                  </button>
                  <button
                    type="button"
                    onClick={deleteBoundaryNearPlayhead}
                    className="sc-btn sc-btn-secondary h-7 px-2"
                  >
                    删除临近切分点
                  </button>
                </div>

                <div className="flex items-center gap-2">
                  <span className="text-[var(--sc-text-secondary)]">缩放</span>
                  <input
                    type="range"
                    min={0}
                    max={100}
                    step={1}
                    value={Math.round(zoomNormalized * 100)}
                    onChange={handleZoomSliderChange}
                    className="sc-range h-1.5 w-32"
                  />
                  <span className="w-14 text-right font-mono text-[var(--sc-text-secondary)]">{Math.round(pixelsPerSecond)}px/s</span>
                  <button
                    type="button"
                    onClick={handleZoomReset}
                    className="sc-btn sc-btn-secondary h-7 px-2"
                  >
                    重置
                  </button>
                </div>
              </div>

              <div className="min-h-0 bg-[var(--sc-bg-panel)] px-4">
                {effectiveDurationMs > 0 ? (
                  <ReviewTimelineWorkspace
                    ref={timelineRef}
                    taskId={reviewTaskId ?? ''}
                    scenes={scenes}
                    durationMs={effectiveDurationMs}
                    playheadMs={playheadMs}
                    isPlaying={isPlaying}
                    pixelsPerSecond={pixelsPerSecond}
                    minPixelsPerSecond={zoomBounds.minPps}
                    maxPixelsPerSecond={zoomBounds.maxPps}
                    zoomStepFactor={1.08}
                    onPixelsPerSecondChange={handlePixelsPerSecondChange}
                    onViewportWidthChange={handleTimelineViewportWidthChange}
                    onAddBoundary={handleAddBoundary}
                    onDeleteBoundary={handleDeleteBoundary}
                    onSetPlayhead={seekPlayhead}
                  />
                ) : (
                  <div className="flex h-full items-center justify-center text-[var(--sc-text-muted)]">无可用时间轴数据</div>
                )}
              </div>
            </div>
          </div>

          <div className="min-h-0 border-l border-[var(--sc-border-subtle)] bg-[var(--sc-bg-panel)]">
            <ReviewShotSummaryPanel
              taskId={reviewTaskId ?? ''}
              scenes={scenes}
              selectedIndex={selectedSceneIndex}
              isPlaying={isPlaying}
              onSelect={jumpToScene}
            />
          </div>
        </div>
      )}
    </div>
  )
}
