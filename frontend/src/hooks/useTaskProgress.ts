import { useState, useEffect, useCallback, useRef } from 'react'
import { ACTIVE_TASK_STATUSES, TERMINAL_TASK_STATUSES, type TaskStatus } from '@/types/task'
import { taskService } from '@/services/taskService'
import { playSound } from '@/utils/soundPlayer'

/**
 * SSE 进度 Hook（带平滑进度更新）
 *
 * 使用 Server-Sent Events 实时接收任务处理进度
 */
const ACTIVE_PROGRESS_STATUSES = new Set<TaskStatus>(ACTIVE_TASK_STATUSES)
const TERMINAL_PROGRESS_STATUSES = new Set<TaskStatus>(TERMINAL_TASK_STATUSES)

export function useTaskProgress(taskId: string, taskStatus?: string, taskProgress?: number) {
  const [progress, setProgress] = useState(0)
  const [status, setStatus] = useState<TaskStatus>(
    (taskStatus as TaskStatus) || 'PENDING'
  )
  const [totalScenes, setTotalScenes] = useState<number | null>(null)
  const [isConnected, setIsConnected] = useState(false)
  const [error, setError] = useState<Error | null>(null)

  // 跟踪之前的状态，用于检测状态变化
  const previousStatusRef = useRef<TaskStatus>('PENDING')

  // 平滑进度更新（避免频繁更新）
  const progressUpdateTimer = useRef<NodeJS.Timeout | undefined>(undefined)
  const smoothedProgress = useRef(0)
  const lastEventTimestampRef = useRef(0)

  useEffect(() => {
    // 同步外部任务状态，避免 SSE 中断后状态与列表状态不一致
    if (taskStatus) {
      setStatus(taskStatus as TaskStatus)
      if (typeof taskProgress === 'number' && Number.isFinite(taskProgress)) {
        const clamped = Math.max(0, Math.min(100, Math.round(taskProgress)))
        smoothedProgress.current = clamped
        setProgress(clamped)
      } else if (taskStatus === 'COMPLETED') {
        smoothedProgress.current = 100
        setProgress(100)
      }
    }
  }, [taskStatus, taskProgress])

  useEffect(() => {
    // 仅对排队中/处理中任务建立 SSE，避免 PENDING 任务占用连接
    if (!taskId || !taskStatus || !ACTIVE_PROGRESS_STATUSES.has(taskStatus as TaskStatus)) {
      return
    }

    let eventSource: EventSource | null = null

    // 使用 taskService 的 SSE 监听
    eventSource = taskService.listenProgress(taskId, (data) => {
      if (data.type === 'error') {
        setIsConnected(false)
        setError(new Error(data.errorMessage || data.errorCode || 'stream error'))
        return
      }

      if (typeof data.progress !== 'number' || !data.status) {
        return
      }

      if (data.timestamp < lastEventTimestampRef.current) {
        return
      }
      lastEventTimestampRef.current = data.timestamp

      // 目标进度
      const targetProgress = Math.max(0, Math.min(100, Math.round(data.progress)))

      // 平滑过渡到目标进度（每次最多增加 5%）
      const smoothUpdate = () => {
        if (smoothedProgress.current > targetProgress) {
          smoothedProgress.current = targetProgress
          setProgress(targetProgress)
          return
        }
        if (smoothedProgress.current < targetProgress) {
          smoothedProgress.current = Math.min(
            targetProgress,
            smoothedProgress.current + 5
          )
          setProgress(Math.round(smoothedProgress.current))
          progressUpdateTimer.current = setTimeout(smoothUpdate, 100)
        } else {
          smoothedProgress.current = targetProgress
          setProgress(targetProgress)
        }
      }

      // 取消之前的定时器
      if (progressUpdateTimer.current) {
        clearTimeout(progressUpdateTimer.current)
      }

      smoothUpdate()
      setStatus(data.status as TaskStatus)
      setTotalScenes(data.totalScenes ?? null)
      setIsConnected(true)
      setError(null)

      // 检测状态变化并播放提示音
      const previousStatus = previousStatusRef.current
      if (data.status !== previousStatus) {
        if (data.status === 'COMPLETED' && previousStatus !== 'COMPLETED') {
          playSound('complete')
        } else if (
          (data.status === 'FAILED' && previousStatus !== 'FAILED') ||
          (data.status === 'ANALYZE_FAILED' && previousStatus !== 'ANALYZE_FAILED')
        ) {
          playSound('error')
        }
        previousStatusRef.current = data.status as TaskStatus
      }

      // 如果任务完成或失败，关闭连接
      if (TERMINAL_PROGRESS_STATUSES.has(data.status)) {
        setIsConnected(false)
        if (eventSource) {
          eventSource.close()
          eventSource = null
        }
      }
    }, (streamError) => {
      setIsConnected(false)
      setError(streamError)
    })

    // 连接成功
    eventSource.onopen = () => {
      setIsConnected(true)
      setError(null)
    }

    // 清理
    return () => {
      if (eventSource) {
        eventSource.close()
      }
      setIsConnected(false)
      if (progressUpdateTimer.current) {
        clearTimeout(progressUpdateTimer.current)
      }
    }
  }, [taskId, taskStatus])

  return {
    progress,
    status,
    totalScenes,
    isConnected,
    error,
  }
}

/**
 * 上传进度 Hook
 */
export function useUploadProgress() {
  const [progress, setProgress] = useState(0)
  const [isUploading, setIsUploading] = useState(false)

  const startUpload = useCallback(() => {
    setProgress(0)
    setIsUploading(true)
  }, [])

  const updateProgress = useCallback((percentage: number) => {
    setProgress(percentage)
  }, [])

  const completeUpload = useCallback(() => {
    setIsUploading(false)
    setProgress(0)
  }, [])

  return {
    progress,
    isUploading,
    startUpload,
    updateProgress,
    completeUpload,
  }
}
