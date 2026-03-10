/**
 * Error Boundary 组件
 * 捕获子组件中的 JavaScript 错误，显示友好的错误界面
 */
import { Component, ErrorInfo, ReactNode } from 'react'

interface Props {
  children: ReactNode
  fallback?: ReactNode
  onError?: (error: Error, errorInfo: ErrorInfo) => void
}

interface State {
  hasError: boolean
  error: Error | null
}

export class TimelineModalErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props)
    this.state = {
      hasError: false,
      error: null
    }
  }

  static getDerivedStateFromError(error: Error): State {
    return {
      hasError: true,
      error
    }
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('TimelineModal Error Boundary 捕获到错误:', error, errorInfo)

    // 调用自定义错误处理回调
    if (this.props.onError) {
      this.props.onError(error, errorInfo)
    }
  }

  render() {
    if (this.state.hasError) {
      // 使用自定义降级 UI 或默认错误界面
      if (this.props.fallback) {
        return this.props.fallback
      }

      return (
        <div className="flex items-center justify-center h-64">
          <div className="p-8 text-center">
            <svg
              className="mx-auto mb-4 h-16 w-16 text-[var(--sc-danger)]"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
              />
            </svg>
            <h3 className="mb-2 text-lg font-semibold text-[var(--sc-text-primary)]">
              镜头加载失败
            </h3>
            <p className="mb-4 text-[var(--sc-text-secondary)]">
              加载镜头时发生错误，请稍后重试
            </p>
            <button
              onClick={() => window.location.reload()}
              className="sc-btn sc-btn-primary h-9 px-4 text-sm"
            >
              重新加载
            </button>
          </div>
        </div>
      )
    }

    return this.props.children
  }
}
