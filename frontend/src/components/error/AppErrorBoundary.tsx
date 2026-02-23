import { Component, type ErrorInfo, type ReactNode } from 'react'

interface AppErrorBoundaryProps {
  children: ReactNode
}

interface AppErrorBoundaryState {
  hasError: boolean
  error: Error | null
}

export class AppErrorBoundary extends Component<AppErrorBoundaryProps, AppErrorBoundaryState> {
  constructor(props: AppErrorBoundaryProps) {
    super(props)
    this.state = {
      hasError: false,
      error: null,
    }
  }

  static getDerivedStateFromError(error: Error): AppErrorBoundaryState {
    return {
      hasError: true,
      error,
    }
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('Global Error Boundary caught an error:', error, errorInfo)
  }

  render() {
    if (!this.state.hasError) {
      return this.props.children
    }

    return (
      <div className="flex min-h-screen items-center justify-center bg-[var(--sc-bg-app)] px-6 text-[var(--sc-text-primary)]">
        <div className="sc-panel w-full max-w-[560px] rounded-xl p-8 text-center shadow-sm">
          <h1 className="mb-3 text-2xl font-semibold">页面发生运行时错误</h1>
          <p className="mb-6 text-sm text-[var(--sc-text-muted)]">
            请刷新页面后重试。如果问题持续出现，请查看控制台日志定位具体组件错误。
          </p>
          <button
            type="button"
            className="inline-flex items-center rounded-md bg-[var(--sc-brand-500)] px-4 py-2 text-sm font-medium text-white hover:opacity-90"
            onClick={() => window.location.reload()}
          >
            重新加载
          </button>
        </div>
      </div>
    )
  }
}
