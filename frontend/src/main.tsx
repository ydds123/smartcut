import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ReactQueryDevtools } from '@tanstack/react-query-devtools'
import type { AxiosError } from 'axios'
import './index.css'
import App from './App'
import { AppErrorBoundary } from './components/error/AppErrorBoundary'
// ❌ 禁用 Mock API - Sprint 1.2 已完成，前端应调用真实后端 API
// if (import.meta.env.DEV) {
//   import('./mocks/browser')
// }

// 创建 React Query 客户端
function computeRetryDelay(attemptIndex: number, error: unknown): number {
  const axiosError = error as AxiosError | undefined
  const retryAfterHeader = axiosError?.response?.headers?.['retry-after']
  const baseDelay = Math.min(1000 * (2 ** Math.max(0, attemptIndex - 1)), 5000)
  const jitter = Math.floor(Math.random() * 500)
  if (typeof retryAfterHeader === 'string' && retryAfterHeader.trim()) {
    const numeric = Number(retryAfterHeader)
    if (Number.isFinite(numeric) && numeric >= 0) {
      return numeric * 1000 + jitter
    }
    const at = Date.parse(retryAfterHeader)
    if (!Number.isNaN(at)) {
      return Math.max(0, at - Date.now()) + jitter
    }
  }
  return baseDelay + jitter
}

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5000, // 5 秒内数据视为新鲜
      retry: (failureCount, error) => {
        const axiosError = error as AxiosError | undefined
        const status = axiosError?.response?.status
        if (failureCount > 1) {
          return false
        }
        if (status == null) {
          return true
        }
        return [408, 429, 500, 502, 503, 504].includes(status)
      },
      retryDelay: (attemptIndex, error) => computeRetryDelay(attemptIndex, error),
      refetchOnWindowFocus: false, // 窗口聚焦时不自动重新获取
    },
  },
})

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <AppErrorBoundary>
        <App />
      </AppErrorBoundary>
      <ReactQueryDevtools initialIsOpen={false} />
    </QueryClientProvider>
  </StrictMode>,
)
