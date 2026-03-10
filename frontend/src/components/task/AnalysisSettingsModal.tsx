import { useEffect, useState } from 'react'
import type { AnalysisSettings, AnalysisSettingsUpdatePayload } from '@/types/analysis'
import { buildAnalysisApiKeyGuidance } from './analysisSettingsGuidance'

interface AnalysisSettingsModalProps {
  isOpen: boolean
  isLoading: boolean
  isSaving: boolean
  isTesting: boolean
  isOpeningEnvFile: boolean
  settings: AnalysisSettings | null | undefined
  onClose: () => void
  onSave: (payload: AnalysisSettingsUpdatePayload) => Promise<void>
  onTest: (payload: AnalysisSettingsUpdatePayload) => Promise<string>
  onOpenEnvFile: () => Promise<string>
}

function buildDraft(settings: AnalysisSettings | null | undefined): AnalysisSettingsUpdatePayload {
  return {
    provider: settings?.provider || 'gemini',
    baseUrl: settings?.baseUrl || 'https://generativelanguage.googleapis.com',
    model: settings?.model || 'gemini-3.1-flash-lite-preview',
    promptTemplate: settings?.promptTemplate || '',
    analysisEnabled: Boolean(settings?.analysisEnabled),
    requestTimeoutSec: settings?.requestTimeoutSec || 120,
  }
}

export function AnalysisSettingsModal({
  isOpen,
  isLoading,
  isSaving,
  isTesting,
  isOpeningEnvFile,
  settings,
  onClose,
  onSave,
  onTest,
  onOpenEnvFile,
}: AnalysisSettingsModalProps) {
  const [draft, setDraft] = useState<AnalysisSettingsUpdatePayload>(buildDraft(settings))
  const [testMessage, setTestMessage] = useState<string>('')
  const [envActionMessage, setEnvActionMessage] = useState<string>('')

  useEffect(() => {
    if (!isOpen) return
    setDraft(buildDraft(settings))
    setTestMessage('')
    setEnvActionMessage('')
  }, [isOpen, settings])

  if (!isOpen) {
    return null
  }

  const canSubmit = draft.baseUrl.trim().length > 0
    && draft.model.trim().length > 0
    && draft.promptTemplate.trim().length > 0
    && draft.provider.trim().length > 0

  const incompleteReasons = settings?.incompleteReasons || []
  const guidance = buildAnalysisApiKeyGuidance(settings)
  const envVariableName = settings?.envVariableName || 'ANALYSIS_API_KEY'

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-[var(--sc-modal-overlay)] p-4">
      <div className="sc-modal-shell flex max-h-[88vh] w-full max-w-4xl flex-col overflow-hidden">
        <div className="sc-modal-header flex items-center justify-between">
          <div>
            <h2 className="text-sm font-semibold text-[var(--sc-text-primary)]">分析设置</h2>
            <p className="mt-0.5 text-xs text-[var(--sc-text-muted)]">
              API Key 由服务端环境变量托管，页面仅展示可用状态
            </p>
          </div>
          <button type="button" onClick={onClose} className="sc-btn sc-btn-ghost h-7 px-2" disabled={isSaving || isTesting}>
            关闭
          </button>
        </div>

        <div className="min-h-0 flex-1 space-y-4 overflow-y-auto px-5 py-4">
          {isLoading ? (
            <div className="text-sm text-[var(--sc-text-muted)]">读取设置中...</div>
          ) : null}

          <div className="rounded border border-[var(--sc-border-subtle)] bg-[var(--sc-bg-contrast)] px-3 py-2 text-sm">
            <div className="flex items-center justify-between">
              <span className="text-[var(--sc-text-secondary)]">API Key 状态</span>
              <span className={`font-semibold ${settings?.hasApiKey ? 'text-emerald-500' : 'text-[var(--sc-danger)]'}`}>
                {settings?.hasApiKey ? '已就绪' : '未就绪'}
              </span>
            </div>
            <div className="mt-1 text-xs text-[var(--sc-text-muted)]">
              来源：{guidance.sourceLabel}
            </div>
            {incompleteReasons.length > 0 ? (
              <div className="mt-1 text-xs text-[var(--sc-text-muted)]">
                当前缺失项：{incompleteReasons.join('；')}
              </div>
            ) : null}
            <div className="mt-3 rounded border border-[var(--sc-border-subtle)] bg-[var(--sc-bg-surface)] px-3 py-3 text-xs text-[var(--sc-text-secondary)]">
              <div>{guidance.sourceMessage}</div>
              {guidance.visibleEnvFilePath ? (
                <div className="mt-2">
                  {settings?.apiKeySource === 'dotenv_file' ? '当前配置文件：' : '推荐配置文件：'}
                  <code className="ml-1 break-all rounded bg-[var(--sc-bg-contrast)] px-1 py-0.5 text-[var(--sc-text-primary)]">
                    {guidance.visibleEnvFilePath}
                  </code>
                </div>
              ) : null}
              <div className="mt-3 space-y-2">
                <p>为了你的 API Key 安全性，系统采用服务端环境变量方式，不会在页面明文展示。</p>
                <p>
                  如果使用文件配置，请在 <code>{envVariableName}=</code> 这一行的等号后粘贴你的 Key。
                </p>
                <p>修改并保存后，需要重启 <code>backend</code> 和 <code>worker</code> 才会生效。</p>
              </div>
              <pre className="mt-3 overflow-x-auto rounded border border-[var(--sc-border-subtle)] bg-[var(--sc-bg-contrast)] px-3 py-2 text-xs text-[var(--sc-text-primary)]">
{`# AI 分析 API Key
${envVariableName}=your_api_key_here`}
              </pre>
              {guidance.openButtonLabel ? (
                <div className="mt-3">
                  <button
                    type="button"
                    className={`sc-btn ${guidance.openButtonVariant === 'primary' ? 'sc-btn-primary' : 'sc-btn-secondary'} h-8 px-3`}
                    disabled={isOpeningEnvFile}
                    onClick={async () => {
                      const message = await onOpenEnvFile()
                      setEnvActionMessage(message)
                    }}
                  >
                    {isOpeningEnvFile ? '打开中...' : guidance.openButtonLabel}
                  </button>
                </div>
              ) : null}
              {envActionMessage ? (
                <div className="mt-2 text-xs text-[var(--sc-text-muted)]">{envActionMessage}</div>
              ) : null}
            </div>
          </div>

          <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
            <label className="block">
              <div className="mb-1 text-xs font-semibold text-[var(--sc-text-secondary)]">Provider</div>
              <input
                type="text"
                value={draft.provider}
                onChange={(event) => setDraft((previous) => ({ ...previous, provider: event.target.value }))}
                className="sc-input w-full px-2 py-1.5 text-sm"
                placeholder="gemini"
              />
            </label>
            <label className="block">
              <div className="mb-1 text-xs font-semibold text-[var(--sc-text-secondary)]">Model</div>
              <input
                type="text"
                value={draft.model}
                onChange={(event) => setDraft((previous) => ({ ...previous, model: event.target.value }))}
                className="sc-input w-full px-2 py-1.5 text-sm"
                placeholder="gemini-3.1-flash-lite-preview"
              />
            </label>
          </div>

          <label className="block">
            <div className="mb-1 text-xs font-semibold text-[var(--sc-text-secondary)]">访问地址 (Base URL)</div>
            <input
              type="url"
              value={draft.baseUrl}
              onChange={(event) => setDraft((previous) => ({ ...previous, baseUrl: event.target.value }))}
              className="sc-input w-full px-2 py-1.5 text-sm"
              placeholder="https://generativelanguage.googleapis.com"
            />
          </label>

          <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
            <label className="block">
              <div className="mb-1 text-xs font-semibold text-[var(--sc-text-secondary)]">请求超时（秒）</div>
              <input
                type="number"
                min={10}
                max={900}
                step={1}
                value={draft.requestTimeoutSec}
                onChange={(event) => {
                  const value = Number(event.target.value)
                  setDraft((previous) => ({
                    ...previous,
                    requestTimeoutSec: Number.isFinite(value) ? value : previous.requestTimeoutSec,
                  }))
                }}
                className="sc-input w-full px-2 py-1.5 text-sm"
              />
            </label>
            <label className="flex items-end gap-2 pb-2 text-sm text-[var(--sc-text-primary)]">
              <input
                type="checkbox"
                checked={draft.analysisEnabled}
                onChange={(event) => {
                  const enabled = event.target.checked
                  setDraft((previous) => ({ ...previous, analysisEnabled: enabled }))
                }}
              />
              上传后自动发起分析
            </label>
          </div>

          <label className="block">
            <div className="mb-1 text-xs font-semibold text-[var(--sc-text-secondary)]">提示词模板</div>
            <textarea
              value={draft.promptTemplate}
              onChange={(event) => setDraft((previous) => ({ ...previous, promptTemplate: event.target.value }))}
              className="sc-input min-h-[220px] w-full px-2 py-2 text-sm"
              placeholder="输入用于视频分析的提示词模板"
            />
          </label>

          {testMessage ? (
            <div className="rounded border border-[var(--sc-border-subtle)] bg-[var(--sc-bg-contrast)] px-3 py-2 text-xs text-[var(--sc-text-secondary)]">
              {testMessage}
            </div>
          ) : null}
        </div>

        <div className="flex items-center justify-end gap-2 border-t border-[var(--sc-border-subtle)] bg-[var(--sc-bg-surface)] px-5 py-3">
          <button
            type="button"
            className="sc-btn sc-btn-secondary h-8 px-3"
            disabled={!canSubmit || isSaving || isTesting}
            onClick={async () => {
              const message = await onTest(draft)
              setTestMessage(message)
            }}
          >
            {isTesting ? '测试中...' : '测试连接'}
          </button>
          <button
            type="button"
            className="sc-btn sc-btn-primary h-8 px-3"
            disabled={!canSubmit || isSaving || isTesting}
            onClick={async () => {
              await onSave(draft)
            }}
          >
            {isSaving ? '保存中...' : '保存设置'}
          </button>
        </div>
      </div>
    </div>
  )
}
