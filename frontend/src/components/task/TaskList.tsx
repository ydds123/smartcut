import { useEffect, useState } from 'react'
import { TaskListItem } from './TaskListItem'
import { Checkbox } from '@/components/ui/checkbox'
import { Button } from '@/components/ui/button'
import { useDeleteTask, useStartReview } from '@/hooks/useTasks'
import {
  useAnalysisSettings,
  useOpenAnalysisEnvFile,
  useTaskAnalysisBatch,
  useTestAnalysisSettings,
  useUpdateAnalysisSettings,
} from '@/hooks/useAnalysis'
import { useUIStore } from '@/stores/uiStore'
import { taskService } from '@/services/taskService'
import {
  DEFAULT_PROCESSING_SETTINGS,
  loadProcessingSettings,
  type ProcessingPanelSettings,
} from './processingConfigSettings'
import { ProcessingConfigModal } from './ProcessingConfigModal'
import { AnalysisSettingsModal } from './AnalysisSettingsModal'
import type { ProcessingConfigMeta, Task } from '@/types/task'
import type { AnalysisSettingsUpdatePayload } from '@/types/analysis'

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
  const { openReviewModal, openStoryIntroModal, addToast } = useUIStore()
  const deleteTask = useDeleteTask()
  const startReview = useStartReview()
  const updateAnalysisSettings = useUpdateAnalysisSettings()
  const testAnalysisSettings = useTestAnalysisSettings()
  const openAnalysisEnvFile = useOpenAnalysisEnvFile()
  const [isConfigOpen, setIsConfigOpen] = useState(false)
  const [isAnalysisConfigOpen, setIsAnalysisConfigOpen] = useState(false)
  const [pendingActionTaskId, setPendingActionTaskId] = useState<string | null>(null)
  const [pendingDeleteTaskId, setPendingDeleteTaskId] = useState<string | null>(null)
  const [processingSettings, setProcessingSettings] = useState<ProcessingPanelSettings>(
    DEFAULT_PROCESSING_SETTINGS
  )
  const [processingConfigMeta, setProcessingConfigMeta] = useState<ProcessingConfigMeta | null>(null)
  const analysisSettingsQuery = useAnalysisSettings(isAnalysisConfigOpen)

  useEffect(() => {
    let disposed = false
    const loadMeta = async () => {
      try {
        const meta = await taskService.getProcessingConfigMeta()
        if (disposed) return
        setProcessingConfigMeta(meta)
        setProcessingSettings(loadProcessingSettings(meta))
      } catch {
        if (disposed) return
        setProcessingConfigMeta(null)
        setProcessingSettings(loadProcessingSettings())
      }
    }
    void loadMeta()
    return () => {
      disposed = true
    }
  }, [])

  const analysisBatchQuery = useTaskAnalysisBatch(
    tasks.map((task) => task.id),
    tasks.length > 0
  )
  const analysisByTaskId = new Map(
    (analysisBatchQuery.data?.items || []).map((item) => [item.taskId, item])
  )

  const selectedVisibleCount = tasks.filter((task) => selectedTaskIds.has(task.id)).length
  const allVisibleSelected = tasks.length > 0 && selectedVisibleCount === tasks.length
  const hasAnySelected = selectedTaskIds.size > 0

  const handleDelete = (taskId: string) => {
    const task = tasks.find((candidate) => candidate.id === taskId)
    if (task && confirm(`确定要删除任务 "${task.displayName}" 吗？`)) {
      setPendingDeleteTaskId(taskId)
      deleteTask.mutate(taskId, {
        onSettled: () => {
          setPendingDeleteTaskId((current) => (current === taskId ? null : current))
        },
      })
    }
  }

  const handleStartReview = (taskId: string) => {
    setPendingActionTaskId(taskId)
    startReview.mutate(taskId, {
      onSettled: () => {
        setPendingActionTaskId((current) => (current === taskId ? null : current))
      },
    })
  }

  const handleOpenReview = (taskId: string) => {
    openReviewModal(taskId)
  }

  const handleOpenStoryIntro = (taskId: string) => {
    openStoryIntroModal(taskId)
  }

  const handleSaveAnalysisSettings = async (payload: AnalysisSettingsUpdatePayload) => {
    try {
      await updateAnalysisSettings.mutateAsync(payload)
      addToast({
        type: 'success',
        message: '分析设置已保存',
      })
      setIsAnalysisConfigOpen(false)
    } catch {
      addToast({
        type: 'error',
        message: '保存分析设置失败，请稍后重试',
      })
    }
  }

  const handleTestAnalysisSettings = async (payload: AnalysisSettingsUpdatePayload): Promise<string> => {
    try {
      const result = await testAnalysisSettings.mutateAsync(payload)
      const suffix = result.latencyMs ? `（${result.latencyMs}ms）` : ''
      const message = result.message || '连接测试通过'
      addToast({
        type: 'success',
        message: `连接测试通过${suffix}`,
      })
      return `${message}${suffix}`
    } catch (error: any) {
      const detail = error?.response?.data?.detail || '连接测试失败'
      addToast({
        type: 'error',
        message: typeof detail === 'string' ? detail : '连接测试失败',
      })
      return typeof detail === 'string' ? detail : '连接测试失败'
    }
  }

  const handleOpenAnalysisEnvFile = async (): Promise<string> => {
    try {
      const result = await openAnalysisEnvFile.mutateAsync()
      const message = result.message || '已打开配置文件'
      addToast({
        type: 'success',
        message,
      })
      return message
    } catch (error: any) {
      const detail = error?.response?.data?.detail || '打开配置文件失败'
      addToast({
        type: 'error',
        message: typeof detail === 'string' ? detail : '打开配置文件失败',
      })
      return typeof detail === 'string' ? detail : '打开配置文件失败'
    }
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
          <Button
            type="button"
            size="sm"
            variant="secondary"
            onClick={onAddSource}
            className="h-8 gap-1 px-4"
          >
            <span className="text-base leading-none">+</span>
            添加来源
          </Button>
          <Button
            type="button"
            size="sm"
            variant="secondary"
            onClick={() => setIsConfigOpen(true)}
            className="h-8 px-4"
          >
            参数配置
          </Button>
          <Button
            type="button"
            size="sm"
            variant="secondary"
            onClick={() => setIsAnalysisConfigOpen(true)}
            className="h-8 px-4"
          >
            分析设置
          </Button>
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
          <div className="sc-table-header grid grid-cols-[32px_minmax(0,2.4fr)_minmax(0,1.25fr)_minmax(0,0.95fr)_80px_64px_minmax(0,0.95fr)_minmax(0,1.8fr)] items-center gap-x-2.5 px-3 py-2 text-sm font-semibold">
            <div />
            <div className="px-1.5">任务名称</div>
            <div className="px-1.5">状态 / 进度</div>
            <div className="px-1.5">故事介绍</div>
            <div className="px-1.5">视频时长</div>
            <div className="px-1.5">镜头数</div>
            <div className="px-1.5">上传时间</div>
            <div className="px-1.5">操作</div>
          </div>

          <div className="flex-1 min-h-0 overflow-y-auto">
            {tasks.map((task) => (
              <TaskListItem
                key={task.id}
                task={task}
                analysisStatus={analysisByTaskId.get(task.id)}
                analysisStatusReady={analysisBatchQuery.isSuccess}
                selected={selectedTaskIds.has(task.id)}
                onSelectChange={(checked) => onToggleTask(task.id, checked)}
                onDelete={handleDelete}
                onStartReview={handleStartReview}
                onOpenReview={handleOpenReview}
                onOpenStoryIntro={handleOpenStoryIntro}
                isProcessing={pendingActionTaskId === task.id}
                isDeleting={pendingDeleteTaskId === task.id}
              />
            ))}
          </div>
        </div>
      )}

      <ProcessingConfigModal
        isOpen={isConfigOpen}
        initialSettings={processingSettings}
        configMeta={processingConfigMeta}
        onClose={() => setIsConfigOpen(false)}
        onSave={(nextSettings) => setProcessingSettings(nextSettings)}
      />

      <AnalysisSettingsModal
        isOpen={isAnalysisConfigOpen}
        isLoading={analysisSettingsQuery.isLoading}
        isSaving={updateAnalysisSettings.isPending}
        isTesting={testAnalysisSettings.isPending}
        isOpeningEnvFile={openAnalysisEnvFile.isPending}
        settings={analysisSettingsQuery.data}
        onClose={() => setIsAnalysisConfigOpen(false)}
        onSave={handleSaveAnalysisSettings}
        onTest={handleTestAnalysisSettings}
        onOpenEnvFile={handleOpenAnalysisEnvFile}
      />
    </div>
  )
}
