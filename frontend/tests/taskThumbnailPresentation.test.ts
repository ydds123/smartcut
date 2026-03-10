import { describe, expect, test } from 'bun:test'

import { getTaskThumbnailPresentation } from '../src/components/task/taskThumbnailPresentation'

describe('taskThumbnailPresentation', () => {
  test('renders the image when preview url exists and loading has not failed', () => {
    expect(getTaskThumbnailPresentation('http://127.0.0.1:8000/api/tasks/task-1/frame?t=500', false)).toEqual({
      alt: '',
      shouldRenderImage: true,
    })
  })

  test('falls back to placeholder when preview url is missing', () => {
    expect(getTaskThumbnailPresentation(null, false)).toEqual({
      alt: '',
      shouldRenderImage: false,
    })
  })

  test('falls back to placeholder after image load failure', () => {
    expect(getTaskThumbnailPresentation('http://127.0.0.1:8000/api/tasks/task-1/frame?t=500', true)).toEqual({
      alt: '',
      shouldRenderImage: false,
    })
  })
})
