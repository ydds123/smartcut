import { useCallback } from 'react'
import { useRetryTaskAnalysis, useTaskAnalysis } from '@/hooks/useAnalysis'
import { useUIStore } from '@/stores/uiStore'
import { StoryIntroModal } from './StoryIntroModal'

export function StoryIntroModalHost() {
  const {
    isStoryIntroModalOpen,
    storyIntroTaskId,
    closeStoryIntroModal,
    addToast,
  } = useUIStore()
  const taskAnalysis = useTaskAnalysis(
    storyIntroTaskId ?? '',
    isStoryIntroModalOpen && Boolean(storyIntroTaskId)
  )
  const retryTaskAnalysis = useRetryTaskAnalysis()

  const handleRetryAnalysis = useCallback(async () => {
    if (!storyIntroTaskId) {
      return
    }

    try {
      const result = await retryTaskAnalysis.mutateAsync(storyIntroTaskId)
      if (result.status === 'FAILED') {
        addToast({
          type: 'error',
          message: result.message || '重试请求未通过，请检查分析配置',
        })
        return
      }
      if (result.deduplicated) {
        addToast({
          type: 'info',
          message: result.message || '已有分析任务在处理中',
        })
        return
      }
      addToast({
        type: 'success',
        message: '已提交重试请求',
      })
    } catch (error: any) {
      const detail = error?.response?.data?.detail
      addToast({
        type: 'error',
        message: typeof detail === 'string' ? detail : '重试失败，请稍后重试',
      })
    }
  }, [addToast, retryTaskAnalysis, storyIntroTaskId])

  return (
    <StoryIntroModal
      isOpen={isStoryIntroModalOpen}
      isLoading={taskAnalysis.isLoading}
      data={taskAnalysis.data}
      isRetrying={retryTaskAnalysis.isPending}
      onClose={closeStoryIntroModal}
      onRetry={handleRetryAnalysis}
    />
  )
}
