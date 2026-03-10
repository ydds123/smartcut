import { useEffect } from 'react'
import { useUIStore, type ToastType } from '@/stores/uiStore'

/**
 * Toast 类型配置
 */
const toastConfig: Record<
  ToastType,
  { bgColor: string; iconColor: string; icon: string }
> = {
  success: {
    bgColor: 'bg-[var(--sc-bg-surface)] border-[var(--sc-border-subtle)]',
    iconColor: 'text-success',
    icon: '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />',
  },
  error: {
    bgColor: 'bg-[var(--sc-bg-surface)] border-[var(--sc-border-subtle)]',
    iconColor: 'text-danger',
    icon: '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />',
  },
  warning: {
    bgColor: 'bg-[var(--sc-bg-surface)] border-[var(--sc-border-subtle)]',
    iconColor: 'text-warning',
    icon: '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />',
  },
  info: {
    bgColor: 'bg-[var(--sc-bg-surface)] border-[var(--sc-border-subtle)]',
    iconColor: 'text-info',
    icon: '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />',
  },
}

/**
 * 单个 Toast 组件
 */
interface ToastItemProps {
  id: string
  type: ToastType
  message: string
  onRemove: (id: string) => void
}

function ToastItem({ id, type, message, onRemove }: ToastItemProps) {
  const config = toastConfig[type]

  useEffect(() => {
    // 进入动画
  }, [])

  const handleClose = () => {
    onRemove(id)
  }

  return (
    <div
      className={`${config.bgColor} border rounded-lg shadow-lg p-4 flex items-start gap-3 min-w-[300px] max-w-md animate-in slide-in-from-right fade-in duration-300`}
    >
      {/* 图标 */}
      <div className={`${config.iconColor} flex-shrink-0 mt-0.5`}>
        <svg
          className="w-5 h-5"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
          dangerouslySetInnerHTML={{ __html: config.icon }}
        />
      </div>

      {/* 消息内容 */}
      <div className="flex-1 min-w-0">
        <p className="text-sm break-words text-[var(--sc-text-primary)]">{message}</p>
      </div>

      {/* 关闭按钮 */}
      <button
        onClick={handleClose}
        className="flex-shrink-0 text-[var(--sc-text-muted)] transition-colors hover:text-[var(--sc-text-secondary)]"
      >
        <svg
          className="w-4 h-4"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M6 18L18 6M6 6l12 12"
          />
        </svg>
      </button>
    </div>
  )
}

/**
 * Toast 容器组件
 *
 * 渲染所有 Toast 通知，固定在屏幕右上角
 */
export function ToastContainer() {
  const { toasts, removeToast } = useUIStore()

  if (toasts.length === 0) {
    return null
  }

  return (
    <div className="fixed top-4 right-4 z-[9999] flex flex-col gap-2 pointer-events-none">
      {toasts.map((toast) => (
        <div key={toast.id} className="pointer-events-auto">
          <ToastItem
            id={toast.id}
            type={toast.type}
            message={toast.message}
            onRemove={removeToast}
          />
        </div>
      ))}
    </div>
  )
}
