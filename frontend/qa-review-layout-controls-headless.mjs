import fs from 'node:fs/promises'
import { chromium } from 'playwright'

const UI_BASE = 'http://127.0.0.1:5173'
const OUT_DIR = '/Users/apple/Documents/Claude Code/01_项目/短片拉片工具/smartcut/test-results'
const stamp = Date.now()
const screenshotPath = `${OUT_DIR}/qa-review-layout-controls-${stamp}.png`
const reportPath = `${OUT_DIR}/qa-review-layout-controls-report-${stamp}.json`

function toNumber(value) {
  return typeof value === 'number' && Number.isFinite(value) ? value : 0
}

function nearlyEqual(a, b, tolerance = 8) {
  return Math.abs(a - b) <= tolerance
}

async function openReviewModal(page) {
  const previewButtons = page.getByRole('button', { name: /预览分镜|查看并编辑/ })
  try {
    await previewButtons.first().waitFor({ state: 'visible', timeout: 20000 })
  } catch {
    const snapshotButtons = await page.locator('button').allTextContents()
    throw new Error(
      `未找到“预览分镜/查看并编辑”按钮，无法进入审核页。当前按钮: ${snapshotButtons.join(' | ')}`
    )
  }

  await previewButtons.first().click()
  await page.getByRole('heading', { name: '分镜预览' }).waitFor({ timeout: 15000 })
}

async function closeReviewModal(page) {
  await page.getByRole('button', { name: '关闭' }).click()
  await page.waitForTimeout(250)
}

async function readLayoutMetrics(page) {
  return page.evaluate(() => {
    const scroll = document.querySelector('[data-testid="review-layout-scroll"]')
    const grid = document.querySelector('[data-testid="review-layout-grid"]')
    const left = document.querySelector('[data-testid="review-layout-left"]')
    const middle = document.querySelector('[data-testid="review-layout-middle"]')
    const right = document.querySelector('[data-testid="review-layout-right"]')

    const leftWidth = left?.getBoundingClientRect().width ?? 0
    const middleWidth = middle?.getBoundingClientRect().width ?? 0
    const rightWidth = right?.getBoundingClientRect().width ?? 0
    const scrollClientWidth = scroll instanceof HTMLElement ? scroll.clientWidth : 0
    const scrollWidth = scroll instanceof HTMLElement ? scroll.scrollWidth : 0

    const hasNarrativeTitle = Boolean(
      Array.from(document.querySelectorAll('h3')).find((node) =>
        node.textContent?.includes('叙事单元分析（规划中）')
      )
    )

    return {
      hasScrollContainer: Boolean(scroll),
      hasGrid: Boolean(grid),
      hasNarrativeTitle,
      leftWidth,
      middleWidth,
      rightWidth,
      leftToMiddleRatio: middleWidth > 0 ? leftWidth / middleWidth : 0,
      middleToRightRatio: rightWidth > 0 ? middleWidth / rightWidth : 0,
      scrollClientWidth,
      scrollWidth,
      hasHorizontalOverflow: scrollWidth - scrollClientWidth > 1,
    }
  })
}

async function dragSplitter(page, testId, deltaX) {
  const splitter = page.locator(`[data-testid="${testId}"]`)
  const count = await splitter.count()
  if (count === 0) {
    throw new Error(`未找到分割线: ${testId}`)
  }

  const box = await splitter.first().boundingBox()
  if (!box) {
    throw new Error(`无法读取分割线位置: ${testId}`)
  }

  const x = box.x + box.width / 2
  const y = box.y + Math.min(box.height / 2, 320)

  await page.mouse.move(x, y)
  await page.mouse.down()
  await page.mouse.move(x + deltaX, y, { steps: 12 })
  await page.mouse.up()
  await page.waitForTimeout(160)
}

async function readOverlayMetrics(page) {
  return page.evaluate(() => {
    const overlay = document.querySelector('div.absolute.inset-x-3.bottom-3')
    const playButton = overlay?.querySelector('button')
    const style = overlay ? getComputedStyle(overlay) : null
    const activeElementIsPlayButton = Boolean(playButton && document.activeElement === playButton)

    return {
      found: Boolean(overlay),
      opacity: style ? Number.parseFloat(style.opacity) : -1,
      pointerEvents: style?.pointerEvents ?? null,
      activeElementIsPlayButton,
    }
  })
}

async function run() {
  await fs.mkdir(OUT_DIR, { recursive: true })
  const browser = await chromium.launch({ headless: true })
  const page = await browser.newPage({ viewport: { width: 980, height: 900 } })
  const checks = []

  try {
    await page.goto(UI_BASE, { waitUntil: 'domcontentloaded', timeout: 20000 })
    await openReviewModal(page)
    await page.waitForTimeout(700)

    const hoverCapable = await page.evaluate(() =>
      window.matchMedia('(hover: hover) and (pointer: fine)').matches
    )

    const initialLayout = await readLayoutMetrics(page)
    checks.push({
      name: 'layout_grid_exists',
      pass: initialLayout.hasGrid && initialLayout.hasScrollContainer,
      detail: `hasGrid=${initialLayout.hasGrid}, hasScroll=${initialLayout.hasScrollContainer}`,
    })
    checks.push({
      name: 'three_panels_exist',
      pass: initialLayout.leftWidth > 0 && initialLayout.middleWidth > 0 && initialLayout.rightWidth > 0,
      detail: `left=${initialLayout.leftWidth.toFixed(1)}, middle=${initialLayout.middleWidth.toFixed(1)}, right=${initialLayout.rightWidth.toFixed(1)}`,
    })
    checks.push({
      name: 'narrative_placeholder_exists',
      pass: initialLayout.hasNarrativeTitle,
      detail: `hasNarrativeTitle=${initialLayout.hasNarrativeTitle}`,
    })
    checks.push({
      name: 'narrow_screen_uses_horizontal_scroll',
      pass: initialLayout.hasHorizontalOverflow,
      detail: `scrollWidth=${initialLayout.scrollWidth}, clientWidth=${initialLayout.scrollClientWidth}`,
    })
    checks.push({
      name: 'default_ratio_left_middle_about_2',
      pass: Math.abs(initialLayout.leftToMiddleRatio - 2) <= 0.35,
      detail: `left/middle=${initialLayout.leftToMiddleRatio.toFixed(3)}`,
    })
    checks.push({
      name: 'default_ratio_middle_right_about_1',
      pass: Math.abs(initialLayout.middleToRightRatio - 1) <= 0.25,
      detail: `middle/right=${initialLayout.middleToRightRatio.toFixed(3)}`,
    })

    await dragSplitter(page, 'review-layout-splitter-left-middle', 120)
    const afterLeftDrag = await readLayoutMetrics(page)
    checks.push({
      name: 'splitter1_changes_left_and_middle',
      pass: afterLeftDrag.leftWidth > initialLayout.leftWidth + 12 && afterLeftDrag.middleWidth < initialLayout.middleWidth - 12,
      detail: `left: ${initialLayout.leftWidth.toFixed(1)} -> ${afterLeftDrag.leftWidth.toFixed(1)}, middle: ${initialLayout.middleWidth.toFixed(1)} -> ${afterLeftDrag.middleWidth.toFixed(1)}`,
    })
    checks.push({
      name: 'splitter1_keeps_right_stable',
      pass: nearlyEqual(afterLeftDrag.rightWidth, initialLayout.rightWidth, 12),
      detail: `right: ${initialLayout.rightWidth.toFixed(1)} -> ${afterLeftDrag.rightWidth.toFixed(1)}`,
    })

    await dragSplitter(page, 'review-layout-splitter-middle-right', 110)
    const afterRightDrag = await readLayoutMetrics(page)
    checks.push({
      name: 'splitter2_changes_middle_and_right',
      pass: afterRightDrag.middleWidth > afterLeftDrag.middleWidth + 12 && afterRightDrag.rightWidth < afterLeftDrag.rightWidth - 12,
      detail: `middle: ${afterLeftDrag.middleWidth.toFixed(1)} -> ${afterRightDrag.middleWidth.toFixed(1)}, right: ${afterLeftDrag.rightWidth.toFixed(1)} -> ${afterRightDrag.rightWidth.toFixed(1)}`,
    })
    checks.push({
      name: 'splitter2_keeps_left_stable',
      pass: nearlyEqual(afterRightDrag.leftWidth, afterLeftDrag.leftWidth, 12),
      detail: `left: ${afterLeftDrag.leftWidth.toFixed(1)} -> ${afterRightDrag.leftWidth.toFixed(1)}`,
    })

    await closeReviewModal(page)
    await openReviewModal(page)
    await page.waitForTimeout(500)
    const reopenedLayout = await readLayoutMetrics(page)
    checks.push({
      name: 'layout_persists_after_reopen',
      pass:
        nearlyEqual(reopenedLayout.leftWidth, afterRightDrag.leftWidth, 14)
        && nearlyEqual(reopenedLayout.middleWidth, afterRightDrag.middleWidth, 14)
        && nearlyEqual(reopenedLayout.rightWidth, afterRightDrag.rightWidth, 14),
      detail: `reopen(left/mid/right)=(${reopenedLayout.leftWidth.toFixed(1)}, ${reopenedLayout.middleWidth.toFixed(1)}, ${reopenedLayout.rightWidth.toFixed(1)})`,
    })

    const initialOverlay = await readOverlayMetrics(page)
    checks.push({
      name: 'overlay_exists',
      pass: initialOverlay.found,
      detail: `found=${initialOverlay.found}`,
    })

    if (hoverCapable) {
      checks.push({
        name: 'overlay_initially_hidden_on_hover_devices',
        pass: initialOverlay.opacity <= 0.05 && initialOverlay.pointerEvents === 'none',
        detail: `opacity=${initialOverlay.opacity.toFixed(3)}, pointerEvents=${initialOverlay.pointerEvents}`,
      })
    } else {
      checks.push({
        name: 'overlay_always_visible_on_non_hover_devices',
        pass: initialOverlay.opacity >= 0.95,
        detail: `opacity=${initialOverlay.opacity.toFixed(3)}`,
      })
    }

    const video = page.locator('video')
    const videoCount = await video.count()
    if (videoCount > 0) {
      await video.first().hover()
    }
    await page.waitForTimeout(260)

    const afterHover = await readOverlayMetrics(page)
    checks.push({
      name: 'overlay_shows_on_hover',
      pass: afterHover.opacity >= 0.95,
      detail: `opacity=${afterHover.opacity.toFixed(3)}`,
    })

    await page.mouse.move(6, 6)
    await page.waitForTimeout(1200)
    const afterLeave = await readOverlayMetrics(page)
    if (hoverCapable) {
      checks.push({
        name: 'overlay_hides_after_leave_delay',
        pass: afterLeave.opacity <= 0.05 && afterLeave.pointerEvents === 'none',
        detail: `opacity=${afterLeave.opacity.toFixed(3)}, pointerEvents=${afterLeave.pointerEvents}`,
      })
    }

    await page.screenshot({ path: screenshotPath, fullPage: true })

    const report = {
      mode: 'qa-review-layout-controls-headless',
      timestamp: new Date().toISOString(),
      baseUrl: UI_BASE,
      screenshot: screenshotPath,
      environment: {
        hoverCapable,
      },
      metrics: {
        initialLayout: {
          leftWidth: toNumber(initialLayout.leftWidth),
          middleWidth: toNumber(initialLayout.middleWidth),
          rightWidth: toNumber(initialLayout.rightWidth),
          leftToMiddleRatio: toNumber(initialLayout.leftToMiddleRatio),
          middleToRightRatio: toNumber(initialLayout.middleToRightRatio),
          scrollWidth: toNumber(initialLayout.scrollWidth),
          scrollClientWidth: toNumber(initialLayout.scrollClientWidth),
        },
        persistedLayout: {
          leftWidth: toNumber(reopenedLayout.leftWidth),
          middleWidth: toNumber(reopenedLayout.middleWidth),
          rightWidth: toNumber(reopenedLayout.rightWidth),
        },
      },
      checks,
      passCount: checks.filter((item) => item.pass).length,
      failCount: checks.filter((item) => !item.pass).length,
    }

    await fs.writeFile(reportPath, JSON.stringify(report, null, 2), 'utf8')
    console.log(JSON.stringify(report, null, 2))
  } finally {
    await browser.close()
  }
}

run().catch((error) => {
  console.error('[qa-review-layout-controls] FAILED:', error)
  process.exitCode = 1
})
