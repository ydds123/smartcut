import { create } from 'zustand'

function createToastId(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID()
  }
  const perfPart = typeof performance !== 'undefined' ? Math.floor(performance.now() * 1000) : 0
  return `toast-${Date.now()}-${perfPart}`
}

/**
 * Toast 消息类型
 */
export type ToastType = 'success' | 'error' | 'info' | 'warning'

/**
 * Toast 消息实体
 */
export interface Toast {
  id: string
  type: ToastType
  message: string
  duration?: number
}

/**
 * UI State 接口
 */
interface UIState {
  // Modal 状态
  isTimelineOpen: boolean
  selectedTaskId: string | null
  isUploadModalOpen: boolean
  isReviewModalOpen: boolean
  reviewTaskId: string | null
  isStoryIntroModalOpen: boolean
  storyIntroTaskId: string | null

  // Toast 队列
  toasts: Toast[]

  // Actions
  openTimeline: (taskId: string) => void
  closeTimeline: () => void
  openUploadModal: () => void
  closeUploadModal: () => void
  openReviewModal: (taskId: string) => void
  closeReviewModal: () => void
  openStoryIntroModal: (taskId: string) => void
  closeStoryIntroModal: () => void
  addToast: (toast: Omit<Toast, 'id'>) => void
  removeToast: (id: string) => void
  clearToasts: () => void
}

/**
 * UI Store (Zustand)
 *
 * 用于管理客户端状态：
 * - Modal 开关状态
 * - Toast 通知队列
 * - 其他纯 UI 交互状态
 */
export const useUIStore = create<UIState>((set, get) => ({
  // Initial state
  isTimelineOpen: false,
  selectedTaskId: null,
  isUploadModalOpen: false,
  isReviewModalOpen: false,
  reviewTaskId: null,
  isStoryIntroModalOpen: false,
  storyIntroTaskId: null,
  toasts: [],

  // Actions
  openTimeline: (taskId: string) =>
    set({
      isTimelineOpen: true,
      selectedTaskId: taskId,
    }),

  closeTimeline: () =>
    set({
      isTimelineOpen: false,
      selectedTaskId: null,
    }),

  openUploadModal: () =>
    set({
      isUploadModalOpen: true,
    }),

  closeUploadModal: () =>
    set({
      isUploadModalOpen: false,
    }),

  openReviewModal: (taskId: string) =>
    set({
      isReviewModalOpen: true,
      reviewTaskId: taskId,
    }),

  closeReviewModal: () =>
    set({
      isReviewModalOpen: false,
      reviewTaskId: null,
    }),

  openStoryIntroModal: (taskId: string) =>
    set({
      isStoryIntroModalOpen: true,
      storyIntroTaskId: taskId,
    }),

  closeStoryIntroModal: () =>
    set({
      isStoryIntroModalOpen: false,
      storyIntroTaskId: null,
    }),

  addToast: (toast) => {
    const id = createToastId()
    const newToast: Toast = {
      id,
      type: toast.type || 'info',
      message: toast.message,
      duration: toast.duration || 3000,
    }

    set((state) => ({
      toasts: [...state.toasts, newToast],
    }))

    // 自动移除 Toast
    if (newToast.duration && newToast.duration > 0) {
      setTimeout(() => {
        get().removeToast(id)
      }, newToast.duration)
    }
  },

  removeToast: (id) =>
    set((state) => ({
      toasts: state.toasts.filter((t) => t.id !== id),
    })),

  clearToasts: () => set({ toasts: [] }),
}))
