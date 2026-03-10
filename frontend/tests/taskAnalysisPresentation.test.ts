import { describe, expect, test } from 'bun:test'

import { getTaskAnalysisPresentation } from '../src/components/task/taskAnalysisPresentation'

describe('taskAnalysisPresentation', () => {
  test('maps all analysis statuses to short labels', () => {
    expect(getTaskAnalysisPresentation('NOT_CONFIGURED').label).toBe('未配置')
    expect(getTaskAnalysisPresentation('NOT_STARTED').label).toBe('未开始')
    expect(getTaskAnalysisPresentation('QUEUED').label).toBe('排队中')
    expect(getTaskAnalysisPresentation('RUNNING').label).toBe('分析中')
    expect(getTaskAnalysisPresentation('SUCCEEDED').label).toBe('已完成')
    expect(getTaskAnalysisPresentation('FAILED').label).toBe('失败')
  })

  test('only succeeded analysis can open the story intro modal from the task table', () => {
    expect(getTaskAnalysisPresentation('SUCCEEDED').canOpen).toBe(true)
    expect(getTaskAnalysisPresentation('FAILED').canOpen).toBe(false)
    expect(getTaskAnalysisPresentation('RUNNING').canOpen).toBe(false)
  })

  test('uses a neutral placeholder before batch analysis status has loaded', () => {
    const presentation = getTaskAnalysisPresentation(undefined, false)

    expect(presentation.label).toBe('--')
    expect(presentation.canOpen).toBe(false)
  })
})
