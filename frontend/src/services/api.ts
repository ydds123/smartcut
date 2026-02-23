import axios, { AxiosInstance, AxiosError } from 'axios'
import type { ApiError } from '@/types/task'

const API_TOKEN = (import.meta.env.VITE_API_TOKEN || '').trim()

// 创建 Axios 实例
const apiClient: AxiosInstance = axios.create({
  baseURL: import.meta.env.VITE_API_URL || '',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
})

// 请求拦截器
apiClient.interceptors.request.use(
  (config) => {
    if (API_TOKEN) {
      if (config.headers && typeof (config.headers as any).set === 'function') {
        ;(config.headers as any).set('X-API-Token', API_TOKEN)
      } else {
        config.headers = {
          ...(config.headers as Record<string, string> | undefined),
          'X-API-Token': API_TOKEN,
        } as any
      }
    }
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// 响应拦截器
apiClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError<ApiError>) => {
    // 统一错误处理
    if (error.response) {
      // 服务器返回错误状态码
      const message = error.response.data?.detail || error.message
      console.error('API Error:', message)
    } else if (error.request) {
      // 请求已发出但没有收到响应
      console.error('Network Error: No response received')
    } else {
      // 请求配置错误
      console.error('Request Config Error:', error.message)
    }
    return Promise.reject(error)
  }
)

export default apiClient
