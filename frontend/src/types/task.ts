/**
 * 任务状态枚举
 */
export type TaskStatus =
  | 'PENDING'
  | 'QUEUED'
  | 'PROCESSING'
  | 'COMPLETED'
  | 'FAILED'
  | 'ANALYZE_QUEUED'
  | 'ANALYZING'
  | 'ANALYZE_FAILED'
  | 'DETECTING'
  | 'REVIEW_PENDING'
  | 'REVIEW_APPROVED'
  | 'SPLITTING'
  | 'TIMELINE_READY'

export const ACTIVE_TASK_STATUSES: TaskStatus[] = [
  'QUEUED',
  'PROCESSING',
  'ANALYZE_QUEUED',
  'ANALYZING',
  'DETECTING',
  'REVIEW_APPROVED',
  'SPLITTING',
]

export const PROGRESS_VISIBLE_TASK_STATUSES: TaskStatus[] = [
  ...ACTIVE_TASK_STATUSES,
]

export const TERMINAL_TASK_STATUSES: TaskStatus[] = [
  'COMPLETED',
  'FAILED',
  'ANALYZE_FAILED',
  'REVIEW_PENDING',
  'TIMELINE_READY',
]

export const PREVIEWABLE_TASK_STATUSES: TaskStatus[] = [
  'REVIEW_PENDING',
  'REVIEW_APPROVED',
  'SPLITTING',
  'TIMELINE_READY',
  'COMPLETED',
  'FAILED',
  'ANALYZE_FAILED',
]

export const DELETABLE_TASK_STATUSES: TaskStatus[] = [
  'PENDING',
  'QUEUED',
  'PROCESSING',
  'DETECTING',
  'REVIEW_PENDING',
  'REVIEW_APPROVED',
  'SPLITTING',
  'TIMELINE_READY',
  'COMPLETED',
  'FAILED',
  'ANALYZE_QUEUED',
  'ANALYZING',
  'ANALYZE_FAILED',
]

export interface ReviewScene {
  startMs: number
  endMs: number
}

export interface DetectionResult {
  scenes: ReviewScene[]
  durationMs: number
  report: Record<string, unknown>
}

export type DetectorMode = 'content' | 'adaptive'
export type DetectionMode = 'fast' | 'precision'
export type ProcessingMode = 'manual'

export interface ProcessingConfig {
  detector: DetectorMode
  detectionMode: DetectionMode
  useTransnet: boolean
  sceneThreshold: number
  minSceneLenFrames: number
  minSceneDurationMsFloor: number
  downscale: number
  frameSkip: number
  adaptiveThreshold: number
  adaptiveMinContentVal: number
  adaptiveFrameWindow: number
  thumbnailRetry: number
  weightHue: number
  weightSat: number
  weightLum: number
  weightEdges: number
  transnetThreshold: number
  transnetSoftCandidateMultiplier: number
  transnetToleranceFrames: number
  transnetWindowSize: number
  transnetAdditionalBoundaryThreshold: number
  transnetOnlyMinGapFrames: number
  useThresholdDetector: boolean
  thresholdDetectorThreshold: number
  thresholdDetectorFadeBias: number
  mergeGapFrames: number
  splitCopyMode: boolean
  scenedetectTimeoutSec: number
}

export interface ProcessTaskOptions {
  mode?: ProcessingMode
  profile?: 'quality'
  overrideConfig?: Partial<ProcessingConfig>
}

export type ProcessingFieldGroup = 'sensitivity' | 'min-scene' | 'stability' | 'transnet' | 'misc'

export interface ProcessingConfigGroupMeta {
  id: ProcessingFieldGroup
  label: string
  description: string
}

export interface ProcessingConfigFieldMeta {
  key: keyof ProcessingConfig
  type: 'enum' | 'bool' | 'int' | 'float'
  default: string | number | boolean
  min?: number | null
  max?: number | null
  step?: number | null
  group?: ProcessingFieldGroup | null
  label?: string | null
  description?: string | null
  detectorScope?: 'adaptive' | 'content' | null
  modeScope?: 'precision' | null
  boolScope?: keyof ProcessingConfig | null
  options?: string[] | null
  provenance: 'pyscenedetect' | 'smartcut'
  sourceRef?: string | null
  uiVisible: boolean
}

export interface ProcessingConfigMeta {
  version: string
  groups: ProcessingConfigGroupMeta[]
  defaults: ProcessingConfig
  fields: ProcessingConfigFieldMeta[]
}

export interface ProcessTaskResult {
  status: string
  jobId?: string
  deduplicated?: boolean
  resolvedConfig?: Partial<ProcessingConfig>
  configMeta?: ProcessingConfigMeta
}

export interface QualityFlags {
  overSegmented?: boolean
  underSegmented?: boolean
  unstableBoundary?: boolean
  flashFalseCut?: boolean
  shotsPerMinute?: number
  shortShotRatio?: number
  veryShortRatio?: number
  longShotRatio?: number
  sceneCount?: number
  metrics?: Record<string, number>
  [key: string]: unknown
}

export interface SuspectSegment {
  sequenceIndex: number
  startMs: number
  endMs: number
  reason: string
  confidence: number
  reviewHint?: string
}

export interface SplitStats {
  totalScenes: number
  reusedCount: number
  renderedCount: number
  reusedRatio: number
  incrementalEnabled?: boolean
  fallbackFullResplit: boolean
  linkSuccessCount?: number
  copyFallbackCount?: number
  planElapsedMs?: number
  reuseMaterializeElapsedMs?: number
  renderElapsedMs?: number
  dbElapsedMs?: number
  cleanupElapsedMs?: number
  totalElapsedMs?: number
}

/**
 * 任务实体
 */
export interface Task {
  id: string
  displayName: string
  filePath: string
  fileSize: number
  durationMs?: number | null
  status: TaskStatus
  progress: number
  activeOperation?: string | null
  activeJobId?: string | null
  totalScenes: number | null
  shotsCount?: number | null
  previewThumbnailPath?: string | null
  processMode?: string | null
  configProfile?: string | null
  requestedConfig?: Partial<ProcessingConfig> | null
  resolvedConfig?: Partial<ProcessingConfig> | null
  qualityFlags?: QualityFlags | null
  suspectSegments?: SuspectSegment[] | null
  tuningHistory?: Array<Record<string, unknown>> | null
  reviewNotes?: string | null
  latestSplitStats?: SplitStats | null
  detectionResult?: DetectionResult | null
  userEditedScenes?: ReviewScene[] | null
  reviewedAt?: string | null
  createdAt: string
  updatedAt: string
}

/**
 * 镜头/片段实体
 */
export interface Scene {
  id: string
  taskId: string
  sequenceIndex: number
  startMs: number
  endMs: number
  filePath: string | null
  thumbnailPath: string | null
  createdAt: string
}

/**
 * 创建任务 DTO
 */
export interface CreateTaskDTO {
  displayName: string
  file: File
}

/**
 * 上传进度
 */
export interface UploadProgress {
  loaded: number
  total: number
  percentage: number
}

export interface ProgressStreamEvent {
  type: 'progress' | 'terminal'
  taskId: string
  progress: number
  status: TaskStatus
  totalScenes?: number | null
  timestamp: number
}

export interface ProgressStreamErrorEvent {
  type: 'error'
  taskId: string
  errorCode: string
  errorMessage: string
  timestamp: number
}

export type ProgressStreamPayload = ProgressStreamEvent | ProgressStreamErrorEvent

/**
 * 任务详情（包含镜头列表）
 */
export interface TaskDetail extends Task {
  scenes: Scene[]
}

/**
 * API 响应包装
 */
export interface ApiResponse<T> {
  data: T
  message?: string
}

/**
 * 错误响应
 */
export interface ApiError {
  detail: string
  status?: number
}
