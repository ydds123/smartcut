import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { useUIStore } from '@/stores/uiStore'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { taskService } from '@/services/taskService'
import type { Scene, SplitStats, TaskStatus } from '@/types/task'
import { TimelineModalErrorBoundary } from '@/components/error/TimelineModalErrorBoundary'
import { useDraggableModal } from '@/hooks/useDraggableModal'
import { SceneListRail, type SceneListRailItem } from '@/components/shared/SceneListRail'
import { resolveAssetUrl } from '@/utils/assetUrl'

type SceneMark = 'STAR' | 'REVIEW' | 'APPROVED'
type TimelineMarkerKind = 'SCENE_BOUNDARY'

interface TimelineMarker {
  id: string
  sceneId: string
  atMs: number
  kind: TimelineMarkerKind
}

interface TimelineSession {
  selectedSceneId: string | null
  currentTimeSec: number
  autoContinueEnabled: boolean
  isMuted: boolean
  playbackRate: number
  selectedSceneIds: string[]
  selectedMarkerIds?: string[]
}

interface TimelineMarkerSelectionApi {
  toggleMarker: (markerId: string) => void
  clearMarkers: () => void
  getSelectedMarkers: () => TimelineMarker[]
}

const PLAYBACK_RATES = [0.5, 0.75, 1, 1.25, 1.5, 2]

function formatTimeCode(ms: number): string {
  const totalSeconds = Math.max(0, Math.floor(ms / 1000))
  const hours = Math.floor(totalSeconds / 3600)
  const minutes = Math.floor((totalSeconds % 3600) / 60)
  const seconds = totalSeconds % 60

  if (hours > 0) {
    return `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`
  }
  return `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`
}

function formatTimeRange(startMs: number, endMs: number): string {
  return `${formatTimeCode(startMs)} - ${formatTimeCode(endMs)}`
}

function formatElapsedMs(elapsedMs?: number): string {
  if (!Number.isFinite(elapsedMs) || elapsedMs === undefined || elapsedMs <= 0) {
    return '--'
  }
  if (elapsedMs >= 1000) {
    return `${(elapsedMs / 1000).toFixed(elapsedMs >= 10000 ? 0 : 1)}s`
  }
  return `${Math.round(elapsedMs)}ms`
}

function formatSplitStatsSummary(stats: SplitStats | null): string | null {
  if (!stats) {
    return null
  }
  const total = Math.max(0, stats.totalScenes ?? 0)
  const reused = Math.max(0, stats.reusedCount ?? 0)
  const rendered = Math.max(0, stats.renderedCount ?? 0)
  const fallback = stats.fallbackFullResplit ? '是' : '否'
  return `上次切分：复用 ${reused}/${total} · 重切 ${rendered} · 回退全量 ${fallback} · 耗时 ${formatElapsedMs(stats.totalElapsedMs)}`
}

function getMarksStorageKey(taskId: string): string {
  return `timeline:marks:${taskId}`
}

function getSessionStorageKey(taskId: string): string {
  return `timeline:session:${taskId}`
}

function safeJsonParse<T>(raw: string | null): T | null {
  if (!raw) {
    return null
  }

  try {
    return JSON.parse(raw) as T
  } catch {
    return null
  }
}

function parseTimecodeToMs(input: string): number | null {
  const normalized = input.trim()
  if (!normalized) {
    return null
  }

  const parts = normalized.split(':')
  if (parts.length !== 2 && parts.length !== 3) {
    return null
  }

  if (parts.some((part) => !/^\d+$/.test(part))) {
    return null
  }

  let hours = 0
  let minutes = 0
  let seconds = 0

  if (parts.length === 2) {
    minutes = Number(parts[0])
    seconds = Number(parts[1])
  } else {
    hours = Number(parts[0])
    minutes = Number(parts[1])
    seconds = Number(parts[2])
  }

  if (minutes >= 60 || seconds >= 60) {
    return null
  }

  return (hours * 3600 + minutes * 60 + seconds) * 1000
}

function findSceneIndexByQuery(query: string, scenes: Scene[]): number | null {
  const normalized = query.trim()
  if (!normalized) {
    return null
  }

  if (/^#?\d+$/.test(normalized)) {
    const numberPart = normalized.startsWith('#') ? normalized.slice(1) : normalized
    const sequenceNo = Number(numberPart)
    if (Number.isNaN(sequenceNo) || sequenceNo <= 0) {
      return null
    }

    return sequenceNo <= scenes.length ? sequenceNo - 1 : null
  }

  const timeMs = parseTimecodeToMs(normalized)
  if (timeMs === null) {
    return null
  }

  const inRangeIndex = scenes.findIndex(
    (scene) => timeMs >= scene.startMs && timeMs < scene.endMs
  )
  if (inRangeIndex >= 0) {
    return inRangeIndex
  }

  if (scenes.length === 0) {
    return null
  }

  if (timeMs < scenes[0].startMs) {
    return 0
  }

  const lastScene = scenes[scenes.length - 1]
  if (timeMs >= lastScene.endMs) {
    return scenes.length - 1
  }

  return null
}

function escapeCsvCell(value: string): string {
  const escaped = value.replace(/"/g, '""')
  return `"${escaped}"`
}

function downloadTextFile(filename: string, content: string, mimeType: string): void {
  const blob = new Blob([content], { type: mimeType })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
}

async function extractVideoPoster(videoUrl: string): Promise<string | null> {
  return new Promise((resolve) => {
    const video = document.createElement('video')
    const timeoutId = window.setTimeout(() => {
      cleanup()
      resolve(null)
    }, 8000)

    let settled = false

    const cleanup = () => {
      if (settled) {
        return
      }
      settled = true
      window.clearTimeout(timeoutId)
      video.pause()
      video.removeAttribute('src')
      video.load()
    }

    const finish = (value: string | null) => {
      cleanup()
      resolve(value)
    }

    const capture = () => {
      try {
        const width = video.videoWidth || 320
        const height = video.videoHeight || 180
        const canvas = document.createElement('canvas')
        canvas.width = width
        canvas.height = height

        const context = canvas.getContext('2d')
        if (!context) {
          finish(null)
          return
        }

        context.drawImage(video, 0, 0, width, height)
        const posterDataUrl = canvas.toDataURL('image/jpeg', 0.75)
        finish(posterDataUrl)
      } catch {
        finish(null)
      }
    }

    video.crossOrigin = 'anonymous'
    video.muted = true
    video.playsInline = true
    video.preload = 'metadata'

    video.addEventListener(
      'loadedmetadata',
      () => {
        if (!Number.isFinite(video.duration) || video.duration <= 0) {
          capture()
          return
        }
        video.currentTime = Math.min(0.15, Math.max(0.01, video.duration / 3))
      },
      { once: true }
    )
    video.addEventListener('seeked', capture, { once: true })
    video.addEventListener(
      'error',
      () => {
        finish(null)
      },
      { once: true }
    )

    video.src = videoUrl
  })
}

export function TimelineModal() {
  const { isTimelineOpen, selectedTaskId, closeTimeline, addToast, openReviewModal } = useUIStore()
  const queryClient = useQueryClient()
  const { modalRef, modalStyle, onHandlePointerDown, dragging } = useDraggableModal({
    isOpen: isTimelineOpen,
  })

  const [scenes, setScenes] = useState<Scene[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [selectedSceneIndex, setSelectedSceneIndex] = useState<number | null>(null)
  const [taskStatus, setTaskStatus] = useState<TaskStatus | null>(null)
  const [taskDisplayName, setTaskDisplayName] = useState<string>('')
  const [latestSplitStats, setLatestSplitStats] = useState<SplitStats | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [sceneMarks, setSceneMarks] = useState<Record<string, SceneMark>>({})
  const [selectedSceneIds, setSelectedSceneIds] = useState<Set<string>>(new Set())
  const [selectedMarkerIds, setSelectedMarkerIds] = useState<Set<string>>(new Set())
  const [scenePosterMap, setScenePosterMap] = useState<Record<string, string>>({})

  const [autoContinueEnabled, setAutoContinueEnabled] = useState(false)
  const [isMuted, setIsMuted] = useState(false)
  const [playbackRate, setPlaybackRate] = useState(1)
  const [pendingAutoPlay, setPendingAutoPlay] = useState(false)
  const [isSceneVideoPlaying, setIsSceneVideoPlaying] = useState(false)
  const [isReturningToEdit, setIsReturningToEdit] = useState(false)

  const videoRef = useRef<HTMLVideoElement | null>(null)
  const markerSelectionApiRef = useRef<TimelineMarkerSelectionApi | null>(null)
  const posterExtractingIdsRef = useRef<Set<string>>(new Set())
  const posterTaskTokenRef = useRef(0)
  const sequenceModeRef = useRef(false)
  const currentTimeRef = useRef(0)
  const restoreTimeRef = useRef<number | null>(null)
  const restoringSceneIdRef = useRef<string | null>(null)
  const marksHydratedRef = useRef(false)
  const sessionHydratedRef = useRef(false)

  const selectedScene = selectedSceneIndex !== null ? scenes[selectedSceneIndex] ?? null : null
  const selectedSceneVideoUrl = resolveAssetUrl(selectedScene?.filePath ?? null)

  const sceneIndexById = useMemo(() => {
    const map = new Map<string, number>()
    scenes.forEach((scene, index) => {
      map.set(scene.id, index)
    })
    return map
  }, [scenes])

  const timelineMarkers = useMemo<TimelineMarker[]>(() => {
    return scenes.map((scene) => ({
      id: `boundary:${scene.id}:${scene.startMs}`,
      sceneId: scene.id,
      atMs: scene.startMs,
      kind: 'SCENE_BOUNDARY',
    }))
  }, [scenes])

  const markerMap = useMemo(() => {
    const map = new Map<string, TimelineMarker>()
    timelineMarkers.forEach((marker) => {
      map.set(marker.id, marker)
    })
    return map
  }, [timelineMarkers])

  const selectedScenes = useMemo(
    () => scenes.filter((scene) => selectedSceneIds.has(scene.id)),
    [scenes, selectedSceneIds]
  )

  const timelineSceneItems = useMemo<SceneListRailItem[]>(
    () =>
      scenes.map((scene, index) => ({
        id: scene.id,
        index,
        startMs: scene.startMs,
        endMs: scene.endMs,
        previewUrl: scenePosterMap[scene.id] ?? resolveAssetUrl(scene.thumbnailPath),
      })),
    [scenePosterMap, scenes]
  )

  const toggleMarker = useCallback((markerId: string) => {
    setSelectedMarkerIds((current) => {
      const next = new Set(current)
      if (next.has(markerId)) {
        next.delete(markerId)
      } else {
        next.add(markerId)
      }
      return next
    })
  }, [])

  const clearMarkers = useCallback(() => {
    setSelectedMarkerIds(new Set())
  }, [])

  const getSelectedMarkers = useCallback((): TimelineMarker[] => {
    return [...selectedMarkerIds]
      .map((markerId) => markerMap.get(markerId))
      .filter((marker): marker is TimelineMarker => Boolean(marker))
  }, [markerMap, selectedMarkerIds])

  useEffect(() => {
    markerSelectionApiRef.current = {
      toggleMarker,
      clearMarkers,
      getSelectedMarkers,
    }
  }, [clearMarkers, getSelectedMarkers, toggleMarker])

  useEffect(() => {
    if (!isTimelineOpen || scenes.length === 0) {
      return
    }

    const focusIndexes =
      selectedSceneIndex === null
        ? Array.from({ length: Math.min(12, scenes.length) }, (_, index) => index)
        : Array.from(
            { length: 17 },
            (_, offset) => selectedSceneIndex - 8 + offset
          ).filter((index) => index >= 0 && index < scenes.length)

    const queue = focusIndexes
      .map((index) => scenes[index])
      .filter((scene) => {
        if (!scene?.filePath) {
          return false
        }
        if (scenePosterMap[scene.id]) {
          return false
        }
        if (posterExtractingIdsRef.current.has(scene.id)) {
          return false
        }
        return true
      })

    if (queue.length === 0) {
      return
    }

    const token = ++posterTaskTokenRef.current
    let cancelled = false
    let cursor = 0

    const runWorker = async () => {
      while (!cancelled && cursor < queue.length) {
        const scene = queue[cursor]
        cursor += 1

        if (!scene.filePath) {
          continue
        }

        const videoUrl = resolveAssetUrl(scene.filePath)
        if (!videoUrl) {
          continue
        }

        posterExtractingIdsRef.current.add(scene.id)
        const poster = await extractVideoPoster(videoUrl)
        posterExtractingIdsRef.current.delete(scene.id)

        if (cancelled || posterTaskTokenRef.current !== token || !poster) {
          continue
        }

        setScenePosterMap((current) => {
          if (current[scene.id]) {
            return current
          }
          return {
            ...current,
            [scene.id]: poster,
          }
        })
      }
    }

    const workerCount = Math.min(3, queue.length)
    void Promise.all(Array.from({ length: workerCount }, () => runWorker()))

    return () => {
      cancelled = true
    }
  }, [isTimelineOpen, scenePosterMap, scenes, selectedSceneIndex])

  const loadStoredSession = useCallback((taskId: string): TimelineSession | null => {
    const parsed = safeJsonParse<TimelineSession>(
      localStorage.getItem(getSessionStorageKey(taskId))
    )
    if (!parsed) {
      return null
    }

    return {
      selectedSceneId: parsed.selectedSceneId ?? null,
      currentTimeSec:
        typeof parsed.currentTimeSec === 'number' && parsed.currentTimeSec >= 0
          ? parsed.currentTimeSec
          : 0,
      autoContinueEnabled: Boolean(parsed.autoContinueEnabled),
      isMuted: Boolean(parsed.isMuted),
      playbackRate:
        typeof parsed.playbackRate === 'number' && PLAYBACK_RATES.includes(parsed.playbackRate)
          ? parsed.playbackRate
          : 1,
      selectedSceneIds: Array.isArray(parsed.selectedSceneIds)
        ? parsed.selectedSceneIds.filter((item) => typeof item === 'string')
        : [],
      selectedMarkerIds: Array.isArray(parsed.selectedMarkerIds)
        ? parsed.selectedMarkerIds.filter((item) => typeof item === 'string')
        : [],
    }
  }, [])

  const saveSession = useCallback(() => {
    if (!selectedTaskId || !sessionHydratedRef.current) {
      return
    }

    const selectedSceneId =
      selectedSceneIndex !== null ? scenes[selectedSceneIndex]?.id ?? null : null
    const payload: TimelineSession = {
      selectedSceneId,
      currentTimeSec: currentTimeRef.current,
      autoContinueEnabled,
      isMuted,
      playbackRate,
      selectedSceneIds: [...selectedSceneIds],
      selectedMarkerIds: [...selectedMarkerIds],
    }

    localStorage.setItem(getSessionStorageKey(selectedTaskId), JSON.stringify(payload))
  }, [
    autoContinueEnabled,
    isMuted,
    playbackRate,
    scenes,
    selectedSceneIds,
    selectedMarkerIds,
    selectedSceneIndex,
    selectedTaskId,
  ])

  const persistMarks = useCallback(
    (nextMarks: Record<string, SceneMark>) => {
      if (!selectedTaskId || !marksHydratedRef.current) {
        return
      }
      localStorage.setItem(getMarksStorageKey(selectedTaskId), JSON.stringify(nextMarks))
    },
    [selectedTaskId]
  )

  const updateSceneMarks = useCallback(
    (updater: (current: Record<string, SceneMark>) => Record<string, SceneMark>) => {
      setSceneMarks((current) => {
        const next = updater(current)
        persistMarks(next)
        return next
      })
    },
    [persistMarks]
  )

  const loadScenes = useCallback(async () => {
    if (!selectedTaskId) {
      return
    }

    setLoading(true)
    setError(null)
    setScenePosterMap({})
    posterExtractingIdsRef.current.clear()
    sessionHydratedRef.current = false
    marksHydratedRef.current = false

    try {
      const taskDetail = await taskService.getResult(selectedTaskId)
      const sortedScenes = [...taskDetail.scenes].sort(
        (a, b) => a.sequenceIndex - b.sequenceIndex
      )

      const validMarkerIds = new Set(
        sortedScenes.map((scene) => `boundary:${scene.id}:${scene.startMs}`)
      )

      const storedMarks =
        safeJsonParse<Record<string, SceneMark>>(
          localStorage.getItem(getMarksStorageKey(selectedTaskId))
        ) ?? {}
      const storedSession = loadStoredSession(selectedTaskId)

      const validSelectedIds = new Set(
        (storedSession?.selectedSceneIds ?? []).filter((sceneId) =>
          sortedScenes.some((scene) => scene.id === sceneId)
        )
      )
      const validStoredMarkers = new Set(
        (storedSession?.selectedMarkerIds ?? []).filter((markerId) =>
          validMarkerIds.has(markerId)
        )
      )

      let initialIndex: number | null = sortedScenes.length > 0 ? 0 : null
      if (storedSession?.selectedSceneId) {
        const restoredIndex = sortedScenes.findIndex(
          (scene) => scene.id === storedSession.selectedSceneId
        )
        if (restoredIndex >= 0) {
          initialIndex = restoredIndex
        }
      }

      setScenes(sortedScenes)
      setTaskStatus(taskDetail.status)
      setTaskDisplayName(taskDetail.displayName ?? '')
      setLatestSplitStats(taskDetail.latestSplitStats ?? null)
      setSceneMarks(storedMarks)
      setSelectedSceneIds(validSelectedIds)
      setSelectedMarkerIds(validStoredMarkers)
      setAutoContinueEnabled(storedSession?.autoContinueEnabled ?? false)
      setIsMuted(storedSession?.isMuted ?? false)
      setPlaybackRate(storedSession?.playbackRate ?? 1)
      setSelectedSceneIndex(initialIndex)

      restoreTimeRef.current = null
      restoringSceneIdRef.current = null
      currentTimeRef.current = 0

      if (
        initialIndex !== null &&
        storedSession?.selectedSceneId &&
        storedSession.currentTimeSec > 0
      ) {
        restoreTimeRef.current = storedSession.currentTimeSec
        restoringSceneIdRef.current = sortedScenes[initialIndex].id
        currentTimeRef.current = storedSession.currentTimeSec
      }

      marksHydratedRef.current = true
      sessionHydratedRef.current = true
    } catch (loadError) {
      console.error('Failed to load scenes:', loadError)
      setError('加载镜头失败，请稍后重试')
      setScenes([])
      setTaskStatus(null)
      setSelectedSceneIndex(null)
      setSelectedSceneIds(new Set())
      setSelectedMarkerIds(new Set())
      setScenePosterMap({})
      posterExtractingIdsRef.current.clear()
    } finally {
      setLoading(false)
    }
  }, [loadStoredSession, selectedTaskId])

  useEffect(() => {
    if (!isTimelineOpen || !selectedTaskId) {
      setScenes([])
      setError(null)
      setSelectedSceneIndex(null)
      setSceneMarks({})
      setSelectedSceneIds(new Set())
      setSelectedMarkerIds(new Set())
      setScenePosterMap({})
      setSearchQuery('')
      setTaskStatus(null)
      setTaskDisplayName('')
      setLatestSplitStats(null)
      setAutoContinueEnabled(false)
      setIsMuted(false)
      setPlaybackRate(1)
      setPendingAutoPlay(false)
      setIsSceneVideoPlaying(false)
      setIsReturningToEdit(false)
      sequenceModeRef.current = false
      marksHydratedRef.current = false
      sessionHydratedRef.current = false
      posterExtractingIdsRef.current.clear()
      currentTimeRef.current = 0
      restoreTimeRef.current = null
      restoringSceneIdRef.current = null
      return
    }

    loadScenes()
  }, [isTimelineOpen, loadScenes, selectedTaskId])

  useEffect(() => {
    if (!selectedTaskId || !marksHydratedRef.current) {
      return
    }
    localStorage.setItem(getMarksStorageKey(selectedTaskId), JSON.stringify(sceneMarks))
  }, [sceneMarks, selectedTaskId])

  useEffect(() => {
    if (!isTimelineOpen || !selectedTaskId) {
      return
    }

    const timer = window.setInterval(() => {
      saveSession()
    }, 2000)

    return () => {
      window.clearInterval(timer)
      saveSession()
    }
  }, [isTimelineOpen, saveSession, selectedTaskId])

  useEffect(() => {
    const video = videoRef.current
    if (!video) {
      return
    }
    video.muted = isMuted
  }, [isMuted, selectedScene?.id])

  useEffect(() => {
    const video = videoRef.current
    if (!video) {
      return
    }
    video.playbackRate = playbackRate
  }, [playbackRate, selectedScene?.id])

  useEffect(() => {
    if (!autoContinueEnabled) {
      sequenceModeRef.current = false
    }
  }, [autoContinueEnabled])

  useEffect(() => {
    if (!pendingAutoPlay) {
      return
    }

    if (!selectedSceneVideoUrl || !videoRef.current) {
      setPendingAutoPlay(false)
      return
    }

    const playPromise = videoRef.current.play()
    if (playPromise) {
      playPromise.catch(() => {
        addToast({
          type: 'warning',
          message: '自动续播被浏览器拦截，请手动点击播放',
        })
      })
    }
    setPendingAutoPlay(false)
  }, [addToast, pendingAutoPlay, selectedSceneVideoUrl])

  const handleOpenSelectedSceneFolder = useCallback(async () => {
    if (!selectedTaskId || !selectedScene?.id || !selectedScene.filePath) {
      addToast({
        type: 'warning',
        message: '该镜头暂无可打开的切片目录',
      })
      return
    }

    try {
      await taskService.openSceneFolder(selectedTaskId, selectedScene.id)
      addToast({
        type: 'success',
        message: '已打开切片所在文件夹',
      })
    } catch (error) {
      console.error('Open scene folder failed:', error)
      addToast({
        type: 'error',
        message: '打开文件夹失败，请检查后端权限',
      })
    }
  }, [addToast, selectedScene, selectedTaskId])

  const handleSelectScene = useCallback(
    (index: number, options?: { autoplay?: boolean; fromSequence?: boolean }) => {
      setSelectedSceneIndex(index)
      setIsSceneVideoPlaying(false)
      if (options?.autoplay) {
        setPendingAutoPlay(true)
      }
      if (!options?.fromSequence) {
        sequenceModeRef.current = false
      }
    },
    []
  )

  const handleStartPlayback = useCallback(() => {
    if (!selectedSceneVideoUrl || !videoRef.current) {
      addToast({
        type: 'warning',
        message: '该镜头暂无可播放的视频文件',
      })
      return
    }

    sequenceModeRef.current = autoContinueEnabled
    const playPromise = videoRef.current.play()
    if (playPromise) {
      playPromise.catch(() => {
        addToast({
          type: 'warning',
          message: '播放失败，请检查浏览器权限后重试',
        })
      })
    }
  }, [addToast, autoContinueEnabled, selectedSceneVideoUrl])

  const handleVideoEnded = useCallback(() => {
    setIsSceneVideoPlaying(false)
    if (!autoContinueEnabled || !sequenceModeRef.current || selectedSceneIndex === null) {
      return
    }

    const nextIndex = selectedSceneIndex + 1
    if (nextIndex >= scenes.length) {
      sequenceModeRef.current = false
      addToast({
        type: 'info',
        message: '已播放到最后一个镜头',
      })
      return
    }

    handleSelectScene(nextIndex, {
      autoplay: true,
      fromSequence: true,
    })
  }, [addToast, autoContinueEnabled, handleSelectScene, scenes.length, selectedSceneIndex])

  const handleVideoPause = useCallback(() => {
    setIsSceneVideoPlaying(false)
    const video = videoRef.current
    if (!video || video.ended) {
      return
    }
    sequenceModeRef.current = false
  }, [])

  const handleVideoLoadedMetadata = useCallback(() => {
    const video = videoRef.current
    if (!video || !selectedScene) {
      return
    }

    video.muted = isMuted
    video.playbackRate = playbackRate

    if (
      restoreTimeRef.current !== null &&
      restoringSceneIdRef.current === selectedScene.id
    ) {
      const maxSeek = Number.isFinite(video.duration)
        ? Math.max(0, video.duration - 0.05)
        : restoreTimeRef.current
      video.currentTime = Math.min(restoreTimeRef.current, maxSeek)
      currentTimeRef.current = video.currentTime
      restoreTimeRef.current = null
      restoringSceneIdRef.current = null
    }
  }, [isMuted, playbackRate, selectedScene])

  const handleVideoTimeUpdate = useCallback(() => {
    const currentVideo = videoRef.current
    if (!currentVideo) {
      return
    }
    currentTimeRef.current = currentVideo.currentTime
  }, [])

  const handleJumpToScene = useCallback(() => {
    const targetIndex = findSceneIndexByQuery(searchQuery, scenes)
    if (targetIndex === null) {
      addToast({
        type: 'warning',
        message: '未找到匹配镜头，支持 #序号 / MM:SS / HH:MM:SS',
      })
      return
    }

    handleSelectScene(targetIndex)
    addToast({
      type: 'success',
      message: `已跳转到镜头 #${targetIndex + 1}`,
      duration: 1500,
    })
  }, [addToast, handleSelectScene, scenes, searchQuery])

  const cycleSceneMark = useCallback(
    (sceneId: string) => {
      updateSceneMarks((current) => {
        const next = { ...current }
        const value = current[sceneId]
        if (!value) {
          next[sceneId] = 'STAR'
        } else if (value === 'STAR') {
          next[sceneId] = 'REVIEW'
        } else if (value === 'REVIEW') {
          next[sceneId] = 'APPROVED'
        } else {
          delete next[sceneId]
        }
        return next
      })
    },
    [updateSceneMarks]
  )

  const setMarkForSelectedScene = useCallback(
    (mark: SceneMark | null) => {
      if (!selectedScene) {
        return
      }
      updateSceneMarks((current) => {
        const next = { ...current }
        if (mark) {
          next[selectedScene.id] = mark
        } else {
          delete next[selectedScene.id]
        }
        return next
      })
    },
    [selectedScene, updateSceneMarks]
  )

  const toggleSceneSelection = useCallback((sceneId: string, checked: boolean) => {
    setSelectedSceneIds((current) => {
      const next = new Set(current)
      if (checked) {
        next.add(sceneId)
      } else {
        next.delete(sceneId)
      }
      return next
    })
  }, [])

  const handleToggleAllScenes = useCallback(() => {
    setSelectedSceneIds((current) => {
      const next = new Set(current)
      const shouldClear = scenes.length > 0 && scenes.every((scene) => next.has(scene.id))
      if (shouldClear) {
        scenes.forEach((scene) => next.delete(scene.id))
      } else {
        scenes.forEach((scene) => next.add(scene.id))
      }
      return next
    })
  }, [scenes])

  const handleBatchSetMark = useCallback(
    (mark: SceneMark | null) => {
      if (selectedScenes.length === 0) {
        addToast({
          type: 'warning',
          message: '请先勾选要批量处理的镜头',
        })
        return
      }

      updateSceneMarks((current) => {
        const next = { ...current }
        selectedScenes.forEach((scene) => {
          if (mark) {
            next[scene.id] = mark
          } else {
            delete next[scene.id]
          }
        })
        return next
      })

      addToast({
        type: 'success',
        message: `已更新 ${selectedScenes.length} 个镜头标记`,
      })
    },
    [addToast, selectedScenes, updateSceneMarks]
  )

  const handleBatchExportJson = useCallback(() => {
    if (selectedScenes.length === 0) {
      addToast({
        type: 'warning',
        message: '请先勾选要导出的镜头',
      })
      return
    }

    const payload = selectedScenes.map((scene) => {
      const index = (sceneIndexById.get(scene.id) ?? 0) + 1
      return {
        sceneNumber: index,
        timeRange: formatTimeRange(scene.startMs, scene.endMs),
        startMs: scene.startMs,
        endMs: scene.endMs,
        durationMs: scene.endMs - scene.startMs,
        mark: sceneMarks[scene.id] ?? null,
        filePath: scene.filePath,
        thumbnailPath: scene.thumbnailPath,
      }
    })

    const taskPart = selectedTaskId ?? 'task'
    downloadTextFile(
      `timeline-${taskPart}-scenes.json`,
      JSON.stringify(payload, null, 2),
      'application/json;charset=utf-8'
    )

    addToast({
      type: 'success',
      message: `已导出 ${selectedScenes.length} 条 JSON 记录`,
    })
  }, [addToast, sceneIndexById, sceneMarks, selectedScenes, selectedTaskId])

  const handleBatchExportCsv = useCallback(() => {
    if (selectedScenes.length === 0) {
      addToast({
        type: 'warning',
        message: '请先勾选要导出的镜头',
      })
      return
    }

    const header = [
      'scene_number',
      'start_ms',
      'end_ms',
      'time_range',
      'duration_ms',
      'mark',
      'file_path',
      'thumbnail_path',
    ]
    const rows = selectedScenes.map((scene) => {
      const sceneNumber = (sceneIndexById.get(scene.id) ?? 0) + 1
      const cells = [
        String(sceneNumber),
        String(scene.startMs),
        String(scene.endMs),
        formatTimeRange(scene.startMs, scene.endMs),
        String(scene.endMs - scene.startMs),
        sceneMarks[scene.id] ?? '',
        scene.filePath ?? '',
        scene.thumbnailPath ?? '',
      ]
      return cells.map((cell) => escapeCsvCell(cell)).join(',')
    })

    const csv = [header.join(','), ...rows].join('\n')
    const taskPart = selectedTaskId ?? 'task'
    downloadTextFile(`timeline-${taskPart}-scenes.csv`, csv, 'text/csv;charset=utf-8')

    addToast({
      type: 'success',
      message: `已导出 ${selectedScenes.length} 条 CSV 记录`,
    })
  }, [addToast, sceneIndexById, sceneMarks, selectedScenes, selectedTaskId])

  const handleBatchOpenSourceClips = useCallback(() => {
    if (selectedScenes.length === 0) {
      addToast({
        type: 'warning',
        message: '请先勾选要打开的镜头',
      })
      return
    }

    const urls = selectedScenes
      .map((scene) => resolveAssetUrl(scene.filePath))
      .filter((url): url is string => Boolean(url))

    if (urls.length === 0) {
      addToast({
        type: 'warning',
        message: '所选镜头没有可打开的切片文件',
      })
      return
    }

    if (urls.length > 8) {
      addToast({
        type: 'warning',
        message: `将尝试打开 ${urls.length} 个窗口，浏览器可能拦截部分弹窗`,
      })
    }

    let blocked = 0
    urls.forEach((url) => {
      const result = window.open(url, '_blank', 'noopener,noreferrer')
      if (!result) {
        blocked += 1
      }
    })

    if (blocked > 0) {
      addToast({
        type: 'warning',
        message: `已请求打开 ${urls.length} 个窗口，疑似被拦截 ${blocked} 个`,
      })
      return
    }

    addToast({
      type: 'success',
      message: `已打开 ${urls.length} 个切片窗口`,
    })
  }, [addToast, selectedScenes])

  const handleReturnToEdit = useCallback(async () => {
    if (!selectedTaskId || isReturningToEdit) {
      return
    }

    try {
      setIsReturningToEdit(true)
      const result = await taskService.resetReviewFromTimeline(selectedTaskId)
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['tasks'] }),
        queryClient.invalidateQueries({ queryKey: ['tasks', selectedTaskId] }),
        queryClient.invalidateQueries({ queryKey: ['tasks', selectedTaskId, 'review-data'] }),
      ])

      closeTimeline()
      openReviewModal(selectedTaskId)
      addToast({
        type: 'success',
        message: `已同步 ${result.scenesCount} 个镜头到审核页`,
      })
    } catch (error) {
      console.error('Return to review failed:', error)
      addToast({
        type: 'error',
        message: '返回编辑失败：无法同步当前工作台镜头',
      })
    } finally {
      setIsReturningToEdit(false)
    }
  }, [addToast, closeTimeline, isReturningToEdit, openReviewModal, queryClient, selectedTaskId])

  const isTimelineReady = taskStatus === 'TIMELINE_READY'
  const isDetailStatus =
    taskStatus === 'COMPLETED'
    || taskStatus === 'FAILED'
    || taskStatus === 'ANALYZE_FAILED'
  const splitStatsSummary = formatSplitStatsSummary(latestSplitStats)

  if (!isTimelineOpen) {
    return null
  }

  return (
    <TimelineModalErrorBoundary>
      <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-5">
        <div className="absolute inset-0 bg-[var(--sc-modal-overlay)]" onClick={closeTimeline} />

        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="timeline-modal-title"
          data-testid="timeline-modal"
          ref={modalRef}
          style={modalStyle}
          className="sc-modal-shell relative flex h-[86vh] min-h-[720px] w-full max-w-[1380px] flex-col overflow-hidden text-[var(--sc-text-primary)]"
        >
          <div
            className={`sc-modal-header flex items-center justify-between ${dragging ? 'cursor-grabbing' : 'cursor-move'}`}
            onPointerDown={onHandlePointerDown}
          >
            <div className="min-w-0">
              <h2 id="timeline-modal-title" className="text-sm font-semibold text-[var(--sc-text-primary)]">
                时间轴工作台
              </h2>
              <p className="truncate text-sm text-[var(--sc-text-secondary)]">
                {taskDisplayName || selectedTaskId || '未命名任务'}
              </p>
              {splitStatsSummary ? (
                <p className="truncate text-xs text-[var(--sc-text-muted)]">{splitStatsSummary}</p>
              ) : null}
            </div>
            <div className="flex items-center gap-2" data-drag-ignore="true">
              {isDetailStatus && (
                <button
                  type="button"
                  onClick={closeTimeline}
                  className="sc-btn sc-btn-secondary h-8 px-3"
                >
                  返回工作台
                </button>
              )}
              {isTimelineReady && (
                <>
                  <button
                    type="button"
                    onClick={handleReturnToEdit}
                    disabled={isReturningToEdit}
                    className="sc-btn sc-btn-secondary h-8 px-3"
                  >
                    {isReturningToEdit ? '同步中...' : '返回编辑'}
                  </button>
                </>
              )}
              <button
                type="button"
                onClick={closeTimeline}
                aria-label="关闭时间轴"
                className="sc-btn sc-btn-ghost sc-btn-icon"
              >
                <svg className="h-4.5 w-4.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M6 18L18 6M6 6l12 12"
                  />
                </svg>
              </button>
            </div>
          </div>

          <div className="flex-1 min-h-0 p-3">
            {loading ? (
              <div className="flex h-full items-center justify-center">
                <div className="flex flex-col items-center gap-3">
                  <div className="h-8 w-8 animate-spin rounded-full border-4 border-[var(--sc-accent)] border-t-transparent" />
                  <p className="text-sm text-[var(--sc-text-muted)]">加载镜头中...</p>
                </div>
              </div>
            ) : error ? (
              <div className="flex h-full items-center justify-center">
                <Card className="sc-surface p-8 text-center !shadow-none">
                  <svg
                    className="mx-auto mb-3 h-10 w-10 text-[var(--sc-danger)]"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                    />
                  </svg>
                  <p className="text-sm text-[var(--sc-text-muted)]">{error}</p>
                  <div className="mt-4">
                    <Button variant="secondary" size="sm" onClick={loadScenes}>
                      重试
                    </Button>
                  </div>
                </Card>
              </div>
            ) : scenes.length === 0 ? (
              <div className="flex h-full items-center justify-center">
                <Card className="sc-surface p-8 text-center text-[var(--sc-text-muted)] !shadow-none">
                  <p className="text-sm">暂无镜头数据</p>
                  <p className="mt-1 text-xs">请先处理视频任务</p>
                </Card>
              </div>
            ) : (
              <div className="flex h-full min-h-0 gap-3.5">
                <div className="flex w-[270px] min-w-[270px] min-h-0">
                  <SceneListRail
                    items={timelineSceneItems}
                    selectedIndex={selectedSceneIndex}
                    onSelect={(index) => handleSelectScene(index)}
                    variant="workspace"
                    density="comfortable"
                    isPlaying={isSceneVideoPlaying}
                    enableAutoScrollOnSelection
                    autoScrollTrigger="always"
                    showDurationBadge
                    showFooterTotalDuration
                    listTestId="timeline-scenes-grid"
                    formatTimeLabel={formatTimeCode}
                  />
                </div>

                <Card className="flex min-h-0 flex-1 flex-col border border-[var(--sc-border-subtle)] !bg-[var(--sc-bg-panel)] !shadow-none p-3">
                  {selectedScene ? (
                    <>
                      <div className="flex items-center justify-between border-b border-[var(--sc-border-subtle)] pb-2.5">
                        <p className="text-xs font-semibold text-[var(--sc-text-secondary)]">
                          场景 #{selectedSceneIndex! + 1} · {formatTimeCode(selectedScene.startMs)} - {formatTimeCode(selectedScene.endMs)}
                        </p>
                        <div className="flex items-center gap-2">
                          <button
                            type="button"
                            role="switch"
                            aria-checked={autoContinueEnabled}
                            aria-label="自动续播"
                            onClick={() => setAutoContinueEnabled((value) => !value)}
                            className={`sc-btn inline-flex h-8 items-center gap-2 px-2.5 text-xs font-medium ${
                              autoContinueEnabled
                                ? 'border-[var(--sc-accent)] bg-[var(--sc-accent-soft)] text-[var(--sc-text-primary)]'
                                : 'border-[var(--sc-border-subtle)] bg-[var(--sc-bg-surface)] text-[var(--sc-text-secondary)] hover:bg-[var(--sc-bg-elevated)]'
                            }`}
                          >
                            <span
                              className={`relative inline-flex h-4.5 w-8 items-center rounded-full transition-colors ${
                                autoContinueEnabled ? 'bg-[var(--sc-accent)]' : 'bg-[var(--sc-border-strong)]'
                              }`}
                            >
                              <span
                                className={`h-3.5 w-3.5 rounded-full bg-white shadow transition-transform ${
                                  autoContinueEnabled ? 'translate-x-[14px]' : 'translate-x-[2px]'
                                }`}
                              />
                            </span>
                            <span>自动续播</span>
                          </button>
                          <label className="inline-flex h-8 items-center gap-2 rounded-md border border-[var(--sc-border-subtle)] bg-[var(--sc-bg-surface)] px-2 text-xs font-medium text-[var(--sc-text-secondary)]">
                            倍速
                            <select
                              value={playbackRate}
                              onChange={(event) => {
                                const nextRate = Number(event.target.value)
                                if (PLAYBACK_RATES.includes(nextRate)) {
                                  setPlaybackRate(nextRate)
                                }
                              }}
                              className="sc-input h-6 px-1.5 text-xs"
                              aria-label="时间轴预览播放速度"
                            >
                              {PLAYBACK_RATES.map((rate) => (
                                <option key={rate} value={rate}>
                                  {rate}x
                                </option>
                              ))}
                            </select>
                          </label>
                        </div>
                      </div>

                      <div className="mt-2.5 flex min-h-0 flex-1 flex-col overflow-hidden">
                        <div className="overflow-hidden rounded-lg border border-[var(--sc-border-subtle)] bg-black">
                          {selectedSceneVideoUrl ? (
                            <video
                              key={selectedScene.id}
                              ref={videoRef}
                              src={selectedSceneVideoUrl}
                              controls
                              preload="metadata"
                              className="aspect-video w-full bg-black"
                              onPlay={() => {
                                setIsSceneVideoPlaying(true)
                                if (autoContinueEnabled) {
                                  sequenceModeRef.current = true
                                }
                              }}
                              onEnded={handleVideoEnded}
                              onPause={handleVideoPause}
                              onLoadedMetadata={handleVideoLoadedMetadata}
                              onTimeUpdate={handleVideoTimeUpdate}
                            />
                          ) : (
                            <div className="flex aspect-video items-center justify-center text-sm text-[var(--sc-text-muted)]">
                              该镜头暂无可预览视频文件
                            </div>
                          )}
                        </div>

                        <div className="mt-2 rounded-md border border-[var(--sc-border-subtle)] bg-[var(--sc-bg-surface)] px-3 py-2 text-xs text-[var(--sc-text-secondary)]">
                          已选择场景 #{selectedSceneIndex! + 1}
                        </div>
                      </div>
                    </>
                  ) : (
                    <div className="flex h-full items-center justify-center text-sm text-[var(--sc-text-muted)]">
                      请选择镜头
                    </div>
                  )}

                  <div className="mt-2 flex items-center justify-end gap-2 border-t border-[var(--sc-border-subtle)] pt-2">
                    <button
                      type="button"
                      onClick={() => {
                        void handleOpenSelectedSceneFolder()
                      }}
                      className="sc-btn sc-btn-secondary h-8 px-3 text-[var(--sc-text-secondary)]"
                    >
                      打开所在文件夹
                    </button>
                    <button
                      type="button"
                      onClick={closeTimeline}
                      className="sc-btn sc-btn-secondary h-8 px-3"
                    >
                      {isDetailStatus ? '返回工作台' : '关闭'}
                    </button>
                  </div>

                  <div className="hidden" aria-hidden="true">
                    <button type="button" onClick={handleStartPlayback}>
                      debug-play
                    </button>
                    <button type="button" onClick={handleJumpToScene}>
                      debug-jump
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        if (selectedScene) {
                          cycleSceneMark(selectedScene.id)
                        }
                      }}
                    >
                      debug-cycle-mark
                    </button>
                    <button type="button" onClick={() => setMarkForSelectedScene('STAR')}>
                      debug-set-mark
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        if (selectedScene) {
                          toggleSceneSelection(selectedScene.id, true)
                        }
                      }}
                    >
                      debug-select-scene
                    </button>
                    <button type="button" onClick={handleToggleAllScenes}>
                      debug-toggle-all
                    </button>
                    <button type="button" onClick={() => handleBatchSetMark('REVIEW')}>
                      debug-batch-mark
                    </button>
                    <button type="button" onClick={handleBatchExportJson}>
                      debug-export-json
                    </button>
                    <button type="button" onClick={handleBatchExportCsv}>
                      debug-export-csv
                    </button>
                    <button type="button" onClick={handleBatchOpenSourceClips}>
                      debug-open-clips
                    </button>
                  </div>
                </Card>
              </div>
            )}
          </div>
        </div>
      </div>
    </TimelineModalErrorBoundary>
  )
}
