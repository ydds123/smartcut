import type { ProcessTaskOptions, ProcessingConfig } from '@/types/task'

const STORAGE_KEY = 'smartcut:processing-config:v1'

export interface ProcessingPanelSettings {
  profile: 'quality'
  enableOverride: boolean
  overrideConfig: Partial<ProcessingConfig>
}

export const DEFAULT_PROCESSING_SETTINGS: ProcessingPanelSettings = {
  profile: 'quality',
  enableOverride: false,
  overrideConfig: {
    detector: 'content',
    detectionMode: 'fast',
    useTransnet: false,
    sceneThreshold: 27,
    minSceneLenFrames: 15,
    minSceneDurationMsFloor: 1000,
    downscale: 1,
    frameSkip: 0,
    adaptiveThreshold: 3,
    adaptiveMinContentVal: 15,
    adaptiveFrameWindow: 2,
    thumbnailRetry: 1,
    weightHue: 1,
    weightSat: 1,
    weightLum: 1,
    weightEdges: 0,
    transnetThreshold: 0.3,
    transnetSoftCandidateMultiplier: 0.75,
    transnetToleranceFrames: 12,
    transnetWindowSize: 100,
    transnetAdditionalBoundaryThreshold: 0.55,
    transnetOnlyMinGapFrames: 12,
    useThresholdDetector: false,
    thresholdDetectorThreshold: 12,
    thresholdDetectorFadeBias: 0,
    mergeGapFrames: 0,
    splitCopyMode: false,
    scenedetectTimeoutSec: 600,
  },
}

const ALLOWED_OVERRIDE_KEYS = Object.keys(
  DEFAULT_PROCESSING_SETTINGS.overrideConfig
) as Array<keyof ProcessingConfig>

function sanitizeOverrideConfig(
  overrideConfig: Partial<ProcessingConfig> | undefined | null
): Partial<ProcessingConfig> {
  const sanitized: Partial<ProcessingConfig> = {}
  if (!overrideConfig) {
    return sanitized
  }

  ALLOWED_OVERRIDE_KEYS.forEach((key) => {
    const value = overrideConfig[key]
    if (value !== undefined && value !== null) {
      ;(sanitized as Record<keyof ProcessingConfig, ProcessingConfig[keyof ProcessingConfig]>)[key] =
        value as ProcessingConfig[keyof ProcessingConfig]
    }
  })

  // Backward compatibility for previous typo key in localStorage payload.
  const legacyPayload = overrideConfig as Record<string, unknown>
  if (
    sanitized.thresholdDetectorFadeBias === undefined
    && legacyPayload.thresholdDetectorFadebias !== undefined
    && legacyPayload.thresholdDetectorFadebias !== null
  ) {
    sanitized.thresholdDetectorFadeBias = Number(legacyPayload.thresholdDetectorFadebias)
  }
  return sanitized
}

export function loadProcessingSettings(): ProcessingPanelSettings {
  const raw = localStorage.getItem(STORAGE_KEY)
  if (!raw) {
    return DEFAULT_PROCESSING_SETTINGS
  }

  try {
    const parsed = JSON.parse(raw) as ProcessingPanelSettings
    return {
      ...DEFAULT_PROCESSING_SETTINGS,
      ...parsed,
      overrideConfig: {
        ...DEFAULT_PROCESSING_SETTINGS.overrideConfig,
        ...sanitizeOverrideConfig(parsed.overrideConfig),
      },
    }
  } catch {
    return DEFAULT_PROCESSING_SETTINGS
  }
}

export function persistProcessingSettings(settings: ProcessingPanelSettings): void {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(settings))
}

export function toProcessTaskOptions(settings: ProcessingPanelSettings): ProcessTaskOptions {
  if (!settings.enableOverride) {
    return {
      mode: 'manual',
      profile: settings.profile,
    }
  }

  return {
    mode: 'manual',
    profile: settings.profile,
    overrideConfig: settings.overrideConfig,
  }
}
