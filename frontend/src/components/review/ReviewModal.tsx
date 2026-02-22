import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useUIStore } from '@/stores/uiStore'
import { useApproveReview, useReviewData, useSaveReviewData, useTask } from '@/hooks/useTasks'
import type { ReviewScene } from '@/types/task'
import { ReviewPlaybackControls } from './ReviewPlaybackControls'
import { ReviewShotSummaryPanel } from './ReviewShotSummaryPanel'
import { ReviewTimelineWorkspace, type ReviewTimelineWorkspaceHandle } from './ReviewTimelineWorkspace'
import { clamp, resolveAssetUrl } from './reviewUtils'

const MIN_PIXELS_PER_SECOND = 10
const MAX_PIXELS_PER_SECOND = 200

export function ReviewModal() {
  const { isReviewModalOpen, reviewTaskId, closeReviewModal, openTimeline, addToast } = useUIStore()

  const [scenes, setScenes] = useState<ReviewScene[]>([])
  const [isDirty, setIsDirty] = useState(false)
  const [selectedSceneIndex, setSelectedSceneIndex] = useState<number | null>(null)
  const [playheadMs, setPlayheadMs] = useState(0)
  const [isPlaying, setIsPlaying] = useState(false)
  const [videoDurationMs, setVideoDurationMs] = useState(0)
  const [videoLoadFailed, setVideoLoadFailed] = useState(false)
  const [pixelsPerSecond, setPixelsPerSecond] = useState(50)
  const videoRef = useRef<HTMLVideoElement | null>(null)
  const timelineRef = useRef<ReviewTimelineWorkspaceHandle | null>(null)

  const { data: taskDetail } = useTask(reviewTaskId ?? '')
  const { data, isLoading } = useReviewData(reviewTaskId ?? '', isReviewModalOpen && !!reviewTaskId)
  const saveReviewData = useSaveReviewData()
  const approveReview = useApproveReview()

  const durationMs = data?.detectionResult?.durationMs ?? 0
  const isTimelineReady = data?.status === 'TIMELINE_READY'
  const sourceVideoUrl = useMemo(() => resolveAssetUrl(taskDetail?.filePath ?? null), [taskDetail?.filePath])
  const effectiveDurationMs = videoDurationMs > 0 ? videoDurationMs : durationMs

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

  const handleZoomSliderChange = useCallback((event: React.ChangeEvent<HTMLInputElement>) => {
    prepareZoomAnchor()
    setPixelsPerSecond(Number(event.target.value))
  }, [prepareZoomAnchor])

  if (!isReviewModalOpen) {
    return null
  }

  const isConfirming = saveReviewData.isPending || approveReview.isPending
  const confirmLabel = isTimelineReady ? '重新切分并覆盖' : '确认并切分'

  return (
    <div className="fixed inset-0 z-50 flex flex-col bg-[#09090b]">
      <div className="flex items-center justify-between border-b border-[#27272a] bg-[#111113] px-4 py-2.5">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <h2 className="text-sm font-semibold text-[#f4f4f5]">场景预览确认</h2>
            {isDirty ? <span className="text-xs text-[#f59e0b]">已修改</span> : null}
            <span className="text-xs text-[#71717a]">{scenes.length} 个镜头</span>
            {isTimelineReady ? <span className="text-xs text-[#60a5fa]">已切分，可继续调整</span> : null}
          </div>
          <p className="truncate text-xs text-[#71717a]">参考 Storyboard 成片编辑布局 · 当前任务 {reviewTaskId ?? '--'}</p>
        </div>

        <div className="flex items-center gap-2">
          {isTimelineReady ? (
            <button
              type="button"
              onClick={handleViewTimeline}
              className="inline-flex h-8 items-center rounded-md border border-[#3f3f46] bg-[#18181b] px-3 text-sm text-[#e4e4e7] hover:bg-[#27272a]"
            >
              查看工作台
            </button>
          ) : null}

          <button
            type="button"
            onClick={handleConfirm}
            disabled={isConfirming || scenes.length === 0}
            className="inline-flex h-8 items-center rounded-md bg-[#2563eb] px-3 text-sm font-medium text-white transition-colors hover:bg-[#1d4ed8] disabled:cursor-not-allowed disabled:bg-[#64748b]"
          >
            {isConfirming ? '提交中...' : confirmLabel}
          </button>

          <button
            type="button"
            onClick={closeReviewModal}
            className="inline-flex h-8 w-8 items-center justify-center rounded-full text-[#a1a1aa] hover:bg-[#27272a] hover:text-white"
            aria-label="关闭"
          >
            ✕
          </button>
        </div>
      </div>

      {isLoading ? (
        <div className="flex flex-1 items-center justify-center text-[#a1a1aa]">加载审核数据中...</div>
      ) : (
        <div className="grid min-h-0 flex-1 grid-cols-[minmax(0,1fr)_320px] overflow-hidden">
          <div className="flex min-h-0 min-w-0 flex-col bg-[#0a0a0a]">
            <div className="grid min-h-0 flex-1 grid-rows-[minmax(260px,7fr)_56px_48px_minmax(160px,3fr)]">
              <div className="border-b border-[#27272a] bg-[#0f0f0f] p-4">
                <div className="mb-2 flex items-center justify-between">
                  <span className="text-sm font-semibold text-[#f4f4f5]">视频预览</span>
                  <span className="font-mono text-xs text-[#a1a1aa]">
                    {selectedSceneIndex !== null ? `镜头 #${selectedSceneIndex + 1}` : '未定位镜头'}
                  </span>
                </div>
                <div className="h-[calc(100%-28px)] overflow-hidden rounded-lg border border-[#27272a] bg-black">
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
                    <div className="flex h-full items-center justify-center text-sm text-[#71717a]">
                      {sourceVideoUrl ? '原视频加载失败，无法播放' : '未找到原视频源'}
                    </div>
                  )}
                </div>
              </div>

              <ReviewPlaybackControls
                playheadMs={playheadMs}
                durationMs={effectiveDurationMs}
                isPlaying={isPlaying}
                onSeek={seekPlayhead}
                onStepSecondBack={() => stepPlayhead(-1000)}
                onStepSecondForward={() => stepPlayhead(1000)}
                onTogglePlay={() => {
                  void handleTogglePlayback()
                }}
              />

              <div className="flex items-center justify-between border-b border-[#27272a] bg-[#0f0f0f] px-4 text-xs text-[#a1a1aa]">
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => handleAddBoundary(playheadMs)}
                    className="rounded border border-[#3f3f46] bg-[#18181b] px-2 py-1 text-[#d4d4d8] hover:bg-[#27272a]"
                  >
                    添加切分点
                  </button>
                  <button
                    type="button"
                    onClick={deleteBoundaryNearPlayhead}
                    className="rounded border border-[#3f3f46] bg-[#18181b] px-2 py-1 text-[#d4d4d8] hover:bg-[#27272a]"
                  >
                    删除临近切分点
                  </button>
                </div>

                <div className="flex items-center gap-2">
                  <span className="text-[#71717a]">缩放</span>
                  <input
                    type="range"
                    min={MIN_PIXELS_PER_SECOND}
                    max={MAX_PIXELS_PER_SECOND}
                    value={pixelsPerSecond}
                    onChange={handleZoomSliderChange}
                    className="h-1.5 w-32 accent-[#2563eb]"
                  />
                  <span className="w-14 text-right font-mono">{pixelsPerSecond}px/s</span>
                </div>
              </div>

              <div className="min-h-0 bg-[#09090b] px-4">
                {effectiveDurationMs > 0 ? (
                  <ReviewTimelineWorkspace
                    ref={timelineRef}
                    taskId={reviewTaskId ?? ''}
                    scenes={scenes}
                    durationMs={effectiveDurationMs}
                    playheadMs={playheadMs}
                    isPlaying={isPlaying}
                    pixelsPerSecond={pixelsPerSecond}
                    onPixelsPerSecondChange={setPixelsPerSecond}
                    onAddBoundary={handleAddBoundary}
                    onDeleteBoundary={handleDeleteBoundary}
                    onSetPlayhead={seekPlayhead}
                  />
                ) : (
                  <div className="flex h-full items-center justify-center text-[#71717a]">无可用时间轴数据</div>
                )}
              </div>
            </div>
          </div>

          <div className="min-h-0 border-l border-[#27272a] bg-[#0f0f0f]">
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
