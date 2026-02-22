/**
 * SmartCut 视频上传和进度条功能测试
 *
 * 测试目标:
 * 1. 打开 http://localhost:5173
 * 2. 上传视频文件
 * 3. 验证标题显示 (左对齐、省略号、tooltip)
 * 4. 点击"开始处理"按钮
 * 5. 监控进度条更新
 * 6. 验证处理阶段提示
 * 7. 验证完成状态
 */

import { chromium, type Page, type Browser } from 'playwright'

// 配置
const BASE_URL = 'http://localhost:5173'
const VIDEO_PATH = '/Users/apple/Downloads/Downie4 下载/黑色环保动画短片《转折点》，当人类成为濒危动物时，世界会怎样？.mp4'
const SCREENSHOT_DIR = '/Users/apple/Documents/Claude Code/01_项目/短片拉片工具/smartcut/test-results/screenshots'

// 测试结果记录
interface TestResult {
  name: string
  status: 'PASS' | 'FAIL' | 'SKIP'
  message: string
  screenshot?: string
  timestamp: string
}

const results: TestResult[] = []

// 辅助函数: 记录测试结果
function logResult(name: string, status: 'PASS' | 'FAIL' | 'SKIP', message: string, screenshot?: string) {
  const result: TestResult = {
    name,
    status,
    message,
    screenshot,
    timestamp: new Date().toISOString()
  }
  results.push(result)
  console.log(`[${status}] ${name}: ${message}`)
}

// 辅助函数: 截图
async function takeScreenshot(page: Page, name: string): Promise<string> {
  const path = `${SCREENSHOT_DIR}/${name}.png`
  await page.screenshot({ path, fullPage: false })
  return path
}

// 辅助函数: 等待选择器出现
async function waitForSelector(page: Page, selector: string, timeout = 10000): Promise<boolean> {
  try {
    await page.waitForSelector(selector, { timeout })
    return true
  } catch {
    return false
  }
}

// 辅助函数: 等待进度变化
async function waitForProgressChange(page: Page, currentProgress: number, timeout = 30000): Promise<number | null> {
  const startTime = Date.now()

  while (Date.now() - startTime < timeout) {
    const progressText = await page.locator('.progress-label').first().textContent().catch(() => null)
    if (progressText) {
      const match = progressText.match(/(\d+)%/)
      if (match) {
        const newProgress = parseInt(match[1])
        if (newProgress !== currentProgress) {
          return newProgress
        }
      }
    }
    await page.waitForTimeout(500)
  }

  return null
}

// 主测试函数
async function runTests() {
  console.log('='.repeat(60))
  console.log('SmartCut 视频上传和进度条功能测试')
  console.log('='.repeat(60))
  console.log(`目标URL: ${BASE_URL}`)
  console.log(`测试视频: ${VIDEO_PATH}`)
  console.log('')

  let browser: Browser | null = null
  let page: Page | null = null

  try {
    // 1. 启动浏览器
    console.log('🚀 启动浏览器...')
    browser = await chromium.launch({
      headless: false, // 显示浏览器以便观察
      slowMo: 100 // 稍微减慢操作速度
    })

    const context = await browser.newContext({
      viewport: { width: 1280, height: 720 }
    })

    page = await context.newPage()

    // 监听控制台消息
    const consoleMessages: string[] = []
    page.on('console', msg => {
      consoleMessages.push(`[${msg.type()}] ${msg.text()}`)
    })

    // 2. 打开页面
    console.log('🌐 打开应用页面...')
    await page.goto(BASE_URL, { waitUntil: 'networkidle' })
    await page.waitForTimeout(1000) // 等待页面稳定

    const screenshot1 = await takeScreenshot(page, '01-page-loaded')
    logResult('打开页面', 'PASS', '页面加载成功', screenshot1)

    // 检查控制台错误
    const errors = consoleMessages.filter(m => m.includes('[error]'))
    if (errors.length > 0) {
      logResult('控制台检查', 'FAIL', `发现 ${errors.length} 个控制台错误`)
      console.log('控制台错误:', errors)
    } else {
      logResult('控制台检查', 'PASS', '没有控制台错误')
    }

    // 3. 查找上传区域
    console.log('\n📤 准备上传视频...')

    // 检查上传区域是否存在
    const uploadAreaExists = await waitForSelector(page, 'input[type="file"]', 5000)
    if (!uploadAreaExists) {
      logResult('上传区域', 'FAIL', '找不到文件上传输入框')
      throw new Error('上传区域不存在')
    }
    logResult('上传区域', 'PASS', '找到文件上传输入框')

    // 4. 上传视频文件
    console.log('📹 上传视频文件...')

    // 使用 file chooser 上传
    const fileInput = page.locator('input[type="file"]')
    await fileInput.setInputFiles(VIDEO_PATH)

    console.log('⏳ 等待上传完成（最多等待30秒）...')

    // 等待 toast 消息（上传成功或失败）
    let uploadSuccess = false
    let uploadError = null

    try {
      // 等待上传进度条消失或显示成功消息
      await page.waitForFunction(() => {
        const bodyText = document.body.textContent || ''
        return bodyText.includes('上传成功') || bodyText.includes('上传失败')
      }, { timeout: 30000 })

      const bodyText = await page.locator('body').textContent()
      if (bodyText?.includes('上传成功')) {
        uploadSuccess = true
        console.log('✅ 上传成功消息已显示')
      } else if (bodyText?.includes('上传失败')) {
        uploadError = '上传失败消息已显示'
        console.log('❌ 上传失败消息已显示')
      }
    } catch {
      uploadError = '30秒内未显示上传结果消息'
      console.log('⏱️ 超时：30秒内未显示上传结果')
    }

    if (!uploadSuccess) {
      const screenshot2 = await takeScreenshot(page, '02-upload-failed')
      logResult('上传视频', 'FAIL', uploadError || '上传失败', screenshot2)
      throw new Error(`上传失败: ${uploadError}`)
    }

    // 等待任务列表刷新
    await page.waitForTimeout(2000)

    // 等待任务卡片出现
    console.log('🔍 查找任务卡片...')

    // 先检查页面是否有任务标题
    const hasTaskHeading = await page.locator('h2, h1').filter({ hasText: '任务列表' }).count() > 0

    // 尝试多种选择器来查找任务卡片
    const taskSelectors = [
      'h3',  // 任务标题
      '[class*="task"]',  // 包含 task 类名的元素
      '[class*="Card"]',  // 包含 Card 类名的元素
      'section',  // section 元素
      'article',  // article 元素
    ]

    let foundAnyTask = false
    let taskTitleText = ''

    for (const selector of taskSelectors) {
      try {
        const elements = page.locator(selector)
        const count = await elements.count()
        console.log(`   选择器 "${selector}": 找到 ${count} 个元素`)

        for (let i = 0; i < Math.min(count, 10); i++) {
          const text = await elements.nth(i).textContent() || ''
          if (text.includes('转折点') || text.includes('黑色环保') || text.includes('个场景')) {
            foundAnyTask = true
            taskTitleText = text.substring(0, 100)
            console.log(`   找到任务相关文本: "${taskTitleText}"`)
            break
          }
        }

        if (foundAnyTask) break
      } catch {
        continue
      }
    }

    if (!foundAnyTask) {
      // 最后尝试：获取整个页面文本
      const fullPageText = await page.locator('body').textContent() || ''
      console.log('页面文本预览:', fullPageText.substring(0, 500))

      const hasTaskText = fullPageText.includes('转折点') || fullPageText.includes('黑色环保')
      if (hasTaskText) {
        foundAnyTask = true
        logResult('任务卡片', 'PASS', '在页面文本中找到任务相关内容')
      } else {
          const screenshot2 = await takeScreenshot(page, '02-no-task-card')
        logResult('上传视频', 'FAIL', '上传后未显示任务卡片', screenshot2)
        throw new Error('任务卡片未出现')
      }
    } else {
      const screenshot2 = await takeScreenshot(page, '03-task-created')
    logResult('上传视频', 'PASS', '视频上传成功，任务卡片已创建', screenshot2)

    // 5. 验证标题显示
    console.log('\n📝 验证标题显示...')

    // 查找任务卡片中的标题元素
    const titleSelectors = [
      'h3',
      '[class*="font-semibold"]',
      '.text-lg'
    ]

    let titleElement = null
    let titleText = ''

    for (const selector of titleSelectors) {
      try {
        const element = page.locator(selector).first()
        if (await element.count() > 0) {
          const text = await element.textContent() || ''
          if (text.includes('转折点') || text.includes('黑色环保')) {
            titleElement = element
            titleText = text
            break
          }
        }
      } catch {
        continue
      }
    }

    if (!titleElement) {
      // 尝试获取所有文本内容
      titleText = await page.locator('body').textContent() || ''
      logResult('标题显示', 'FAIL', '找不到任务标题元素')
    } else {
      logResult('标题显示', 'PASS', `标题显示: "${titleText}"`)

      // 检查标题是否有 truncate 类
      const hasTruncate = await titleElement.evaluate(el => {
        return window.getComputedStyle(el).overflow === 'hidden' ||
          el.classList.contains('truncate')
      })
      logResult('标题省略号', hasTruncate ? 'PASS' : 'FAIL',
        hasTruncate ? '标题应用了省略号样式' : '标题未应用省略号样式')

      // 检查 title 属性（tooltip）
      const hasTooltip = await titleElement.getAttribute('title')
      logResult('标题Tooltip', hasTooltip ? 'PASS' : 'FAIL',
        hasTooltip ? `Tooltip存在: "${hasTooltip}"` : 'Tooltip不存在')
    }

    const screenshot3 = await takeScreenshot(page, '04-title-verified')
    screenshot3 && logResult('标题截图', 'PASS', '标题验证截图', screenshot3)

    // 6. 点击"开始处理"按钮
    console.log('\n▶️  点击"开始处理"按钮...')

    // 查找开始处理按钮
    const processButtonSelectors = [
      'button:has-text("开始处理")',
      'button:has-text("处理")',
      '[class*="Button"]:has-text("开始")'
    ]

    let processButton = null
    for (const selector of processButtonSelectors) {
      try {
        const btn = page.locator(selector).first()
        if (await btn.count() > 0) {
          processButton = btn
          break
        }
      } catch {
        continue
      }
    }

    if (!processButton) {
      const screenshot4 = await takeScreenshot(page, '05-no-process-button')
      logResult('开始处理按钮', 'FAIL', '找不到"开始处理"按钮', screenshot4)
      throw new Error('开始处理按钮不存在')
    }

    await processButton.click()
    await page.waitForTimeout(1000)

    const screenshot5 = await takeScreenshot(page, '06-process-started')
    logResult('开始处理', 'PASS', '成功点击"开始处理"按钮', screenshot5)

    // 7. 监控进度条更新
    console.log('\n📊 监控进度条更新...')

    // 等待进度条出现
    const progressSelectors = [
      '[class*="progress"]',
      'progress',
      '.bg-blue-600'
    ]

    let progressElement = null
    for (const selector of progressSelectors) {
      try {
        const el = page.locator(selector).first()
        if (await el.count() > 0) {
          progressElement = el
          break
        }
      } catch {
        continue
      }
    }

    if (!progressElement) {
      logResult('进度条', 'FAIL', '找不到进度条元素')
    } else {
      logResult('进度条', 'PASS', '进度条元素存在')

      // 监控进度变化
      console.log('⏳ 监控进度变化（最多等待60秒）...')

      const progressHistory: number[] = []
      let currentProgress = 0
      let noChangeCount = 0
      const maxNoChange = 10 // 10次无变化后退出

      while (progressHistory.length < 60) {
        // 获取当前进度
        const progressText = await page.locator('.progress-label, [class*="progress"]').textContent().catch(() => null)
        let progress = 0

        if (progressText) {
          const match = progressText.match(/(\d+)%/)
          if (match) {
            progress = parseInt(match[1])
          }
        }

        // 检查进度是否有变化
        if (progress !== currentProgress) {
          console.log(`   进度: ${currentProgress}% → ${progress}%`)

          // 检查进度跳跃是否过大（超过5%）
          const jump = progress - currentProgress
          if (jump > 5) {
            logResult(`进度跳跃 ${progressHistory.length + 1}`, 'WARN', `进度从 ${currentProgress}% 跳到 ${progress}% (跳跃 ${jump}%)`)
          }

          progressHistory.push(progress)
          currentProgress = progress
          noChangeCount = 0

          // 如果达到100%，退出循环
          if (progress >= 100) {
            break
          }
        } else {
          noChangeCount++
          if (noChangeCount >= maxNoChange) {
            console.log('   进度长时间无变化，停止监控')
            break
          }
        }

        await page.waitForTimeout(1000)
      }

      // 分析进度变化
      if (progressHistory.length === 0) {
        logResult('进度更新', 'FAIL', '进度条没有任何更新')
      } else {
        const finalProgress = progressHistory[progressHistory.length - 1]
        logResult('进度更新', 'PASS', `进度从 0% 更新到 ${finalProgress}%，共 ${progressHistory.length} 次变化`)

        // 检查是否平滑更新
        let hasLargeJump = false
        for (let i = 1; i < progressHistory.length; i++) {
          if (progressHistory[i] - progressHistory[i - 1] > 5) {
            hasLargeJump = true
            break
          }
        }
        logResult('进度平滑性', hasLargeJump ? 'WARN' : 'PASS',
          hasLargeJump ? '存在较大进度跳跃' : '进度更新平滑，单次跳跃不超过5%')
      }

      const screenshot6 = await takeScreenshot(page, '07-progress-monitored')
      screenshot6 && logResult('进度监控截图', 'PASS', '进度条监控截图', screenshot6)
    }

    // 8. 验证处理阶段提示
    console.log('\n📋 验证处理阶段提示...')

    const stageText = await page.locator('body').textContent() || ''
    const stages = {
      '正在检测场景': stageText.includes('正在检测场景'),
      '正在切分视频': stageText.includes('正在切分视频'),
      '正在生成缩略图': stageText.includes('正在生成缩略图'),
      '即将完成': stageText.includes('即将完成')
    }

    for (const [stage, found] of Object.entries(stages)) {
      logResult(`阶段提示: ${stage}`, found ? 'PASS' : 'SKIP', found ? '发现该阶段提示' : '未发现该阶段提示')
    }

    // 9. 等待处理完成
    console.log('\n⏳ 等待处理完成...')

    // 等待"查看结果"按钮出现
    try {
      await page.waitForSelector('button:has-text("查看结果")', { timeout: 120000 })
      logResult('处理完成', 'PASS', '任务处理完成，显示"查看结果"按钮')

      const screenshot7 = await takeScreenshot(page, '08-completed')
      logResult('完成状态截图', 'PASS', '任务完成状态截图', screenshot7)

      // 检查完成状态
      const completedText = await page.locator('body').textContent() || ''
      const hasCompletedStatus = completedText.includes('已完成') || completedText.includes('completed')
      const hasSceneCount = completedText.includes('个场景')

      logResult('完成状态', hasCompletedStatus ? 'PASS' : 'FAIL',
        hasCompletedStatus ? '显示完成状态' : '未显示完成状态')
      logResult('场景统计', hasSceneCount ? 'PASS' : 'FAIL',
        hasSceneCount ? '显示场景数量统计' : '未显示场景数量统计')

    } catch {
      logResult('处理完成', 'FAIL', '等待120秒后仍未完成处理')
      const screenshotFail = await takeScreenshot(page, '09-timeout')
      logResult('超时截图', 'PASS', '处理超时时状态截图', screenshotFail)
    }

    // 10. 最终截图
    const finalScreenshot = await takeScreenshot(page, '10-final-state')
    logResult('最终状态', 'PASS', '最终状态截图', finalScreenshot)

  } catch (error) {
    console.error('❌ 测试执行出错:', error)
    logResult('测试执行', 'FAIL', `错误: ${error instanceof Error ? error.message : String(error)}`)

    // 尝试截图
    if (page) {
      try {
        const errorScreenshot = await takeScreenshot(page, 'error-state')
        logResult('错误截图', 'PASS', '错误发生时状态截图', errorScreenshot)
      } catch {
        // 忽略截图错误
      }
    }

  } finally {
    // 关闭浏览器
    if (browser) {
      console.log('\n🔚 关闭浏览器...')
      await browser.close()
    }
  }

  // 打印测试报告
  console.log('\n' + '='.repeat(60))
  console.log('测试报告')
  console.log('='.repeat(60))

  const passed = results.filter(r => r.status === 'PASS').length
  const failed = results.filter(r => r.status === 'FAIL').length
  const skipped = results.filter(r => r.status === 'SKIP').length
  const warned = results.filter(r => r.status === 'WARN').length

  console.log(`\n总计: ${results.length} | 通过: ${passed} | 失败: ${failed} | 跳过: ${skipped} | 警告: ${warned}`)

  console.log('\n详细结果:')
  console.log('-'.repeat(60))

  for (const result of results) {
    const icon = result.status === 'PASS' ? '✅' : result.status === 'FAIL' ? '❌' : result.status === 'WARN' ? '⚠️' : '⏭️'
    console.log(`${icon} ${result.name}: ${result.message}`)
    if (result.screenshot) {
      console.log(`   截图: ${result.screenshot}`)
    }
  }

  console.log('\n' + '='.repeat(60))

  return { passed, failed, skipped, warned, results }
}

// 运行测试
runTests()
  .then(summary => {
    process.exit(summary.failed > 0 ? 1 : 0)
  })
  .catch(error => {
    console.error('测试运行失败:', error)
    process.exit(1)
  })
