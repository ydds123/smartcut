import { useCallback, useState } from 'react'
import { uploadService } from '@/services/uploadService'
import { useUIStore } from '@/stores/uiStore'
import { useUploadProgress } from '@/hooks/useTaskProgress'
import { playSound } from '@/utils/soundPlayer'

export function UploadArea() {
  const [isDragging, setIsDragging] = useState(false)
  const { addToast } = useUIStore()
  const { progress, isUploading, startUpload, updateProgress, completeUpload } =
    useUploadProgress()

  // 处理文件选择
  const handleFiles = useCallback(
    async (files: FileList | File[]) => {
      const file = Array.from(files)[0]

      if (!file) return

      // 校验文件类型
      if (!uploadService.validateFileType(file)) {
        addToast({
          type: 'error',
          message: '不支持的文件格式，请上传 MP4/MOV/AVI/MKV 视频',
        })
        playSound('error')
        return
      }

      // 校验文件大小
      if (!uploadService.validateFileSize(file, 500)) {
        addToast({
          type: 'error',
          message: '文件大小超过 500MB 限制',
        })
        playSound('error')
        return
      }

      // 开始上传
      startUpload()

      try {
        await uploadService.upload(
          {
            displayName: file.name,
            file,
          },
          ({ percentage }) => {
            updateProgress(percentage)
          }
        )

        addToast({
          type: 'success',
          message: `上传成功: ${file.name}`,
        })
        playSound('success')
      } catch {
        addToast({
          type: 'error',
          message: '上传失败，请重试',
        })
        playSound('error')
      } finally {
        completeUpload()
      }
    },
    [addToast, startUpload, updateProgress, completeUpload]
  )

  // 拖拽事件处理
  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(true)
  }, [])

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(false)
  }, [])

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault()
      setIsDragging(false)

      const files = e.dataTransfer.files
      handleFiles(files)
    },
    [handleFiles]
  )

  // 点击上传
  const handleFileInput = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const files = e.target.files
      if (files) {
        handleFiles(files)
      }
    },
    [handleFiles]
  )

  return (
    <div className="space-y-4">
      {/* 拖拽上传区域 */}
      <div
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        className={`
          relative border-2 border-dashed rounded-lg p-12 text-center transition-colors
          ${
            isDragging
              ? 'border-[var(--sc-accent)] bg-[var(--sc-accent-soft)]'
              : 'border-[var(--sc-border-strong)] hover:border-[var(--sc-border-subtle)]'
          }
          ${isUploading ? 'pointer-events-none opacity-50' : 'cursor-pointer'}
        `}
      >
        <input
          type="file"
          accept="video/mp4,video/quicktime,video/x-msvideo,video/x-matroska"
          onChange={handleFileInput}
          className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
          disabled={isUploading}
        />

        <div className="space-y-4">
          {/* 图标 */}
          <div className="mx-auto w-16 h-16 text-[var(--sc-text-muted)]">
            <svg
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
              xmlns="http://www.w3.org/2000/svg"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
              />
            </svg>
          </div>

          {/* 文本 */}
          <div>
            <p className="text-lg font-medium text-[var(--sc-text-primary)]">
              {isDragging ? '释放文件以上传' : '拖拽视频文件到此处'}
            </p>
            <p className="mt-1 text-sm text-[var(--sc-text-muted)]">
              或点击选择文件 • 支持 MP4/MOV/AVI/MKV • 最大 500MB
            </p>
          </div>
        </div>
      </div>

      {/* 上传进度 */}
      {isUploading && (
        <div className="rounded-lg border border-[var(--sc-border-subtle)] bg-[var(--sc-bg-surface)] p-4">
          <div className="flex justify-between text-sm mb-2">
            <span className="text-[var(--sc-text-secondary)]">上传中...</span>
            <span className="font-medium">{progress}%</span>
          </div>
          <div className="h-2 w-full overflow-hidden rounded-full bg-[var(--sc-bg-elevated)]">
            <div
              className="h-2 rounded-full bg-[var(--sc-accent)] transition-all duration-300"
              style={{ width: `${progress}%` }}
            />
          </div>
        </div>
      )}
    </div>
  )
}
