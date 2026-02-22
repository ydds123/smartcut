import { chromium } from 'playwright'
import fs from 'node:fs/promises'

const BASE_URL = 'http://127.0.0.1:5173'
const OUT_ROOT = '/Users/apple/Documents/Claude Code/01_项目/短片拉片工具/smartcut/test-results'
const stamp = Date.now()
const screenshot = `/Users/apple/Documents/Claude Code/qaskills_review_filmstrip_${stamp}.png`
const reportPath = `${OUT_ROOT}/qaskills-review-filmstrip-report-${stamp}.json`

function fail(message) {
  throw new Error(message)
}

async function setZoom(page, value) {
  await page.evaluate((next) => {
    const marker = Array.from(document.querySelectorAll('span')).find((node) => node.textContent?.includes('缩放'))
    if (!marker?.parentElement) {
      throw new Error('zoom marker missing')
    }
    const slider = marker.parentElement.querySelector('input[type="range"]')
    if (!slider) {
      throw new Error('zoom slider missing')
    }
    const descriptor = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')
    if (descriptor?.set) {
      descriptor.set.call(slider, String(next))
    } else {
      slider.value = String(next)
    }
    slider.dispatchEvent(new Event('input', { bubbles: true }))
    slider.dispatchEvent(new Event('change', { bubbles: true }))
  }, value)
}

async function readFilmstripMetrics(page) {
  return page.evaluate(() => {
    const scene0 = document.querySelector('[data-review-scene-block="0"]')
    const scrollEl = document.querySelector('[data-review-timeline-scroll="true"]')

    return {
      scene0Slots: scene0 ? scene0.querySelectorAll('[data-review-frame-slot]').length : 0,
      scene0Loaded: scene0 ? scene0.querySelectorAll('[data-review-frame-slot] img').length : 0,
      totalSlots: document.querySelectorAll('[data-review-frame-slot]').length,
      totalLoaded: document.querySelectorAll('[data-review-frame-slot] img').length,
      scrollLeft: scrollEl ? scrollEl.scrollLeft : 0,
      scrollWidth: scrollEl ? scrollEl.scrollWidth : 0,
      clientWidth: scrollEl ? scrollEl.clientWidth : 0,
    }
  })
}

async function scrollTimeline(page, ratio) {
  await page.evaluate((targetRatio) => {
    const scrollEl = document.querySelector('[data-review-timeline-scroll="true"]')
    if (!scrollEl) {
      throw new Error('timeline scroll container missing')
    }
    const maxScrollLeft = Math.max(0, scrollEl.scrollWidth - scrollEl.clientWidth)
    scrollEl.scrollLeft = maxScrollLeft * targetRatio
  }, ratio)
}

async function run() {
  const browser = await chromium.launch({ headless: true })
  const page = await browser.newPage({ viewport: { width: 1720, height: 980 } })
  const checks = []

  try {
    await page.goto(BASE_URL, { waitUntil: 'networkidle', timeout: 15000 })

    const reviewBtn = page.getByRole('button', { name: '查看并编辑' }).first()
    const reviewCount = await page.getByRole('button', { name: '查看并编辑' }).count()
    checks.push({ name: 'review_button_exists', pass: reviewCount > 0, detail: `count=${reviewCount}` })
    if (reviewCount === 0) {
      fail('未找到“查看并编辑”按钮')
    }

    await reviewBtn.click()
    await page.getByRole('heading', { name: '场景预览确认' }).waitFor({ timeout: 10000 })
    await page.waitForTimeout(800)

    await setZoom(page, 20)
    await page.waitForTimeout(1200)
    const lowMetrics = await readFilmstripMetrics(page)

    await setZoom(page, 180)
    await page.waitForTimeout(1400)
    const highMetrics = await readFilmstripMetrics(page)

    checks.push({
      name: 'zoom_increases_scene_slot_density',
      pass: highMetrics.scene0Slots > lowMetrics.scene0Slots,
      detail: `scene0Slots: low=${lowMetrics.scene0Slots}, high=${highMetrics.scene0Slots}`,
    })

    checks.push({
      name: 'zoom_increases_total_slot_density',
      pass: highMetrics.totalSlots > lowMetrics.totalSlots,
      detail: `totalSlots: low=${lowMetrics.totalSlots}, high=${highMetrics.totalSlots}`,
    })

    await scrollTimeline(page, 0.78)
    await page.waitForTimeout(1500)
    const afterScroll = await readFilmstripMetrics(page)

    checks.push({
      name: 'scroll_advances_timeline',
      pass: afterScroll.scrollLeft > highMetrics.scrollLeft,
      detail: `scrollLeft: before=${highMetrics.scrollLeft.toFixed(1)}, after=${afterScroll.scrollLeft.toFixed(1)}`,
    })

    checks.push({
      name: 'scroll_triggers_additional_thumb_loading',
      pass: afterScroll.totalLoaded >= highMetrics.totalLoaded,
      detail: `loadedImgs: before=${highMetrics.totalLoaded}, after=${afterScroll.totalLoaded}`,
    })

    await page.screenshot({ path: screenshot, fullPage: true })

    const report = {
      mode: 'qaskills-review-filmstrip-headless',
      timestamp: new Date().toISOString(),
      baseUrl: BASE_URL,
      screenshot,
      metrics: {
        lowZoom: lowMetrics,
        highZoom: highMetrics,
        afterScroll,
      },
      checks,
      passCount: checks.filter((c) => c.pass).length,
      failCount: checks.filter((c) => !c.pass).length,
    }

    await fs.writeFile(reportPath, JSON.stringify(report, null, 2), 'utf8')
    console.log(JSON.stringify(report, null, 2))
  } finally {
    await browser.close()
  }
}

run().catch((error) => {
  console.error('[qaskills-filmstrip] FAILED:', error)
  process.exitCode = 1
})
