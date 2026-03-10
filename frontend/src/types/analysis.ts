export type AnalysisProvider = 'gemini' | 'openai_compatible' | 'anthropic' | string
export type AnalysisApiKeySource = 'dotenv_file' | 'process_env' | 'missing' | string

export interface AnalysisSettings {
  provider: AnalysisProvider
  baseUrl: string
  model: string
  promptTemplate: string
  analysisEnabled: boolean
  requestTimeoutSec: number
  hasApiKey: boolean
  apiKeySource: AnalysisApiKeySource
  envFilePath?: string | null
  envFileExists: boolean
  canOpenEnvFile: boolean
  envVariableName: string
  isComplete: boolean
  incompleteReasons?: string[]
  updatedAt?: string | null
}

export interface AnalysisSettingsUpdatePayload {
  provider: AnalysisProvider
  baseUrl: string
  model: string
  promptTemplate: string
  analysisEnabled: boolean
  requestTimeoutSec: number
}

export interface AnalysisSettingsTestResult {
  success: boolean
  message: string
  latencyMs?: number | null
}

export interface AnalysisOpenEnvFileResult {
  success: boolean
  message: string
  path?: string | null
}

export type AnalysisRunStatus =
  | 'NOT_CONFIGURED'
  | 'NOT_STARTED'
  | 'QUEUED'
  | 'RUNNING'
  | 'SUCCEEDED'
  | 'FAILED'

export interface TaskAnalysisLatest {
  taskId: string
  analysisType: 'story_intro'
  status: AnalysisRunStatus
  runId?: string | null
  storyIntroMarkdown?: string | null
  summary?: string | null
  errorMessage?: string | null
  canRetry: boolean
  isConfigured: boolean
  hasApiKey: boolean
  apiKeySource: AnalysisApiKeySource
  updatedAt?: string | null
  finishedAt?: string | null
}

export interface RetryAnalysisResponse {
  taskId?: string
  analysisType?: string
  runId: string
  status: Exclude<AnalysisRunStatus, 'NOT_CONFIGURED' | 'NOT_STARTED'>
  deduplicated: boolean
  message?: string | null
}

export interface TaskAnalysisBatchItem {
  taskId: string
  status: AnalysisRunStatus
  runId?: string | null
  canRetry: boolean
  updatedAt?: string | null
}

export interface TaskAnalysisLatestBatchResponse {
  items: TaskAnalysisBatchItem[]
}
