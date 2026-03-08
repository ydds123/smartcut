import { useEffect, useMemo, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { useTasks } from './hooks/useTasks'
import { UploadModal } from './components/upload/UploadModal'
import { TaskList } from './components/task/TaskList'
import { ReviewModal } from './components/review/ReviewModal'
import { ToastContainer } from './components/ui/toast'
import { taskService } from './services/taskService'
import { useUIStore } from './stores/uiStore'

function App() {
  const { data: tasks, isLoading, error } = useTasks()
  const [selectedTaskIds, setSelectedTaskIds] = useState<Set<string>>(new Set())
  const [isBulkDeleting, setIsBulkDeleting] = useState(false)
  const queryClient = useQueryClient()
  const { addToast, openUploadModal } = useUIStore()

  const safeTasks = useMemo(() => tasks ?? [], [tasks])

  useEffect(() => {
    const visibleTaskIds = new Set(safeTasks.map((task) => task.id))
    setSelectedTaskIds((previous) => {
      const next = new Set([...previous].filter((taskId) => visibleTaskIds.has(taskId)))
      return next
    })
  }, [safeTasks])

  const handleToggleTask = (taskId: string, checked: boolean) => {
    setSelectedTaskIds((previous) => {
      const next = new Set(previous)
      if (checked) {
        next.add(taskId)
      } else {
        next.delete(taskId)
      }
      return next
    })
  }

  const handleToggleAllVisible = () => {
    const visibleIds = safeTasks.map((task) => task.id)

    setSelectedTaskIds((previous) => {
      const next = new Set(previous)
      const isAllVisibleSelected =
        visibleIds.length > 0 && visibleIds.every((taskId) => next.has(taskId))

      if (isAllVisibleSelected) {
        visibleIds.forEach((taskId) => next.delete(taskId))
      } else {
        visibleIds.forEach((taskId) => next.add(taskId))
      }

      return next
    })
  }

  const handleBulkDelete = async () => {
    const targetTaskIds = [...selectedTaskIds]
    if (targetTaskIds.length === 0) {
      return
    }

    const confirmed = confirm(
      `确定删除已选择的 ${targetTaskIds.length} 个任务吗？此操作会同步删除本地切分文件。`
    )
    if (!confirmed) {
      return
    }

    setIsBulkDeleting(true)

    try {
      const settledResults = await Promise.allSettled(
        targetTaskIds.map((taskId) => taskService.delete(taskId))
      )

      const failedTaskIds: string[] = []
      settledResults.forEach((result, index) => {
        if (result.status === 'rejected') {
          failedTaskIds.push(targetTaskIds[index])
        }
      })

      const successCount = targetTaskIds.length - failedTaskIds.length
      if (successCount > 0) {
        addToast({
          type: 'success',
          message: `已删除 ${successCount} 个任务`,
        })
      }
      if (failedTaskIds.length > 0) {
        addToast({
          type: 'warning',
          message: `${failedTaskIds.length} 个任务删除失败，可重试`,
        })
      }

      setSelectedTaskIds(new Set(failedTaskIds))
      await queryClient.invalidateQueries({ queryKey: ['tasks'] })
    } catch (bulkDeleteError) {
      addToast({
        type: 'error',
        message: '批量删除失败，请稍后重试',
      })
      console.error('Bulk delete failed:', bulkDeleteError)
    } finally {
      setIsBulkDeleting(false)
    }
  }

  if (error) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[var(--sc-bg-app)]">
        <div className="text-center">
          <h1 className="mb-2 text-2xl font-bold text-[var(--sc-danger)]">加载失败</h1>
          <p className="text-[var(--sc-text-muted)]">{error.message}</p>
        </div>
      </div>
    )
  }

  return (
    <div className="flex h-screen flex-col overflow-hidden bg-[var(--sc-bg-app)] text-[var(--sc-text-primary)]">
      <header className="border-b border-[var(--sc-border-subtle)] bg-[var(--sc-bg-panel)]">
        <div className="mx-auto flex w-full max-w-[1820px] items-center justify-between px-3 py-3 sm:px-4 lg:px-6">
          <div>
            <h1 className="text-[26px] font-semibold leading-8 text-[var(--sc-text-primary)]">SmartCut</h1>
            <p className="text-sm text-[var(--sc-text-muted)]">智能视频切分工具</p>
          </div>
          <div className="text-sm text-[var(--sc-text-muted)]">
            当前任务：<span className="font-semibold text-[var(--sc-text-primary)]">{safeTasks.length}</span>
          </div>
        </div>
      </header>

      <main className="mx-auto w-full max-w-[1820px] flex-1 overflow-hidden px-3 py-3 sm:px-4 lg:px-6 lg:py-4">
        <section className="sc-panel flex h-full min-h-0 flex-col rounded-lg p-3 shadow-sm sm:p-4">
          {isLoading ? (
            <div className="py-10 text-center text-[var(--sc-text-muted)]">加载中...</div>
          ) : (
            <div className="flex-1 min-h-0">
              <TaskList
                tasks={safeTasks}
                selectedTaskIds={selectedTaskIds}
                onToggleTask={handleToggleTask}
                onToggleAllVisible={handleToggleAllVisible}
                onBulkDelete={handleBulkDelete}
                onAddSource={openUploadModal}
                isBulkDeleting={isBulkDeleting}
              />
            </div>
          )}
        </section>
      </main>

      <UploadModal />
      {/* TimelineModal 已按需求暂时停用（时间轴工作台功能下线） */}
      <ReviewModal />
      <ToastContainer />
    </div>
  )
}

export default App
