import { describe, expect, test } from 'bun:test'

import { canOpenTaskPreview, canRetryTaskPreview, hasTaskPreviewData } from '../src/components/task/taskPreviewState'
import type { Task } from '../src/types/task'

function createTask(overrides: Partial<Task> = {}): Task {
  return {
    id: 'task-1',
    displayName: 'demo.mp4',
    filePath: '/tmp/demo.mp4',
    fileSize: 1024,
    durationMs: 120_000,
    status: 'FAILED',
    progress: 0,
    totalScenes: null,
    shotsCount: null,
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
    detectionResult: null,
    userEditedScenes: null,
    reviewedAt: null,
    createdAt: '2026-03-10T00:00:00',
    updatedAt: '2026-03-10T00:00:00',
    ...overrides,
  }
}

describe('taskPreviewState', () => {
  test('shows retry preview when failed task has no preview data', () => {
    const task = createTask()

    expect(hasTaskPreviewData(task)).toBe(false)
    expect(canOpenTaskPreview(task)).toBe(false)
    expect(canRetryTaskPreview(task)).toBe(true)
  })

  test('opens preview for failed task when detection scenes exist', () => {
    const task = createTask({
      detectionResult: {
        scenes: [{ startMs: 0, endMs: 1000 }],
        durationMs: 1000,
        report: {},
      },
    })

    expect(hasTaskPreviewData(task)).toBe(true)
    expect(canOpenTaskPreview(task)).toBe(true)
    expect(canRetryTaskPreview(task)).toBe(false)
  })

  test('uses timeline fallback for completed tasks without cached detection payload', () => {
    const task = createTask({
      status: 'COMPLETED',
      totalScenes: 12,
      shotsCount: 12,
    })

    expect(hasTaskPreviewData(task)).toBe(true)
    expect(canOpenTaskPreview(task)).toBe(true)
  })

  test('requires previewable status even when scene payload exists', () => {
    const task = createTask({
      status: 'DETECTING',
      detectionResult: {
        scenes: [{ startMs: 0, endMs: 1000 }],
        durationMs: 1000,
        report: {},
      },
    })

    expect(hasTaskPreviewData(task)).toBe(true)
    expect(canOpenTaskPreview(task)).toBe(false)
    expect(canRetryTaskPreview(task)).toBe(false)
  })
})
