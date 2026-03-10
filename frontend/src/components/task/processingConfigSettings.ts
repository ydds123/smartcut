import type {
  ProcessTaskOptions,
  ProcessingConfig,
  ProcessingConfigMeta,
} from '@/types/task'

const STORAGE_KEY = 'smartcut:processing-config:v1'

export interface ProcessingPanelSettings {
  profile: 'quality'
  enableOverride: boolean
  overrideConfig: Partial<ProcessingConfig>
}

const FALLBACK_OVERRIDE_DEFAULTS: ProcessingConfig = {
  detector: 'content',
  detectionMode: 'fast',
  useTransnet: false,
  sceneThreshold: 27,
  minSceneLenFrames: 15,
  minSceneDurationMsFloor: 1000,
  downscale: 0,
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
}

function buildOverrideDefaults(meta?: ProcessingConfigMeta | null): ProcessingConfig {
  if (!meta?.defaults) {
    return { ...FALLBACK_OVERRIDE_DEFAULTS }
  }
  return {
    ...FALLBACK_OVERRIDE_DEFAULTS,
    ...meta.defaults,
  }
}

export function buildDefaultProcessingSettings(meta?: ProcessingConfigMeta | null): ProcessingPanelSettings {
  return {
    profile: 'quality',
    enableOverride: false,
    overrideConfig: buildOverrideDefaults(meta),
  }
}

export const DEFAULT_PROCESSING_SETTINGS: ProcessingPanelSettings = buildDefaultProcessingSettings()

function getAllowedOverrideKeys(meta?: ProcessingConfigMeta | null): Array<keyof ProcessingConfig> {
  const dynamicKeys = (meta?.fields || [])
    .map((field) => field.key)
    .filter((key): key is keyof ProcessingConfig => Boolean(key))
  if (dynamicKeys.length > 0) {
    return dynamicKeys
  }
  return Object.keys(FALLBACK_OVERRIDE_DEFAULTS) as Array<keyof ProcessingConfig>
}

function sanitizeOverrideConfig(
  overrideConfig: Partial<ProcessingConfig> | undefined | null,
  allowedKeys: Array<keyof ProcessingConfig>
): Partial<ProcessingConfig> {
  const sanitized: Partial<ProcessingConfig> = {}
  if (!overrideConfig) {
    return sanitized
  }

  allowedKeys.forEach((key) => {
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

export function loadProcessingSettings(meta?: ProcessingConfigMeta | null): ProcessingPanelSettings {
  const defaults = buildDefaultProcessingSettings(meta)
  const allowedKeys = getAllowedOverrideKeys(meta)
  const raw = localStorage.getItem(STORAGE_KEY)
  if (!raw) {
    return defaults
  }

  try {
    const parsed = JSON.parse(raw) as ProcessingPanelSettings
    return {
      ...defaults,
      ...parsed,
      overrideConfig: {
        ...defaults.overrideConfig,
        ...sanitizeOverrideConfig(parsed.overrideConfig, allowedKeys),
      },
    }
  } catch {
    return defaults
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
