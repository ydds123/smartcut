import { beforeEach, describe, expect, test } from 'bun:test'

import { useUIStore } from '../src/stores/uiStore'

function resetUIStore() {
  useUIStore.setState({
    isTimelineOpen: false,
    selectedTaskId: null,
    isUploadModalOpen: false,
    isReviewModalOpen: false,
    reviewTaskId: null,
    isStoryIntroModalOpen: false,
    storyIntroTaskId: null,
    toasts: [],
  })
}

describe('uiStore story intro modal state', () => {
  beforeEach(() => {
    resetUIStore()
  })

  test('opens story intro modal without requiring ReviewModal state', () => {
    useUIStore.getState().openStoryIntroModal('task-story')

    const state = useUIStore.getState()
    expect(state.isStoryIntroModalOpen).toBe(true)
    expect(state.storyIntroTaskId).toBe('task-story')
    expect(state.isReviewModalOpen).toBe(false)
    expect(state.reviewTaskId).toBeNull()
  })

  test('closing story intro modal does not close ReviewModal', () => {
    useUIStore.getState().openReviewModal('task-review')
    useUIStore.getState().openStoryIntroModal('task-review')

    useUIStore.getState().closeStoryIntroModal()

    const state = useUIStore.getState()
    expect(state.isReviewModalOpen).toBe(true)
    expect(state.reviewTaskId).toBe('task-review')
    expect(state.isStoryIntroModalOpen).toBe(false)
    expect(state.storyIntroTaskId).toBeNull()
  })
})
