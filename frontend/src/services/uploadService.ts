import apiClient from './api'
import type { CreateTaskDTO, Task, UploadProgress } from '@/types/task'

/**
 * 上传服务
 */
export const uploadService = {
  /**
   * 上传视频文件
   */
  upload: async (
    data: CreateTaskDTO,
    onProgress?: (progress: UploadProgress) => void
  ): Promise<Task> => {
    const formData = new FormData()
    formData.append('file', data.file)
    formData.append('displayName', data.displayName)

    const response = await apiClient.post<Task>('/api/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
      onUploadProgress: (progressEvent) => {
        if (onProgress && progressEvent.total) {
          const percentage = Math.round(
            (progressEvent.loaded * 100) / progressEvent.total
          )
          onProgress({
            loaded: progressEvent.loaded,
            total: progressEvent.total,
            percentage,
          })
        }
      },
    })

    return response.data
  },

  /**
   * 校验文件类型
   */
  validateFileType: (file: File): boolean => {
    const validTypes = [
      'video/mp4',
      'video/quicktime', // .mov
      'video/x-msvideo', // .avi
      'video/x-matroska', // .mkv
    ]
    return validTypes.includes(file.type)
  },

  /**
   * 校验文件大小
   */
  validateFileSize: (file: File, maxSizeMB: number = 500): boolean => {
    const maxSizeBytes = maxSizeMB * 1024 * 1024
    return file.size <= maxSizeBytes
  },

  /**
   * 格式化文件大小
   */
  formatFileSize: (bytes: number): string => {
    if (bytes === 0) return '0 B'
    const k = 1024
    const sizes = ['B', 'KB', 'MB', 'GB']
    const i = Math.floor(Math.log(bytes) / Math.log(k))
    return `${parseFloat((bytes / Math.pow(k, i)).toFixed(2))} ${sizes[i]}`
  },
}
