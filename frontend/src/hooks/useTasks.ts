import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { taskService } from '@/services/taskService'
import type { ProcessTaskOptions, ReviewScene, Task } from '@/types/task'

const ACTIVE_TASK_STATUSES = new Set([
  'QUEUED',
  'PROCESSING',
  'DETECTING',
  'SPLITTING',
  'REVIEW_APPROVED',
])

/**
 * 获取任务列表 Hook
 *
 * 使用 React Query 管理服务端状态：
 * - 自动缓存 (5 秒 staleTime)
 * - 自动轮询 (5 秒 interval)
 * - 自动重新获取
 */
export function useTasks() {
  return useQuery<Task[]>({
    queryKey: ['tasks'],
    queryFn: taskService.getAll,
    // 仅在存在活跃任务时轮询，避免空转请求。
    refetchInterval: (query) => {
      const tasks = (query.state.data as Task[] | undefined) ?? []
      if (!tasks.length) {
        return false
      }
      const hasActiveTask = tasks.some((task) => ACTIVE_TASK_STATUSES.has(task.status))
      return hasActiveTask ? 5000 : false
    },
    staleTime: 5000, // 5 秒内数据视为新鲜
  })
}

/**
 * 获取任务详情 Hook
 */
export function useTask(id: string) {
  return useQuery({
    queryKey: ['tasks', id],
    queryFn: () => taskService.getById(id),
    enabled: !!id, // 只有 id 存在时才启用
  })
}

/**
 * 删除任务 Hook（带乐观更新）
 */
export function useDeleteTask() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: taskService.delete,

    // 乐观更新：立即从 UI 移除
    onMutate: async (taskId) => {
      // 取消正在进行的查询
      await queryClient.cancelQueries({ queryKey: ['tasks'] })

      // 保存当前数据
      const previousTasks = queryClient.getQueryData<Task[]>(['tasks'])

      // 乐观更新
      queryClient.setQueryData<Task[]>(['tasks'], (old) =>
        old?.filter((t) => t.id !== taskId) ?? []
      )

      // 返回上下文用于回滚
      return { previousTasks }
    },

    // 错误时回滚
    onError: (_err, _taskId, context) => {
      queryClient.setQueryData(['tasks'], context?.previousTasks)
    },

    // 完成后重新获取
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ['tasks'] })
    },
  })
}

/**
 * 开始处理任务 Hook
 */
export function useProcessTask() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (payload: { id: string; options?: ProcessTaskOptions } | string) => {
      if (typeof payload === 'string') {
        return taskService.process(payload)
      }
      return taskService.process(payload.id, payload.options)
    },

    onSuccess: () => {
      // 处理成功后刷新任务列表
      queryClient.invalidateQueries({ queryKey: ['tasks'] })
    },
  })
}

/**
 * 获取任务结果 Hook
 */
export function useTaskResult(id: string) {
  return useQuery({
    queryKey: ['tasks', id, 'result'],
    queryFn: () => taskService.getResult(id),
    enabled: !!id,
  })
}

/**
 * 开始检测并审核 Hook
 */
export function useStartReview() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => taskService.startReview(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tasks'] })
    },
  })
}

/**
 * 获取审核数据 Hook
 */
export function useReviewData(id: string, enabled: boolean) {
  return useQuery({
    queryKey: ['tasks', id, 'review-data'],
    queryFn: () => taskService.getReviewData(id),
    enabled: !!id && enabled,
  })
}

/**
 * 保存用户编辑场景 Hook
 */
export function useSaveReviewData() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, scenes }: { id: string; scenes: ReviewScene[] }) =>
      taskService.saveReviewData(id, scenes),
    onSuccess: (_data, { id }) => {
      queryClient.invalidateQueries({ queryKey: ['tasks', id, 'review-data'] })
    },
  })
}

/**
 * 确认并切分 Hook
 */
export function useApproveReview() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => taskService.approveReview(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tasks'] })
    },
  })
}
