import { useEffect, useState } from 'react'
import { TaskListItem } from './TaskListItem'
import { Checkbox } from '@/components/ui/checkbox'
import { Button } from '@/components/ui/button'
import { useDeleteTask, useProcessTask, useStartReview } from '@/hooks/useTasks'
import { useUIStore } from '@/stores/uiStore'
import {
  DEFAULT_PROCESSING_SETTINGS,
  loadProcessingSettings,
  toProcessTaskOptions,
  type ProcessingPanelSettings,
} from './processingConfigSettings'
import { ProcessingConfigModal } from './ProcessingConfigModal'
import type { Task } from '@/types/task'

interface TaskListProps {
  tasks: Task[]
  selectedTaskIds: Set<string>
  onToggleTask: (taskId: string, checked: boolean) => void
  onToggleAllVisible: () => void
  onBulkDelete: () => void
  onAddSource: () => void
  isBulkDeleting?: boolean
}

export function TaskList({
  tasks,
  selectedTaskIds,
  onToggleTask,
  onToggleAllVisible,
  onBulkDelete,
  onAddSource,
  isBulkDeleting = false,
}: TaskListProps) {
  const { openTimeline, openReviewModal } = useUIStore()
  const deleteTask = useDeleteTask()
  const processTask = useProcessTask()
  const startReview = useStartReview()
  const [isConfigOpen, setIsConfigOpen] = useState(false)
  const [processingSettings, setProcessingSettings] = useState<ProcessingPanelSettings>(
    DEFAULT_PROCESSING_SETTINGS
  )

  useEffect(() => {
    setProcessingSettings(loadProcessingSettings())
  }, [])

  const selectedVisibleCount = tasks.filter((task) => selectedTaskIds.has(task.id)).length
  const allVisibleSelected = tasks.length > 0 && selectedVisibleCount === tasks.length
  const hasAnySelected = selectedTaskIds.size > 0

  const handleDelete = (taskId: string) => {
    const task = tasks.find((candidate) => candidate.id === taskId)
    if (task && confirm(`确定要删除任务 "${task.displayName}" 吗？`)) {
      deleteTask.mutate(taskId)
    }
  }

  const handleViewResult = (taskId: string) => {
    openTimeline(taskId)
  }

  const handleProcess = (taskId: string) => {
    processTask.mutate({
      id: taskId,
      options: toProcessTaskOptions(processingSettings),
    })
  }

  const handleStartReview = (taskId: string) => {
    startReview.mutate(taskId)
  }

  const handleOpenReview = (taskId: string) => {
    openReviewModal(taskId)
  }

  return (
    <div className="flex h-full min-h-0 flex-col gap-2">
      <div className="sc-toolbar flex flex-col gap-2 rounded-lg px-3 py-2.5 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-2 text-sm text-[var(--sc-text-secondary)]">
          <Checkbox
            checked={allVisibleSelected}
            onChange={() => onToggleAllVisible()}
            aria-label="全选当前列表任务"
          />
          <span className="font-medium text-[var(--sc-text-primary)]">全选当前列表</span>
          <span className="text-[var(--sc-text-muted)]">已选择 {selectedTaskIds.size} 项</span>
        </div>
        <div className="flex items-center justify-end gap-2">
          <button
            type="button"
            onClick={onAddSource}
            className="sc-btn sc-btn-secondary h-8 gap-1 px-4"
          >
            <span className="text-base leading-none">+</span>
            添加来源
          </button>
          <button
            type="button"
            onClick={() => setIsConfigOpen(true)}
            className="sc-btn sc-btn-secondary h-8 px-4"
          >
            参数配置
          </button>
          <Button
            size="sm"
            variant="danger"
            onClick={onBulkDelete}
            disabled={!hasAnySelected}
            isLoading={isBulkDeleting}
            className="h-8 px-3 text-xs"
          >
            批量删除
          </Button>
        </div>
      </div>

      {tasks.length === 0 ? (
        <div className="rounded-lg border border-dashed border-[var(--sc-border-subtle)] bg-[var(--sc-bg-contrast)] px-4 py-6 text-sm text-[var(--sc-text-muted)]">
          当前暂无任务
        </div>
      ) : (
        <div className="sc-table-shell flex flex-1 min-h-0 flex-col overflow-hidden rounded-lg">
          <div className="sc-table-header grid grid-cols-[32px_2.8fr_1.2fr_0.6fr_0.9fr_1fr] items-center gap-x-3 px-3 py-2 text-sm font-semibold">
            <div />
            <div>任务名称</div>
            <div>状态 / 进度</div>
            <div>镜头数</div>
            <div>上传时间</div>
            <div>操作</div>
          </div>

          <div className="flex-1 min-h-0 overflow-y-auto">
            {tasks.map((task) => (
              <TaskListItem
                key={task.id}
                task={task}
                selected={selectedTaskIds.has(task.id)}
                onSelectChange={(checked) => onToggleTask(task.id, checked)}
                onViewResult={handleViewResult}
                onDelete={handleDelete}
                onProcess={handleProcess}
                onStartReview={handleStartReview}
                onOpenReview={handleOpenReview}
                isProcessing={processTask.isPending || startReview.isPending}
                isDeleting={deleteTask.isPending}
              />
            ))}
          </div>
        </div>
      )}

      <ProcessingConfigModal
        isOpen={isConfigOpen}
        initialSettings={processingSettings}
        onClose={() => setIsConfigOpen(false)}
        onSave={(nextSettings) => setProcessingSettings(nextSettings)}
      />
    </div>
  )
}
