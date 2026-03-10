import type { LocalPrecisionTargetRange, ReviewScene } from '@/types/task'

function isFiniteScene(scene: ReviewScene): boolean {
  return Number.isFinite(scene.startMs) && Number.isFinite(scene.endMs)
}

function sceneOverlapsRange(scene: ReviewScene, targetRange: LocalPrecisionTargetRange): boolean {
  return scene.startMs < targetRange.endMs && scene.endMs > targetRange.startMs
}

export function resolveLocalPrecisionAnchorSceneIndex(
  scenes: ReviewScene[],
  playheadMs: number,
  selectedSceneIndex: number | null
): number | null {
  if (scenes.length === 0) {
    return null
  }

  const playheadIndex = scenes.findIndex(
    (scene) => playheadMs >= scene.startMs && playheadMs < scene.endMs
  )
  if (playheadIndex >= 0) {
    return playheadIndex
  }

  if (selectedSceneIndex !== null && selectedSceneIndex >= 0 && selectedSceneIndex < scenes.length) {
    return selectedSceneIndex
  }

  return null
}

export function normalizeReviewScenes(scenes: ReviewScene[]): ReviewScene[] {
  const deduplicated = new Map<string, ReviewScene>()

  for (const scene of scenes) {
    if (!isFiniteScene(scene)) {
      throw new Error('scene timing must be finite')
    }
    if (scene.endMs <= scene.startMs) {
      throw new Error('scene endMs must be greater than startMs')
    }

    const key = `${scene.startMs}:${scene.endMs}`
    if (!deduplicated.has(key)) {
      deduplicated.set(key, { startMs: scene.startMs, endMs: scene.endMs })
    }
  }

  const normalized = [...deduplicated.values()].sort((left, right) => left.startMs - right.startMs)

  for (let index = 1; index < normalized.length; index += 1) {
    const previous = normalized[index - 1]
    const current = normalized[index]
    if (current.startMs < previous.endMs) {
      throw new Error(`scene overlap detected at index ${index}`)
    }
  }

  return normalized
}

export function areReviewScenesEqual(left: ReviewScene[], right: ReviewScene[]): boolean {
  const normalizedLeft = normalizeReviewScenes(left)
  const normalizedRight = normalizeReviewScenes(right)

  if (normalizedLeft.length !== normalizedRight.length) {
    return false
  }

  return normalizedLeft.every((scene, index) => {
    const candidate = normalizedRight[index]
    return scene.startMs === candidate.startMs && scene.endMs === candidate.endMs
  })
}

export function mergeLocalPrecisionProposal(
  baseScenes: ReviewScene[],
  targetRange: LocalPrecisionTargetRange,
  proposedScenes: ReviewScene[]
): ReviewScene[] {
  const preservedScenes = baseScenes.filter((scene) => !sceneOverlapsRange(scene, targetRange))
  return normalizeReviewScenes([...preservedScenes, ...proposedScenes])
}
