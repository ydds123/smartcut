import { chromium } from 'playwright'

const BASE_URL = process.env.QA_BASE_URL || 'http://localhost:5173'
const API_BASE_URL = process.env.QA_API_URL || 'http://127.0.0.1:8000'
const VIDEO_PATH =
  process.env.QA_VIDEO_PATH ||
  '/Users/apple/Downloads/Downie4 下载/黑色环保动画短片《转折点》，当人类成为濒危动物时，世界会怎样？.mp4'

function createStamp() {
  return new Date().toISOString().replace(/[:.]/g, '-')
}

async function fetchTaskCount() {
  const response = await fetch(`${API_BASE_URL}/api/tasks`)
  if (!response.ok) {
    throw new Error(`读取任务列表失败: HTTP ${response.status}`)
  }
  const data = await response.json()
  return Array.isArray(data) ? data.length : 0
}

async function waitForTaskCountIncrease(beforeCount, timeoutMs = 60000) {
  const deadline = Date.now() + timeoutMs
  while (Date.now() < deadline) {
    const count = await fetchTaskCount()
    if (count > beforeCount) {
      return count
    }
    await new Promise((resolve) => setTimeout(resolve, 1000))
  }
  return beforeCount
}

async function run() {
  const stamp = createStamp()
  const screenshots = {
    initial: `/tmp/qa-${stamp}-01-initial.png`,
    modal: `/tmp/qa-${stamp}-02-modal.png`,
    afterUpload: `/tmp/qa-${stamp}-03-after-upload.png`,
    final: `/tmp/qa-${stamp}-04-final.png`,
  }

  const browser = await chromium.launch({ headless: false })
  const context = await browser.newContext({ viewport: { width: 1920, height: 1080 } })
  const page = await context.newPage()

  const consoleErrors = []
  const pageErrors = []
  const networkErrors = []

  page.on('console', (msg) => {
    if (msg.type() === 'error') {
      consoleErrors.push(msg.text())
    }
  })
  page.on('pageerror', (err) => {
    pageErrors.push(err.message)
  })
  page.on('response', (resp) => {
    if (resp.status() >= 400) {
      networkErrors.push(`${resp.status()} ${resp.url()}`)
    }
  })

  const result = {
    pass: false,
    beforeCount: 0,
    afterCount: 0,
    runtimeErrorBoundary: false,
    modalOpened: false,
    uploadTriggered: false,
    directProcessClicked: false,
    consoleErrors,
    pageErrors,
    networkErrors,
    screenshots: Object.values(screenshots),
  }

  try {
    console.log('[QA] 打开页面...')
    result.beforeCount = await fetchTaskCount()

    // 对 Vite dev server 使用 load，避免 networkidle 因 HMR 保持连接。
    await page.goto(BASE_URL, { waitUntil: 'load' })
    await page.waitForTimeout(2000)
    await page.screenshot({ path: screenshots.initial, fullPage: true })

    const bodyText = await page.locator('body').innerText()
    result.runtimeErrorBoundary = bodyText.includes('页面发生运行时错误')
    if (result.runtimeErrorBoundary) {
      throw new Error('页面进入运行时错误边界')
    }

    console.log('[QA] 打开添加来源弹窗...')
    await page.getByRole('button', { name: /添加来源/ }).click()
    await page.waitForSelector('div[role="dialog"]', { timeout: 10000 })
    result.modalOpened = true
    await page.screenshot({ path: screenshots.modal, fullPage: true })

    console.log('[QA] 通过弹窗上传视频...')
    const fileInput = page.locator('div[role="dialog"] input[type="file"]')
    await fileInput.setInputFiles(VIDEO_PATH, { timeout: 20000 })
    result.uploadTriggered = true

    result.afterCount = await waitForTaskCountIncrease(result.beforeCount, 60000)
    await page.waitForTimeout(2000)
    await page.screenshot({ path: screenshots.afterUpload, fullPage: true })

    const processButton = page.getByRole('button', { name: '直接处理' }).first()
    if (await processButton.count()) {
      await processButton.click()
      result.directProcessClicked = true
      await page.waitForTimeout(1500)
    }

    await page.screenshot({ path: screenshots.final, fullPage: true })

    result.pass =
      result.modalOpened &&
      result.uploadTriggered &&
      result.afterCount > result.beforeCount &&
      !result.runtimeErrorBoundary &&
      result.consoleErrors.length === 0 &&
      result.pageErrors.length === 0
  } catch (error) {
    result.error = String(error)
  } finally {
    await browser.close()
  }

  console.log(JSON.stringify(result, null, 2))
  if (!result.pass) {
    process.exit(1)
  }
}

run().catch((err) => {
  console.error(err)
  process.exit(1)
})
