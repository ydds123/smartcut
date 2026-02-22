/**
 * 任务状态枚举
 */
export type TaskStatus =
  | 'PENDING'
  | 'QUEUED'
  | 'PROCESSING'
  | 'COMPLETED'
  | 'FAILED'
  | 'DETECTING'
  | 'REVIEW_PENDING'
  | 'REVIEW_APPROVED'
  | 'SPLITTING'
  | 'TIMELINE_READY'

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
  transnetToleranceFrames: number
  transnetWindowSize: number
  transnetTimeoutSec: number
  transnetAdditionalBoundaryThreshold: number
  transnetOnlyMinGapFrames: number
}

export interface ProcessTaskOptions {
  mode?: ProcessingMode
  profile?: 'quality'
  overrideConfig?: Partial<ProcessingConfig>
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

/**
 * 任务实体
 */
export interface Task {
  id: string
  displayName: string
  filePath: string
  fileSize: number
  status: TaskStatus
  progress: number
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

/**
 * SSE 进度事件
 */
export interface ProgressEvent {
  taskId: string
  progress: number
  status: TaskStatus
  message?: string
}

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
