import fs from 'node:fs/promises'
import { chromium } from 'playwright'

const API_BASE = 'http://127.0.0.1:8000'
const UI_BASE = 'http://127.0.0.1:5173'
const OUT_DIR = '/Users/apple/Documents/Claude Code/01_项目/短片拉片工具/smartcut/test-results'
const stamp = Date.now()

const screenshotSuccess = `${OUT_DIR}/qa-analysis-success-${stamp}.png`
const screenshotFailed = `${OUT_DIR}/qa-analysis-failed-${stamp}.png`
const reportPath = `${OUT_DIR}/qa-analysis-flow-report-${stamp}.json`

const PREVIEWABLE = new Set([
  'REVIEW_PENDING',
  'REVIEW_APPROVED',
  'SPLITTING',
  'TIMELINE_READY',
  'COMPLETED',
  'FAILED',
  'ANALYZE_FAILED',
])

const DEFAULT_REQUEST_TIMEOUT_MS = 20000

async function requestJson(path, options = {}) {
  const timeoutMs =
    typeof options.timeoutMs === 'number' && Number.isFinite(options.timeoutMs)
      ? Math.max(1000, options.timeoutMs)
      : DEFAULT_REQUEST_TIMEOUT_MS

  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeoutMs)

  try {
    const { timeoutMs: _ignoredTimeout, ...fetchOptions } = options
    const resp = await fetch(`${API_BASE}${path}`, {
      headers: {
        'Content-Type': 'application/json',
        ...(options.headers || {}),
      },
      ...fetchOptions,
      signal: controller.signal,
    })
    const text = await resp.text()
    const payload = text ? JSON.parse(text) : {}
    if (!resp.ok) {
      const detail = payload?.detail || `HTTP ${resp.status}`
      throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail))
    }
    return payload
  } catch (error) {
    if (error?.name === 'AbortError') {
      throw new Error(`请求超时: ${path} (${timeoutMs}ms)`)
    }
    throw new Error(`请求失败: ${path} -> ${error?.message || String(error)}`)
  } finally {
    clearTimeout(timer)
  }
}

async function getTargetTask() {
  const tasks = await requestJson('/api/tasks')
  const candidates = tasks.filter((task) => PREVIEWABLE.has(task.status))
  if (candidates.length === 0) {
    throw new Error('未找到可预览任务，无法执行有头浏览器验证')
  }

  let fallback = null
  for (const task of candidates) {
    const latest = await requestJson(`/api/tasks/${task.id}/analysis/latest`)
    if (!fallback) {
      fallback = { task, latest }
    }
    if (latest.status === 'SUCCEEDED') {
      return { task, latest }
    }
  }

  return fallback
}

function toSettingsPayload(settings) {
  return {
    provider: settings.provider,
    base_url: settings.base_url || settings.baseUrl,
    model: settings.model,
    prompt_template: settings.prompt_template || settings.promptTemplate,
    analysis_enabled:
      typeof settings.analysis_enabled === 'boolean'
        ? settings.analysis_enabled
        : Boolean(settings.analysisEnabled),
    request_timeout_sec: settings.request_timeout_sec || settings.requestTimeoutSec || 300,
  }
}

async function restoreSettings(settings) {
  await requestJson('/api/analysis/settings', {
    method: 'PUT',
    body: JSON.stringify(toSettingsPayload(settings)),
  })
}

async function setAnalysisModel(model) {
  const settings = await requestJson('/api/analysis/settings')
  const payload = toSettingsPayload(settings)
  payload.model = model
  return requestJson('/api/analysis/settings', {
    method: 'PUT',
    body: JSON.stringify(payload),
  })
}

async function enqueueRetry(taskId) {
  return requestJson(`/api/tasks/${taskId}/analysis/retry`, {
    method: 'POST',
    body: JSON.stringify({}),
  })
}

async function ensureFailedLatest(taskId) {
  // 优先尝试预览模型（通常高峰期会失败）
  await setAnalysisModel('gemini-3.1-flash-lite-preview')
  await enqueueRetry(taskId)
  const maybeFailed = await waitLatest(taskId, ['FAILED', 'SUCCEEDED'], 240000)
  if (maybeFailed.status === 'FAILED') {
    return maybeFailed
  }

  // 若预览模型本次成功，则使用强制失败模型兜底覆盖失败态验证
  await setAnalysisModel('gemini-force-fail-for-qa')
  await enqueueRetry(taskId)
  return waitLatest(taskId, ['FAILED'], 60000)
}

async function waitLatest(taskId, expected, timeoutMs = 180000) {
  const startedAt = Date.now()
  while (Date.now() - startedAt < timeoutMs) {
    const latest = await requestJson(`/api/tasks/${taskId}/analysis/latest`)
    if (expected.includes(latest.status)) {
      return latest
    }
    await new Promise((resolve) => setTimeout(resolve, 2500))
  }
  throw new Error(`等待 analysis 状态超时，期望: ${expected.join(', ')}`)
}

async function openReviewModalForTask(page, displayName) {
  const row = page.locator('.sc-row', { hasText: displayName }).first()
  await row.waitFor({ timeout: 20000 })
  await row.getByRole('button', { name: '预览分镜' }).click()
  await page.getByRole('heading', { name: '分镜预览' }).waitFor({ timeout: 15000 })
}

function getStoryIntroTrigger(page) {
  return page.getByRole('button', { name: '故事介绍', exact: true })
}

async function waitForStoryProcessingIndicators(page, timeoutMs = 10000) {
  const startedAt = Date.now()
  let processingVisible = false
  let loadingVisible = false
  while (Date.now() - startedAt < timeoutMs) {
    processingVisible = await page.getByText('正在分析中，请稍候...').isVisible().catch(() => false)
    loadingVisible = await page.getByText('加载分析状态中...').isVisible().catch(() => false)
    if (processingVisible || loadingVisible) {
      break
    }
    await page.waitForTimeout(400)
  }
  return {
    processingVisible,
    loadingVisible,
  }
}

async function closeStoryIntroModalIfOpen(page) {
  const storyModal = page.locator('.sc-modal-shell').filter({
    has: page.getByRole('heading', { name: '故事介绍' }),
  }).last()
  const closeStoryButton = storyModal.getByRole('button', { name: '关闭' })
  const canCloseStoryModal = await closeStoryButton.isVisible().catch(() => false)
  if (canCloseStoryModal) {
    await closeStoryButton.click()
  }
}

async function run() {
  await fs.mkdir(OUT_DIR, { recursive: true })
  const originalSettings = await requestJson('/api/analysis/settings')

  let browser = null
  const checks = []
  let task = null
  try {
    const target = await getTargetTask()
    task = target.task
    const initialLatest = target.latest

    browser = await chromium.launch({ headless: false })
    const page = await browser.newPage({ viewport: { width: 1560, height: 980 } })

    // The app performs background polling, so networkidle can be flaky.
    await page.goto(UI_BASE, { waitUntil: 'domcontentloaded', timeout: 30000 })
    await openReviewModalForTask(page, task.display_name || task.displayName)

    await getStoryIntroTrigger(page).click()
    await page.getByRole('heading', { name: '故事介绍' }).waitFor({ timeout: 10000 })

    let successLatest = initialLatest
    let successVisible = await page
      .locator('pre')
      .first()
      .isVisible()
      .catch(() => false)
    if (successLatest.status === 'SUCCEEDED' && !successVisible) {
      const startedAt = Date.now()
      while (Date.now() - startedAt < 10000) {
        successVisible = await page
          .locator('pre')
          .first()
          .isVisible()
          .catch(() => false)
        if (successVisible) {
          break
        }
        await page.waitForTimeout(400)
      }
    }
    if (successLatest.status !== 'SUCCEEDED') {
      await setAnalysisModel('gemini-2.5-flash')
      await enqueueRetry(task.id)
      successLatest = await waitLatest(task.id, ['SUCCEEDED', 'FAILED'], 300000)
      if (successLatest.status !== 'SUCCEEDED') {
        await setAnalysisModel('gemini-2.5-flash')
        await enqueueRetry(task.id)
        successLatest = await waitLatest(task.id, ['SUCCEEDED'], 300000)
      }
      await page.waitForTimeout(2000)
      successVisible = await page
        .locator('pre')
        .first()
        .isVisible()
        .catch(() => false)
    }
    checks.push({
      name: 'story_modal_success_state',
      pass: successLatest.status === 'SUCCEEDED' && successVisible,
      detail: `api=${successLatest.status}, uiPre=${successVisible}`,
    })
    await page.screenshot({ path: screenshotSuccess, fullPage: true })

    await setAnalysisModel('gemini-2.5-flash')
    await enqueueRetry(task.id)
    const runningFromApi = await waitLatest(task.id, ['QUEUED', 'RUNNING', 'SUCCEEDED', 'FAILED'], 30000)
    checks.push({
      name: 'retry_enters_running',
      pass: runningFromApi.status === 'QUEUED' || runningFromApi.status === 'RUNNING',
      detail: `status=${runningFromApi.status}`,
    })

    await closeStoryIntroModalIfOpen(page)
    const storyHeading = page.getByRole('heading', { name: '故事介绍' })
    const storyHeadingVisible = await storyHeading.isVisible().catch(() => false)
    if (!storyHeadingVisible) {
      await getStoryIntroTrigger(page).click()
      await storyHeading.waitFor({ timeout: 10000 })
    }
    let processingIndicators = await waitForStoryProcessingIndicators(page, 10000)
    if (
      !processingIndicators.processingVisible
      && !processingIndicators.loadingVisible
      && (runningFromApi.status === 'QUEUED' || runningFromApi.status === 'RUNNING')
    ) {
      await closeStoryIntroModalIfOpen(page)
      await page.waitForTimeout(1400)
      await getStoryIntroTrigger(page).click()
      await storyHeading.waitFor({ timeout: 10000 })
      processingIndicators = await waitForStoryProcessingIndicators(page, 10000)
    }
    checks.push({
      name: 'story_modal_processing_state',
      pass:
        (runningFromApi.status === 'QUEUED' || runningFromApi.status === 'RUNNING')
        && (processingIndicators.processingVisible || processingIndicators.loadingVisible),
      detail: `status=${runningFromApi.status}, processing=${processingIndicators.processingVisible}, initialLoading=${processingIndicators.loadingVisible}`,
    })

    const failedLatest = await ensureFailedLatest(task.id)
    await closeStoryIntroModalIfOpen(page)
    const failedStoryHeading = page.getByRole('heading', { name: '故事介绍' })
    const failedStoryHeadingVisible = await failedStoryHeading.isVisible().catch(() => false)
    if (!failedStoryHeadingVisible) {
      await getStoryIntroTrigger(page).click()
      await failedStoryHeading.waitFor({ timeout: 10000 })
    }
    await page.waitForTimeout(2000)
    const failedMessageVisible = await page
      .getByText('分析失败', { exact: false })
      .isVisible()
      .catch(() => false)
    const retryBtnVisible = await page
      .getByRole('button', { name: '重试分析' })
      .isVisible()
      .catch(() => false)
    checks.push({
      name: 'story_modal_failed_state',
      pass: failedLatest.status === 'FAILED' && retryBtnVisible,
      detail: `api=${failedLatest.status}, failedText=${failedMessageVisible}, retryBtn=${retryBtnVisible}`,
    })
    await page.screenshot({ path: screenshotFailed, fullPage: true })

    if (retryBtnVisible) {
      await setAnalysisModel('gemini-2.5-flash')
      await page.getByRole('button', { name: '重试分析' }).click()
      await page.waitForTimeout(1200)
      const processingAgainVisible = await page.getByText('正在分析中，请稍候...').isVisible().catch(() => false)
      const loadingAgainVisible = await page.getByText('加载分析状态中...').isVisible().catch(() => false)
      checks.push({
        name: 'story_modal_retry_action',
        pass: processingAgainVisible || loadingAgainVisible,
        detail: `processingAgain=${processingAgainVisible}, loadingAgain=${loadingAgainVisible}`,
      })
    } else {
      checks.push({
        name: 'story_modal_retry_action',
        pass: false,
        detail: 'retry button not visible, skip click',
      })
    }
  } finally {
    if (browser) {
      await browser.close()
    }
    try {
      await restoreSettings(originalSettings)
    } catch (error) {
      console.error('[qa-analysis-flow-headed] restore settings failed:', error)
    }
  }

  const report = {
    timestamp: new Date().toISOString(),
    task: {
      id: task?.id ?? null,
      displayName: task ? (task.display_name || task.displayName) : null,
    },
    screenshots: {
      success: screenshotSuccess,
      failed: screenshotFailed,
    },
    checks,
    passCount: checks.filter((item) => item.pass).length,
    failCount: checks.filter((item) => !item.pass).length,
  }

  await fs.writeFile(reportPath, JSON.stringify(report, null, 2), 'utf8')
  console.log(JSON.stringify(report, null, 2))
  if (report.failCount > 0) {
    throw new Error(`QA checks failed: ${report.failCount}`)
  }
}

run().then(() => {
  process.exit(0)
}).catch((error) => {
  console.error('[qa-analysis-flow-headed] FAILED:', error)
  process.exit(1)
})
