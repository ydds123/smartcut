import type { AnalysisSettings } from '@/types/analysis'

export interface AnalysisApiKeyGuidance {
  sourceLabel: string
  sourceMessage: string
  visibleEnvFilePath: string | null
  openButtonLabel: string | null
  openButtonVariant: 'primary' | 'secondary'
}

export function buildAnalysisApiKeyGuidance(
  settings: AnalysisSettings | null | undefined
): AnalysisApiKeyGuidance {
  const source = settings?.apiKeySource || 'missing'
  const canOpenEnvFile = Boolean(settings?.canOpenEnvFile)
  const envFilePath = (settings?.envFilePath || '').trim() || null

  if (source === 'dotenv_file') {
    return {
      sourceLabel: '.env 文件',
      sourceMessage: '当前 API Key 来自本地 .env 配置文件。',
      visibleEnvFilePath: envFilePath,
      openButtonLabel: canOpenEnvFile ? '打开当前 API Key 配置文件' : null,
      openButtonVariant: 'primary',
    }
  }

  if (source === 'process_env') {
    return {
      sourceLabel: '进程环境变量',
      sourceMessage: '当前 API Key 来自进程环境变量，不是来自 .env 文件。',
      visibleEnvFilePath: null,
      openButtonLabel: null,
      openButtonVariant: 'secondary',
    }
  }

  return {
    sourceLabel: '未配置',
    sourceMessage: '当前服务端尚未配置 API Key。你可以在推荐配置文件中新增该环境变量。',
    visibleEnvFilePath: envFilePath,
    openButtonLabel: canOpenEnvFile ? '打开推荐配置文件' : null,
    openButtonVariant: 'secondary',
  }
}
