import { describe, expect, test } from 'bun:test'

import { buildAnalysisApiKeyGuidance } from '../src/components/task/analysisSettingsGuidance'
import type { AnalysisSettings } from '../src/types/analysis'

function createSettings(overrides: Partial<AnalysisSettings> = {}): AnalysisSettings {
  return {
    provider: 'gemini',
    baseUrl: 'https://generativelanguage.googleapis.com',
    model: 'gemini-2.5-flash',
    promptTemplate: 'prompt',
    analysisEnabled: true,
    requestTimeoutSec: 120,
    hasApiKey: false,
    apiKeySource: 'missing',
    envFilePath: '/tmp/backend/.env',
    envFileExists: true,
    canOpenEnvFile: true,
    envVariableName: 'ANALYSIS_API_KEY',
    isComplete: false,
    incompleteReasons: ['服务端未配置 ANALYSIS_API_KEY'],
    updatedAt: null,
    ...overrides,
  }
}

describe('buildAnalysisApiKeyGuidance', () => {
  test('builds current file guidance for dotenv sourced key', () => {
    const guidance = buildAnalysisApiKeyGuidance(
      createSettings({
        hasApiKey: true,
        apiKeySource: 'dotenv_file',
      })
    )

    expect(guidance.sourceLabel).toBe('.env 文件')
    expect(guidance.openButtonLabel).toBe('打开当前 API Key 配置文件')
    expect(guidance.visibleEnvFilePath).toBe('/tmp/backend/.env')
  })

  test('hides file affordance for process environment sourced key', () => {
    const guidance = buildAnalysisApiKeyGuidance(
      createSettings({
        hasApiKey: true,
        apiKeySource: 'process_env',
      })
    )

    expect(guidance.sourceLabel).toBe('进程环境变量')
    expect(guidance.openButtonLabel).toBeNull()
    expect(guidance.visibleEnvFilePath).toBeNull()
  })

  test('shows recommended file action when key is missing but local file can be opened', () => {
    const guidance = buildAnalysisApiKeyGuidance(createSettings())

    expect(guidance.sourceLabel).toBe('未配置')
    expect(guidance.openButtonLabel).toBe('打开推荐配置文件')
    expect(guidance.visibleEnvFilePath).toBe('/tmp/backend/.env')
  })
})
