import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ReactQueryDevtools } from '@tanstack/react-query-devtools'
import './index.css'
import App from './App'
// ❌ 禁用 Mock API - Sprint 1.2 已完成，前端应调用真实后端 API
// if (import.meta.env.DEV) {
//   import('./mocks/browser')
// }

// 创建 React Query 客户端
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5000, // 5 秒内数据视为新鲜
      retry: 1, // 失败重试 1 次
      refetchOnWindowFocus: false, // 窗口聚焦时不自动重新获取
    },
  },
})

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
      <ReactQueryDevtools initialIsOpen={false} />
    </QueryClientProvider>
  </StrictMode>,
)
