import { worker } from './handlers'

// 启动 Mock Service Worker
worker.start({
  onUnhandledRequest: 'bypass',
}).then(() => {
  console.log('🔶 MSW Mock API 已启动')
}).catch((error) => {
  console.error('❌ MSW 启动失败:', error)
})
