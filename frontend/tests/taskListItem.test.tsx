import { describe, expect, test } from 'bun:test'
import { renderToStaticMarkup } from 'react-dom/server'

import { TaskListItem } from '../src/components/task/TaskListItem'
import type { Task } from '../src/types/task'

function createTask(overrides: Partial<Task> = {}): Task {
  return {
    id: 'task-1',
    displayName: 'demo.mp4',
    filePath: '/data/uploads/demo.mp4',
    fileSize: 1024,
    durationMs: 120_000,
    status: 'REVIEW_PENDING',
    progress: 100,
    totalScenes: 8,
    shotsCount: 8,
    previewThumbnailPath: null,
    processMode: null,
    configProfile: null,
    requestedConfig: null,
    resolvedConfig: null,
    qualityFlags: null,
    suspectSegments: null,
    tuningHistory: null,
    reviewNotes: null,
    latestSplitStats: null,
    detectionResult: {
      scenes: [{ startMs: 0, endMs: 1000 }],
      durationMs: 1000,
      report: {},
    },
    userEditedScenes: null,
    reviewedAt: null,
    createdAt: '2026-03-10T00:00:00',
    updatedAt: '2026-03-10T00:00:00',
    ...overrides,
  }
}

describe('TaskListItem story intro status', () => {
  test('renders task thumbnails as decorative images without exposing the file name as alt text', () => {
    const markup = renderToStaticMarkup(
      <table>
        <tbody>
          <tr>
            <td>
              <TaskListItem
                task={createTask({ previewThumbnailPath: '/api/tasks/task-1/frame?t=500' })}
                analysisStatus={{ taskId: 'task-1', status: 'SUCCEEDED', canRetry: false }}
                selected={false}
                onSelectChange={() => {}}
                onDelete={() => {}}
                onOpenStoryIntro={() => {}}
                onOpenReview={() => {}}
              />
            </td>
          </tr>
        </tbody>
      </table>
    )

    expect(markup).toContain('alt=""')
    expect(markup).not.toContain('alt="demo.mp4"')
  })

  test('renders succeeded story intro status with the same status-label style and no old suffix', () => {
    const markup = renderToStaticMarkup(
      <table>
        <tbody>
          <tr>
            <td>
              <TaskListItem
                task={createTask()}
                analysisStatus={{ taskId: 'task-1', status: 'SUCCEEDED', canRetry: false }}
                selected={false}
                onSelectChange={() => {}}
                onDelete={() => {}}
                onOpenStoryIntro={() => {}}
                onOpenReview={() => {}}
              />
            </td>
          </tr>
        </tbody>
      </table>
    )

    expect(markup).toContain('已完成')
    expect(markup).not.toContain('已完成》')
    expect(markup).toContain('打开任务 demo.mp4 的故事介绍')
    expect(markup).toContain('gap-1.5 rounded px-2 py-0.5 text-small')
    expect(markup).not.toContain('>查看<')
  })

  test('renders non-openable story intro status as a static status label without button affordance', () => {
    const markup = renderToStaticMarkup(
      <table>
        <tbody>
          <tr>
            <td>
              <TaskListItem
                task={createTask()}
                analysisStatus={{ taskId: 'task-1', status: 'FAILED', canRetry: false }}
                selected={false}
                onSelectChange={() => {}}
                onDelete={() => {}}
                onOpenStoryIntro={() => {}}
                onOpenReview={() => {}}
              />
            </td>
          </tr>
        </tbody>
      </table>
    )

    expect(markup).toContain('失败')
    expect(markup).not.toContain('打开任务 demo.mp4 的故事介绍')
    expect(markup).toContain('gap-1.5 rounded px-2 py-0.5 text-small')
  })
})
