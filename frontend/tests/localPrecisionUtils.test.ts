import { describe, expect, test } from 'bun:test'

import {
  mergeLocalPrecisionProposal,
  normalizeReviewScenes,
  resolveLocalPrecisionAnchorSceneIndex,
} from '../src/components/review/localPrecisionUtils'
import type { LocalPrecisionTargetRange, ReviewScene } from '../src/types/task'

const SCENES: ReviewScene[] = [
  { startMs: 0, endMs: 1000 },
  { startMs: 1000, endMs: 2000 },
  { startMs: 2000, endMs: 3000 },
  { startMs: 3000, endMs: 4000 },
]

describe('resolveLocalPrecisionAnchorSceneIndex', () => {
  test('prefers playhead matched scene', () => {
    expect(resolveLocalPrecisionAnchorSceneIndex(SCENES, 2500, 0)).toBe(2)
  })

  test('falls back to selected scene index when playhead misses', () => {
    expect(resolveLocalPrecisionAnchorSceneIndex(SCENES, 4500, 1)).toBe(1)
  })

  test('returns null when neither playhead nor selection is usable', () => {
    expect(resolveLocalPrecisionAnchorSceneIndex([], 100, null)).toBeNull()
    expect(resolveLocalPrecisionAnchorSceneIndex(SCENES, 4500, 99)).toBeNull()
  })
})

describe('normalizeReviewScenes', () => {
  test('sorts and removes exact duplicates', () => {
    expect(
      normalizeReviewScenes([
        { startMs: 1000, endMs: 2000 },
        { startMs: 0, endMs: 1000 },
        { startMs: 1000, endMs: 2000 },
      ])
    ).toEqual([
      { startMs: 0, endMs: 1000 },
      { startMs: 1000, endMs: 2000 },
    ])
  })

  test('throws when scenes overlap', () => {
    expect(() =>
      normalizeReviewScenes([
        { startMs: 0, endMs: 1200 },
        { startMs: 1000, endMs: 2000 },
      ])
    ).toThrow('scene overlap detected')
  })
})

describe('mergeLocalPrecisionProposal', () => {
  test('replaces only scenes overlapping the target window', () => {
    const targetRange: LocalPrecisionTargetRange = {
      startMs: 1000,
      endMs: 3000,
      startIndex: 1,
      endIndex: 2,
    }

    expect(
      mergeLocalPrecisionProposal(SCENES, targetRange, [
        { startMs: 1000, endMs: 1800 },
        { startMs: 1800, endMs: 3000 },
      ])
    ).toEqual([
      { startMs: 0, endMs: 1000 },
      { startMs: 1000, endMs: 1800 },
      { startMs: 1800, endMs: 3000 },
      { startMs: 3000, endMs: 4000 },
    ])
  })
})
