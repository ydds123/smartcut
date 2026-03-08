import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { useUIStore } from '@/stores/uiStore'
import { taskService } from '@/services/taskService'
import { useTaskProgress } from '@/hooks/useTaskProgress'
import { useApproveReview, useReviewData, useSaveReviewData, useStartReview, useTask } from '@/hooks/useTasks'
import type {
  ProcessTaskOptions,
  ProcessingConfigMeta,
  ReviewScene,
  SplitStats,
  TaskStatus,
} from '@/types/task'
import { Progress } from '@/components/ui/progress'
import { ProcessingConfigModal } from '@/components/task/ProcessingConfigModal'
import {
  DEFAULT_PROCESSING_SETTINGS,
  loadProcessingSettings,
  toProcessTaskOptions,
  type ProcessingPanelSettings,
} from '@/components/task/processingConfigSettings'
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

function formatResplitStatus(status: TaskStatus): string {
  if (status === 'QUEUED') {
    return '任务排队中...'
  }
  if (status === 'DETECTING') {
    return '正在重新检测分镜...'
  }
  if (status === 'REVIEW_PENDING') {
    return '分镜检测完成，准备切分...'
  }
  if (status === 'REVIEW_APPROVED') {
    return '切分任务已提交，等待执行...'
  }
  if (status === 'SPLITTING') {
    return '正在重新切分中...'
  }
  if (status === 'TIMELINE_READY') {
    return '切分完成'
  }
  if (status === 'FAILED' || status === 'ANALYZE_FAILED') {
    return '处理失败'
  }
  return `处理中：${status}`
}

type TemporaryResplitPhase =
  | 'idle'
  | 'submitting-review'
  | 'running-review'
  | 'submitting-split'
  | 'running-split'

function resolveNearestSceneIndexByMs(source: ReviewScene[], targetMs: number): number {
  if (source.length <= 1) {
    return 0
  }

  let nearestIndex = 0
  let nearestDistance = Number.POSITIVE_INFINITY

  source.forEach((scene, index) => {
    const centerMs = scene.startMs + (scene.endMs - scene.startMs) / 2
    const distance = Math.abs(centerMs - targetMs)
    if (distance < nearestDistance) {
      nearestDistance = distance
      nearestIndex = index
    }
  })

  return nearestIndex
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
  const { isReviewModalOpen, reviewTaskId, closeReviewModal, addToast } = useUIStore()
  const queryClient = useQueryClient()

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
  const [processingConfigMeta, setProcessingConfigMeta] = useState<ProcessingConfigMeta | null>(null)
  const [isResplitConfigOpen, setIsResplitConfigOpen] = useState(false)
  const [resplitSettings, setResplitSettings] = useState<ProcessingPanelSettings>(DEFAULT_PROCESSING_SETTINGS)
  const [temporaryResplitPhase, setTemporaryResplitPhase] = useState<TemporaryResplitPhase>('idle')
  const [reviewStatusOverride, setReviewStatusOverride] = useState<TaskStatus | null>(null)
  const videoRef = useRef<HTMLVideoElement | null>(null)
  const timelineRef = useRef<ReviewTimelineWorkspaceHandle | null>(null)
  const latestPlayheadRef = useRef(0)
  const latestSelectedSceneIndexRef = useRef<number | null>(null)
  const preservePositionOnNextRefreshRef = useRef(false)
  const temporaryResplitTerminalHandledRef = useRef(false)
  const temporaryResplitOptionsRef = useRef<ProcessTaskOptions | null>(null)
  const temporaryResplitSplitTriggeredRef = useRef(false)
  const initializedZoomTaskIdRef = useRef<string | null>(null)
  const metadataAdjustedTaskIdRef = useRef<string | null>(null)
  const userAdjustedZoomTaskIdRef = useRef<string | null>(null)
  const isTemporaryResplitting = temporaryResplitPhase !== 'idle'
  const progressSeedStatus: TaskStatus | undefined =
    temporaryResplitPhase === 'submitting-review' || temporaryResplitPhase === 'running-review'
      ? 'DETECTING'
      : (isTemporaryResplitting ? 'REVIEW_APPROVED' : undefined)

  const { data: taskDetail } = useTask(reviewTaskId ?? '')
  const { data, isLoading } = useReviewData(reviewTaskId ?? '', isReviewModalOpen && !!reviewTaskId)
  const { progress: splitProgress, status: splitStatus } = useTaskProgress(
    reviewTaskId ?? '',
    progressSeedStatus,
    isTemporaryResplitting ? 0 : undefined
  )
  const saveReviewData = useSaveReviewData()
  const startReview = useStartReview()
  const approveReview = useApproveReview()
  const splitStatsSummary = useMemo(
    () => formatSplitStatsSummary(taskDetail?.latestSplitStats),
    [taskDetail?.latestSplitStats]
  )

  const durationMs = data?.detectionResult?.durationMs ?? 0
  const currentReviewStatus =
    reviewStatusOverride
    ?? (data?.status as TaskStatus | undefined)
    ?? (taskDetail?.status as TaskStatus | undefined)
    ?? null
  const isTimelineReady = currentReviewStatus === 'TIMELINE_READY'
  const canSubmitSplit =
    currentReviewStatus === 'REVIEW_PENDING' || currentReviewStatus === 'TIMELINE_READY'
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
    if (!isReviewModalOpen) {
      setIsResplitConfigOpen(false)
      setTemporaryResplitPhase('idle')
      setReviewStatusOverride(null)
      preservePositionOnNextRefreshRef.current = false
      temporaryResplitTerminalHandledRef.current = false
      temporaryResplitOptionsRef.current = null
      temporaryResplitSplitTriggeredRef.current = false
      return
    }

    let disposed = false
    const loadMeta = async () => {
      try {
        const meta = await taskService.getProcessingConfigMeta()
        if (disposed) {
          return
        }
        setProcessingConfigMeta(meta)
      } catch {
        if (disposed) {
          return
        }
        setProcessingConfigMeta(null)
      }
    }
    void loadMeta()

    return () => {
      disposed = true
    }
  }, [isReviewModalOpen])

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
    latestPlayheadRef.current = playheadMs
  }, [playheadMs])

  useEffect(() => {
    latestSelectedSceneIndexRef.current = selectedSceneIndex
  }, [selectedSceneIndex])

  useEffect(() => {
    if (!data) {
      return
    }

    const source = data.userEditedScenes ?? data.detectionResult?.scenes ?? []
    const shouldPreservePosition = preservePositionOnNextRefreshRef.current
    setScenes(source)
    setIsDirty(false)

    if (source.length > 0) {
      if (shouldPreservePosition) {
        const previousPlayhead = latestPlayheadRef.current
        const maxPlayableMs = source[source.length - 1].endMs
        const nextPlayhead = clamp(previousPlayhead, 0, maxPlayableMs)
        const sceneAtPlayhead = source.findIndex(
          (scene) => nextPlayhead >= scene.startMs && nextPlayhead < scene.endMs
        )
        const sameIndex =
          latestSelectedSceneIndexRef.current !== null
          && latestSelectedSceneIndexRef.current >= 0
          && latestSelectedSceneIndexRef.current < source.length
            ? latestSelectedSceneIndexRef.current
            : null
        const nextIndex = sceneAtPlayhead >= 0
          ? sceneAtPlayhead
          : (sameIndex ?? resolveNearestSceneIndexByMs(source, nextPlayhead))

        setSelectedSceneIndex(nextIndex)
        setPlayheadMs(nextPlayhead)
      } else {
        setSelectedSceneIndex(0)
        setPlayheadMs(source[0].startMs)
      }
    } else {
      setSelectedSceneIndex(null)
      setPlayheadMs(0)
    }
    preservePositionOnNextRefreshRef.current = false

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
      setSelectedSceneIndex((previous) => (previous === null ? previous : null))
      return
    }

    const index = scenes.findIndex((scene) => playheadMs >= scene.startMs && playheadMs < scene.endMs)
    if (index >= 0) {
      setSelectedSceneIndex((previous) => (previous === index ? previous : index))
      return
    }

    if (playheadMs >= scenes[scenes.length - 1].endMs) {
      const lastIndex = scenes.length - 1
      setSelectedSceneIndex((previous) => (previous === lastIndex ? previous : lastIndex))
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

  const enqueueSplitTask = useCallback(
    async (options?: ProcessTaskOptions) => {
      if (!reviewTaskId || scenes.length === 0) {
        return null
      }

      if (isDirty) {
        await saveReviewData.mutateAsync({ id: reviewTaskId, scenes })
        setIsDirty(false)
      }

      const response = await approveReview.mutateAsync({
        id: reviewTaskId,
        options,
      })
      return response
    },
    [approveReview, isDirty, reviewTaskId, saveReviewData, scenes]
  )

  const handleConfirm = async () => {
    if (!canSubmitSplit) {
      addToast({
        type: 'info',
        message: '当前任务仅支持预览分镜',
      })
      return
    }

    try {
      await enqueueSplitTask()

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

  const handleOpenResplitConfig = useCallback(() => {
    if (!canSubmitSplit) {
      addToast({
        type: 'info',
        message: '当前任务仅支持预览分镜',
      })
      return
    }
    if (scenes.length === 0) {
      addToast({
        type: 'warning',
        message: '当前没有可切分镜头，无法重新切分',
      })
      return
    }
    if (isTemporaryResplitting) {
      return
    }
    const inheritedSettings = loadProcessingSettings(processingConfigMeta)
    setResplitSettings(inheritedSettings)
    setIsResplitConfigOpen(true)
  }, [addToast, canSubmitSplit, isTemporaryResplitting, processingConfigMeta, scenes.length])

  const handleSubmitTemporaryResplit = useCallback(
    async (settings: ProcessingPanelSettings) => {
      if (!reviewTaskId || scenes.length === 0) {
        return
      }

      try {
        const options = toProcessTaskOptions(settings)
        temporaryResplitTerminalHandledRef.current = false
        temporaryResplitSplitTriggeredRef.current = false
        temporaryResplitOptionsRef.current = options
        setTemporaryResplitPhase('submitting-review')
        setReviewStatusOverride('QUEUED')

        await startReview.mutateAsync({
          id: reviewTaskId,
          options,
        })
        setTemporaryResplitPhase('running-review')
        setReviewStatusOverride('DETECTING')

        addToast({
          type: 'success',
          message: '已提交重新检测任务',
        })
      } catch (error) {
        console.error('Temporary resplit review-submit failed:', error)
        temporaryResplitTerminalHandledRef.current = false
        temporaryResplitSplitTriggeredRef.current = false
        temporaryResplitOptionsRef.current = null
        setTemporaryResplitPhase('idle')
        setReviewStatusOverride(null)
        addToast({
          type: 'error',
          message: '重新检测提交失败，请稍后重试',
        })
      }
    },
    [addToast, reviewTaskId, scenes.length, startReview]
  )

  const handleTemporaryResplitSuccess = useCallback(
    (status: TaskStatus) => {
      if (temporaryResplitTerminalHandledRef.current) {
        return
      }
      temporaryResplitTerminalHandledRef.current = true

      const video = videoRef.current
      if (video) {
        video.pause()
      }
      setIsPlaying(false)
      temporaryResplitOptionsRef.current = null
      temporaryResplitSplitTriggeredRef.current = false
      setTemporaryResplitPhase('idle')
      setReviewStatusOverride('TIMELINE_READY')

      preservePositionOnNextRefreshRef.current = true
      if (reviewTaskId) {
        void Promise.all([
          queryClient.invalidateQueries({ queryKey: ['tasks'] }),
          queryClient.invalidateQueries({ queryKey: ['tasks', reviewTaskId] }),
          queryClient.invalidateQueries({ queryKey: ['tasks', reviewTaskId, 'review-data'] }),
        ])
      }

      const successMessage = status === 'COMPLETED'
        ? '切分完成，已刷新当前页面'
        : '重新检测并切分完成，已刷新当前页面'
      addToast({
        type: 'success',
        message: successMessage,
      })
    },
    [addToast, queryClient, reviewTaskId]
  )

  const handleTemporaryResplitFailure = useCallback(
    (message = '重新检测或切分失败，请调整参数后重试') => {
      if (temporaryResplitTerminalHandledRef.current) {
        return
      }
      temporaryResplitTerminalHandledRef.current = true
      temporaryResplitOptionsRef.current = null
      temporaryResplitSplitTriggeredRef.current = false
      setTemporaryResplitPhase('idle')
      setReviewStatusOverride(null)
      addToast({
        type: 'error',
        message,
      })
    },
    [addToast]
  )

  useEffect(() => {
    if (temporaryResplitPhase === 'idle' || !reviewTaskId) {
      return
    }

    if (splitStatus === 'FAILED' || splitStatus === 'ANALYZE_FAILED') {
      handleTemporaryResplitFailure()
      return
    }

    if (temporaryResplitPhase === 'running-review' || temporaryResplitPhase === 'submitting-split') {
      if (splitStatus === 'REVIEW_PENDING' && !temporaryResplitSplitTriggeredRef.current) {
        temporaryResplitSplitTriggeredRef.current = true
        setTemporaryResplitPhase('submitting-split')
        setReviewStatusOverride('REVIEW_APPROVED')

        void approveReview.mutateAsync({
          id: reviewTaskId,
          options: temporaryResplitOptionsRef.current ?? undefined,
        }).then(() => {
          setTemporaryResplitPhase('running-split')
          addToast({
            type: 'success',
            message: '检测完成，已提交重新切分任务',
          })
        }).catch((error) => {
          console.error('Temporary resplit split-submit failed:', error)
          temporaryResplitSplitTriggeredRef.current = false
          handleTemporaryResplitFailure('切分任务提交失败，请稍后重试')
        })
        return
      }

      if (splitStatus === 'REVIEW_APPROVED' || splitStatus === 'SPLITTING') {
        setTemporaryResplitPhase('running-split')
        setReviewStatusOverride('REVIEW_APPROVED')
        return
      }
    }

    if (
      (temporaryResplitPhase === 'running-review'
        || temporaryResplitPhase === 'submitting-split'
        || temporaryResplitPhase === 'running-split')
      && (splitStatus === 'TIMELINE_READY' || splitStatus === 'COMPLETED')
    ) {
      handleTemporaryResplitSuccess(splitStatus)
      return
    }
  }, [
    addToast,
    approveReview,
    handleTemporaryResplitFailure,
    handleTemporaryResplitSuccess,
    reviewTaskId,
    splitStatus,
    temporaryResplitPhase,
  ])

  useEffect(() => {
    if (temporaryResplitPhase === 'idle' || !reviewTaskId) {
      return
    }

    let disposed = false
    const pollStatus = async () => {
      try {
        const latestTask = await taskService.getById(reviewTaskId)
        if (disposed) {
          return
        }
        const latestStatus = latestTask.status as TaskStatus

        if (latestStatus === 'FAILED' || latestStatus === 'ANALYZE_FAILED') {
          handleTemporaryResplitFailure()
          return
        }

        if (temporaryResplitPhase === 'running-review' || temporaryResplitPhase === 'submitting-split') {
          if (latestStatus === 'REVIEW_PENDING' && !temporaryResplitSplitTriggeredRef.current) {
            temporaryResplitSplitTriggeredRef.current = true
            setTemporaryResplitPhase('submitting-split')
            setReviewStatusOverride('REVIEW_APPROVED')
            try {
              await approveReview.mutateAsync({
                id: reviewTaskId,
                options: temporaryResplitOptionsRef.current ?? undefined,
              })
              if (disposed) {
                return
              }
              setTemporaryResplitPhase('running-split')
              addToast({
                type: 'success',
                message: '检测完成，已提交重新切分任务',
              })
            } catch (error) {
              console.error('Temporary resplit split-submit failed (polling):', error)
              temporaryResplitSplitTriggeredRef.current = false
              if (!disposed) {
                handleTemporaryResplitFailure('切分任务提交失败，请稍后重试')
              }
            }
            return
          }

          if (latestStatus === 'REVIEW_APPROVED' || latestStatus === 'SPLITTING') {
            setTemporaryResplitPhase('running-split')
            setReviewStatusOverride('REVIEW_APPROVED')
            return
          }
        }

        if (
          (temporaryResplitPhase === 'running-review'
            || temporaryResplitPhase === 'submitting-split'
            || temporaryResplitPhase === 'running-split')
          && (latestStatus === 'TIMELINE_READY' || latestStatus === 'COMPLETED')
        ) {
          handleTemporaryResplitSuccess(latestStatus)
        }
      } catch {
        // polling fallback best effort
      }
    }

    const timer = window.setInterval(() => {
      void pollStatus()
    }, 3000)
    void pollStatus()

    return () => {
      disposed = true
      window.clearInterval(timer)
    }
  }, [
    addToast,
    approveReview,
    handleTemporaryResplitFailure,
    handleTemporaryResplitSuccess,
    reviewTaskId,
    temporaryResplitPhase,
  ])

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

  const handleLocateTimelineLine = useCallback(() => {
    if (effectiveDurationMs <= 0) {
      addToast({
        type: 'warning',
        message: '暂无可用时间轴数据，无法定位',
      })
      return
    }

    const timeline = timelineRef.current
    if (!timeline) {
      addToast({
        type: 'warning',
        message: '时间轴尚未就绪，请稍后再试',
      })
      return
    }

    const moved = timeline.locatePlayheadInViewport({ behavior: 'smooth' })
    if (!moved) {
      addToast({
        type: 'info',
        message: '当前轴线已在视野中心附近',
      })
    }
  }, [addToast, effectiveDurationMs])

  if (!isReviewModalOpen) {
    return null
  }

  const isConfirming = saveReviewData.isPending || startReview.isPending || approveReview.isPending
  const isToolbarBusy = isConfirming || isTemporaryResplitting
  const resplitStatusText = temporaryResplitPhase === 'submitting-review'
    ? '正在提交重新检测任务...'
    : temporaryResplitPhase === 'submitting-split'
      ? '检测完成，正在提交切分任务...'
      : formatResplitStatus(splitStatus)
  const resplitProgressValue = (() => {
    if (temporaryResplitPhase === 'submitting-review') {
      return 1
    }
    if (temporaryResplitPhase === 'running-review') {
      return Math.max(1, Math.min(50, Math.round(splitProgress * 0.5)))
    }
    if (temporaryResplitPhase === 'submitting-split') {
      return 55
    }
    if (temporaryResplitPhase === 'running-split') {
      return Math.max(50, Math.min(100, 50 + Math.round(splitProgress * 0.5)))
    }
    return 0
  })()
  const confirmLabel = canSubmitSplit
    ? (isTimelineReady ? '重新切分并覆盖' : '确认并切分')
    : '预览模式'

  return (
    <div className="fixed inset-0 z-50 flex flex-col bg-[var(--sc-bg-app)] text-[var(--sc-text-primary)]">
      <div className="sc-modal-header flex items-center justify-between">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <h2 className="text-sm font-semibold text-[var(--sc-text-primary)]">场景预览确认</h2>
            {isDirty ? <span className="sc-tag sc-tag-warn">已修改</span> : null}
            {isTimelineReady ? <span className="sc-tag sc-tag-accent">已切分，可继续调整</span> : null}
          </div>
          {splitStatsSummary ? (
            <p className="mt-0.5 text-xs text-[var(--sc-text-muted)]">{splitStatsSummary}</p>
          ) : null}
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={handleConfirm}
            disabled={isToolbarBusy || scenes.length === 0 || !canSubmitSplit}
            className="sc-btn sc-btn-primary h-8 px-3"
          >
            {isConfirming ? '提交中...' : confirmLabel}
          </button>

          <button
            type="button"
            onClick={closeReviewModal}
            disabled={isTemporaryResplitting}
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
                    disabled={isToolbarBusy || effectiveDurationMs <= 0 || !canSubmitSplit}
                    className="sc-btn sc-btn-secondary h-7 px-2"
                  >
                    添加切分点
                  </button>
                  <button
                    type="button"
                    onClick={deleteBoundaryNearPlayhead}
                    disabled={isToolbarBusy || scenes.length <= 1 || !canSubmitSplit}
                    className="sc-btn sc-btn-secondary h-7 px-2"
                  >
                    删除临近切分点
                  </button>
                  <button
                    type="button"
                    onClick={handleOpenResplitConfig}
                    disabled={isToolbarBusy || scenes.length === 0 || !canSubmitSplit}
                    className="sc-btn sc-btn-secondary h-7 px-2"
                  >
                    重新切分
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
                  <button
                    type="button"
                    onClick={handleLocateTimelineLine}
                    disabled={effectiveDurationMs <= 0}
                    className="sc-btn sc-btn-secondary h-7 px-2"
                  >
                    定位时间轴线
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

      <ProcessingConfigModal
        isOpen={isResplitConfigOpen}
        initialSettings={resplitSettings}
        configMeta={processingConfigMeta}
        submitLabel="确认"
        persistOnSave={false}
        onClose={() => setIsResplitConfigOpen(false)}
        onSave={(settings) => {
          void handleSubmitTemporaryResplit(settings)
        }}
      />

      {isTemporaryResplitting ? (
        <div className="fixed inset-0 z-[70] flex items-center justify-center bg-[var(--sc-modal-overlay)] p-4">
          <div className="sc-modal-shell w-full max-w-md p-5">
            <h3 className="text-base font-semibold text-[var(--sc-text-primary)]">正在重新检测并切分</h3>
            <p className="mt-1 text-sm text-[var(--sc-text-secondary)]">{resplitStatusText}</p>
            <div className="mt-4">
              <Progress value={resplitProgressValue} showLabel />
            </div>
            <p className="mt-3 text-xs text-[var(--sc-text-muted)]">请稍候，完成后会在当前页面自动刷新。</p>
          </div>
        </div>
      ) : null}
    </div>
  )
}
