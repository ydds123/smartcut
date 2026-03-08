import { memo } from 'react'
import { Card, CardContent, CardHeader } from '@/components/ui/card'
import { StatusBadge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Progress } from '@/components/ui/progress'
import { Checkbox } from '@/components/ui/checkbox'
import { useDeleteTask, useProcessTask, useStartReview } from '@/hooks/useTasks'
import { useUIStore } from '@/stores/uiStore'
import { useTaskProgress } from '@/hooks/useTaskProgress'
import type { Task } from '@/types/task'
import { uploadService } from '@/services/uploadService'

interface TaskCardProps {
  task: Task
  selected: boolean
  onSelectChange: (checked: boolean) => void
}

export const TaskCard = memo(function TaskCard({
  task,
  selected,
  onSelectChange,
}: TaskCardProps) {
  const { openTimeline, openReviewModal } = useUIStore()
  const deleteTask = useDeleteTask()
  const processTask = useProcessTask()
  const startReview = useStartReview()
  const { progress, status, totalScenes } = useTaskProgress(task.id, task.status, task.progress)
  const liveStatus = status || task.status

  const displayProgress = Math.max(0, Math.min(100, progress ?? task.progress ?? 0))
  const shotsCount = totalScenes ?? task.shotsCount ?? task.totalScenes
  const isProcessing = ['PROCESSING', 'QUEUED', 'DETECTING', 'REVIEW_APPROVED', 'SPLITTING', 'ANALYZE_QUEUED', 'ANALYZING'].includes(liveStatus)

  const handleDelete = () => {
    if (confirm(`确定要删除任务 "${task.displayName}" 吗？`)) {
      deleteTask.mutate(task.id)
    }
  }

  const handleProcess = () => {
    processTask.mutate(task.id)
  }

  const handleStartReview = () => {
    startReview.mutate(task.id)
  }

  const handleOpenReview = () => {
    openReviewModal(task.id)
  }

  const handleViewResult = () => {
    openTimeline(task.id)
  }

  const isBusy = processTask.isPending || deleteTask.isPending || startReview.isPending

  return (
    <Card variant="bordered" className="transition-shadow hover:shadow-md">
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <div className="flex min-w-0 flex-1 items-start gap-3">
          <Checkbox
            checked={selected}
            onChange={(event) => onSelectChange(event.target.checked)}
            aria-label={`选择任务 ${task.displayName}`}
            className="mt-1"
          />
          <div className="min-w-0 flex-1">
            <h3 className="truncate text-base font-semibold text-[var(--sc-text-primary)]" title={task.displayName}>
              {task.displayName}
            </h3>
            <p className="text-xs text-[var(--sc-text-muted)]">{uploadService.formatFileSize(task.fileSize)}</p>
          </div>
        </div>
        <StatusBadge status={liveStatus} />
      </CardHeader>

      <CardContent>
        <div className="space-y-3">
          {isProcessing && <Progress value={displayProgress} showLabel />}

          <div className="text-sm text-[var(--sc-text-secondary)]">
            镜头数 <span className="font-medium">{shotsCount ?? '--'}</span>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            {liveStatus === 'PENDING' && (
              <>
                <Button size="sm" onClick={handleProcess} isLoading={processTask.isPending}>
                  直接处理
                </Button>
                <Button size="sm" variant="secondary" onClick={handleStartReview} isLoading={startReview.isPending}>
                  检测并审核
                </Button>
              </>
            )}

            {liveStatus === 'REVIEW_PENDING' && (
              <Button size="sm" onClick={handleOpenReview} disabled={isBusy}>
                查看并编辑
              </Button>
            )}

            {liveStatus === 'TIMELINE_READY' && (
              <Button size="sm" variant="secondary" onClick={handleViewResult} disabled={isBusy}>
                查看工作台
              </Button>
            )}

            {(liveStatus === 'COMPLETED' || liveStatus === 'FAILED' || liveStatus === 'ANALYZE_FAILED') && (
              <Button size="sm" variant="secondary" onClick={handleViewResult} disabled={isBusy}>
                查看详情
              </Button>
            )}

            {(['PENDING', 'QUEUED', 'PROCESSING', 'FAILED', 'REVIEW_PENDING', 'REVIEW_APPROVED', 'SPLITTING', 'ANALYZE_QUEUED', 'ANALYZING', 'ANALYZE_FAILED'] as const).includes(liveStatus as any) && (
              <Button
                size="sm"
                variant="danger"
                onClick={handleDelete}
                isLoading={deleteTask.isPending}
              >
                删除
              </Button>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  )
})
