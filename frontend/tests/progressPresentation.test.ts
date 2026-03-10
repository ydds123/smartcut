import { describe, expect, test } from 'bun:test'

import {
  LONG_RUNNING_STAGE_MS,
  buildProgressPresentation,
  getTaskStageMessage,
} from '../src/hooks/progressPresentation'

describe('getTaskStageMessage', () => {
  test('maps precision transnet detecting stage to full precision review message', () => {
    expect(
      getTaskStageMessage('DETECTING', 60, {
        detectionMode: 'precision',
        useTransnet: true,
      })
    ).toBe('正在执行整片高精度复检，预计耗时更久')
  })

  test('maps splitting and review approved to positive stage messages', () => {
    expect(getTaskStageMessage('SPLITTING', 72)).toBe('正在输出片段与缩略图')
    expect(getTaskStageMessage('REVIEW_APPROVED', 4)).toBe('已确认分镜，正在生成最终结果')
  })
})

describe('buildProgressPresentation', () => {
  test('keeps real progress unchanged during long-running stages', () => {
    const presentation = buildProgressPresentation({
      progress: 68,
      status: 'DETECTING',
      resolvedConfig: {
        detectionMode: 'precision',
        useTransnet: true,
      },
      totalScenes: 45,
      lastProgressAt: 10_000,
      nowMs: 10_000 + LONG_RUNNING_STAGE_MS + 1,
    })

    expect(presentation.progress).toBe(68)
    expect(presentation.stageMessage).toBe('正在执行整片高精度复检，预计耗时更久')
    expect(presentation.isLongRunningStage).toBe(true)
    expect(presentation.totalScenes).toBe(45)
  })

  test('clears long-running presentation on terminal status', () => {
    const presentation = buildProgressPresentation({
      progress: 100,
      status: 'REVIEW_PENDING',
      resolvedConfig: {
        detectionMode: 'precision',
        useTransnet: true,
      },
      totalScenes: 45,
      lastProgressAt: 10_000,
      nowMs: 10_000 + LONG_RUNNING_STAGE_MS + 1,
    })

    expect(presentation.stageMessage).toBeNull()
    expect(presentation.isLongRunningStage).toBe(false)
  })
})
