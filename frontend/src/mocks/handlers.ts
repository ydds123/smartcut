import { http, HttpResponse } from 'msw'
import { setupWorker } from 'msw/browser'

// 模拟任务数据
const mockTasks = [
  {
    id: '1',
    displayName: '示例视频 1.mp4',
    filePath: '/data/tasks/1/original.mp4',
    fileSize: 104857600, // 100MB
    status: 'COMPLETED',
    progress: 100,
    totalScenes: 12,
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
  },
  {
    id: '2',
    displayName: '示例视频 2.mov',
    filePath: '/data/tasks/2/original.mp4',
    fileSize: 52428800, // 50MB
    status: 'PROCESSING',
    progress: 65,
    totalScenes: null,
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
  },
  {
    id: '3',
    displayName: '待处理视频.mp4',
    filePath: '/data/tasks/3/original.mp4',
    fileSize: 209715200, // 200MB
    status: 'PENDING',
    progress: 0,
    totalScenes: null,
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
  },
]

// MSW handlers
export const handlers = [
  // 获取任务列表
  http.get('/api/tasks', () => {
    return HttpResponse.json(mockTasks)
  }),

  // 获取任务详情
  http.get('/api/tasks/:id', ({ params }) => {
    const task = mockTasks.find((t) => t.id === params.id)
    if (!task) {
      return HttpResponse.json({ detail: 'Task not found' }, { status: 404 })
    }
    return HttpResponse.json(task)
  }),

  // 删除任务
  http.delete('/api/tasks/:id', () => {
    return HttpResponse.json({ success: true })
  }),

  // 开始处理任务
  http.post('/api/tasks/:id/process', () => {
    return HttpResponse.json({ status: 'QUEUED' })
  }),

  // 获取任务结果
  http.get('/api/tasks/:id/result', () => {
    return HttpResponse.json({
      scenes: [
        {
          id: 's1',
          taskId: '1',
          sequenceIndex: 0,
          startMs: 0,
          endMs: 5000,
          filePath: '/scenes/001.mp4',
          thumbnailPath: null,
          createdAt: new Date().toISOString(),
        },
      ],
    })
  }),
]

// 设置 MSW worker
export const worker = setupWorker(...handlers)
