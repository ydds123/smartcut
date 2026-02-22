import { useCallback, useEffect, useRef, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { useUIStore } from '@/stores/uiStore'
import { uploadService } from '@/services/uploadService'
import { useUploadProgress } from '@/hooks/useTaskProgress'
import { playSound } from '@/utils/soundPlayer'
import { Button } from '@/components/ui/button'
import { useDraggableModal } from '@/hooks/useDraggableModal'

export function UploadModal() {
  const queryClient = useQueryClient()
  const fileInputRef = useRef<HTMLInputElement | null>(null)
  const [isDragging, setIsDragging] = useState(false)
  const { isUploadModalOpen, closeUploadModal, addToast } = useUIStore()

  const { progress, isUploading, startUpload, updateProgress, completeUpload } =
    useUploadProgress()
  const { modalRef, modalStyle, onHandlePointerDown, dragging } = useDraggableModal({
    isOpen: isUploadModalOpen,
  })

  useEffect(() => {
    if (!isUploadModalOpen) {
      return
    }

    const handleEsc = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && !isUploading) {
        closeUploadModal()
      }
    }

    window.addEventListener('keydown', handleEsc)
    return () => window.removeEventListener('keydown', handleEsc)
  }, [closeUploadModal, isUploadModalOpen, isUploading])

  const handleFiles = useCallback(
    async (files: FileList | File[]) => {
      const file = Array.from(files)[0]
      if (!file) {
        return
      }

      if (!uploadService.validateFileType(file)) {
        addToast({
          type: 'error',
          message: '不支持的文件格式，请上传 MP4/MOV/AVI/MKV 视频',
        })
        playSound('error')
        return
      }

      if (!uploadService.validateFileSize(file, 500)) {
        addToast({
          type: 'error',
          message: '文件大小超过 500MB 限制',
        })
        playSound('error')
        return
      }

      startUpload()

      try {
        await uploadService.upload(
          {
            displayName: file.name,
            file,
          },
          ({ percentage }) => updateProgress(percentage)
        )

        addToast({
          type: 'success',
          message: `上传成功: ${file.name}`,
        })
        playSound('success')
        await queryClient.invalidateQueries({ queryKey: ['tasks'] })
        closeUploadModal()
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
    [addToast, closeUploadModal, completeUpload, queryClient, startUpload, updateProgress]
  )

  const openFilePicker = useCallback(() => {
    if (!isUploading) {
      fileInputRef.current?.click()
    }
  }, [isUploading])

  const handleDrop = useCallback(
    (event: React.DragEvent<HTMLDivElement>) => {
      event.preventDefault()
      setIsDragging(false)
      handleFiles(event.dataTransfer.files)
    },
    [handleFiles]
  )

  const handleDragOver = useCallback((event: React.DragEvent<HTMLDivElement>) => {
    event.preventDefault()
    setIsDragging(true)
  }, [])

  const handleDragLeave = useCallback((event: React.DragEvent<HTMLDivElement>) => {
    event.preventDefault()
    setIsDragging(false)
  }, [])

  const handleFileInput = useCallback(
    (event: React.ChangeEvent<HTMLInputElement>) => {
      if (event.target.files) {
        handleFiles(event.target.files)
      }
      event.target.value = ''
    },
    [handleFiles]
  )

  if (!isUploadModalOpen) {
    return null
  }

  return (
    <div className="fixed inset-0 z-[70] flex items-center justify-center p-4 sm:p-6">
      <div
        className="absolute inset-0 bg-black/40"
        onClick={() => {
          if (!isUploading) {
            closeUploadModal()
          }
        }}
      />

      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="upload-modal-title"
        ref={modalRef}
        style={modalStyle}
        className="relative w-full max-w-3xl rounded-3xl border border-gray-200 bg-white p-6 shadow-2xl sm:p-8"
      >
        <div
          className={`flex items-start justify-between gap-4 ${dragging ? 'cursor-grabbing' : 'cursor-move'}`}
          onPointerDown={onHandlePointerDown}
        >
          <h2 id="upload-modal-title" className="text-3xl font-semibold text-gray-600">
            添加来源
          </h2>
          <button
            type="button"
            onClick={() => closeUploadModal()}
            data-drag-ignore="true"
            className="inline-flex h-9 w-9 items-center justify-center rounded-full text-gray-400 transition-colors hover:bg-info-bg"
            aria-label="关闭上传窗口"
            disabled={isUploading}
          >
            <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 6l12 12M18 6l-12 12" />
            </svg>
          </button>
        </div>

        <div
          role="button"
          tabIndex={isUploading ? -1 : 0}
          onClick={openFilePicker}
          onKeyDown={(event) => {
            if (!isUploading && (event.key === 'Enter' || event.key === ' ')) {
              event.preventDefault()
              openFilePicker()
            }
          }}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          className={`mt-6 rounded-2xl border-2 border-dashed p-10 text-center transition-colors sm:p-12 ${
            isDragging ? 'border-primary bg-info-bg' : 'border-gray-200 bg-white/90'
          } ${isUploading ? 'pointer-events-none opacity-70' : 'cursor-pointer'}`}
        >
          <input
            ref={fileInputRef}
            type="file"
            accept="video/mp4,video/quicktime,video/x-msvideo,video/x-matroska"
            onChange={handleFileInput}
            className="hidden"
            disabled={isUploading}
          />

          <p className="text-4xl font-medium text-gray-600">
            {isDragging ? '释放文件以上传' : '点击或拖放文件上传'}
          </p>
          <p className="mt-3 text-sm text-gray-400">支持 MP4/MOV/AVI/MKV，最大 500MB</p>

          <div className="mt-8 flex justify-center">
            <Button
              size="sm"
              variant="secondary"
              className="rounded-full px-5"
              disabled={isUploading}
              onClick={(event) => {
                event.stopPropagation()
                openFilePicker()
              }}
            >
              上传视频文件
            </Button>
          </div>

          {isUploading && (
            <div className="mx-auto mt-6 max-w-md rounded-xl border border-gray-200 bg-gray-50 p-4">
              <div className="mb-2 flex items-center justify-between text-sm text-gray-500">
                <span>上传中...</span>
                <span className="font-semibold text-primary">{progress}%</span>
              </div>
              <div className="h-2 overflow-hidden rounded-full bg-gray-100">
                <div
                  className="h-full rounded-full bg-primary transition-all duration-300"
                  style={{ width: `${progress}%` }}
                />
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
