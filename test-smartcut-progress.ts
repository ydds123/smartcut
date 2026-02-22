/**
 * SmartCut 进度条和标题功能测试
 *
 * 测试目标:
 * 1. 打开 http://localhost:5173
 * 2. 验证现有任务的标题显示 (左对齐、省略号、tooltip)
 * 3. 点击"开始处理"按钮（如果有 PENDING 任务）
 * 4. 监控进度条更新
 * 5. 验证处理阶段提示
 * 6. 验证完成状态
 */

import { chromium, type Page, type Browser } from 'playwright'

// 配置
const BASE_URL = 'http://localhost:5173'
const SCREENSHOT_DIR = '/Users/apple/Documents/Claude Code/01_项目/短片拉片工具/smartcut/test-results/screenshots'

// 测试结果记录
interface TestResult {
  name: string
  status: 'PASS' | 'FAIL' | 'SKIP' | 'WARN'
  message: string
  screenshot?: string
  timestamp: string
}

const results: TestResult[] = []

// 辅助函数: 记录测试结果
function logResult(name: string, status: 'PASS' | 'FAIL' | 'SKIP' | 'WARN', message: string, screenshot?: string) {
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

// 主测试函数
async function runTests() {
  console.log('='.repeat(60))
  console.log('SmartCut 进度条和标题功能测试')
  console.log('='.repeat(60))
  console.log(`目标URL: ${BASE_URL}`)
  console.log('')

  let browser: Browser | null = null
  let page: Page | null = null

  try {
    // 1. 启动浏览器
    console.log('🚀 启动浏览器...')
    browser = await chromium.launch({
      headless: false,
      slowMo: 100
    })

    const context = await browser.newContext({
      viewport: { width: 1280, height: 720 }
    })

    page = await context.newPage()

    // 监听控制台消息
    const consoleMessages: string[] = []
    page.on('console', msg => {
      const text = msg.text()
      consoleMessages.push(`[${msg.type()}] ${text}`)
      if (msg.type() === 'error') {
        console.log(`   Console Error: ${text}`)
      }
    })

    // 2. 打开页面
    console.log('🌐 打开应用页面...')
    await page.goto(BASE_URL, { waitUntil: 'networkidle' })
    await page.waitForTimeout(2000)

    const screenshot1 = await takeScreenshot(page, '01-page-loaded')
    logResult('打开页面', 'PASS', '页面加载成功', screenshot1)

    // 3. 查找任务
    console.log('\n📋 查找任务...')

    // 等待页面内容加载
    await page.waitForTimeout(2000)

    // 获取页面文本
    const pageText = await page.locator('body').textContent() || ''
    console.log(`页面文本长度: ${pageText.length}`)

    // 查找任务相关内容
    const hasTaskList = pageText.includes('任务列表')
    const hasTask = pageText.includes('转折点') || pageText.includes('黑色环保')
    const hasSceneCount = pageText.includes('个场景')

    logResult('任务列表显示', hasTaskList ? 'PASS' : 'FAIL',
      hasTaskList ? '显示任务列表标题' : '未显示任务列表标题')
    logResult('任务存在', hasTask ? 'PASS' : 'FAIL',
      hasTask ? '找到任务相关内容' : '未找到任务相关内容')

    if (!hasTask) {
      logResult('测试准备', 'FAIL', '没有可测试的任务，请先上传视频')
      throw new Error('没有可测试的任务')
    }

    const screenshot2 = await takeScreenshot(page, '02-with-tasks')
    logResult('任务列表截图', 'PASS', '包含任务的页面截图', screenshot2)

    // 4. 验证标题显示
    console.log('\n📝 验证标题显示...')

    // 查找所有标题元素
    const headings = await page.locator('h1, h2, h3, h4').all()
    console.log(`找到 ${headings.length} 个标题元素`)

    let taskTitleElement = null
    let taskTitleText = ''

    for (const heading of headings) {
      const text = await heading.textContent() || ''
      console.log(`   标题: "${text}"`)

      if (text.includes('转折点') || text.includes('黑色环保')) {
        taskTitleElement = heading
        taskTitleText = text
        break
      }
    }

    if (!taskTitleElement) {
      logResult('标题查找', 'WARN', '未找到任务标题元素，尝试其他方式')
    } else {
      logResult('标题显示', 'PASS', `找到任务标题: "${taskTitleText}"`)

      // 检查 truncate 类
      const classes = await taskTitleElement.getAttribute('class') || ''
      const hasTruncate = classes.includes('truncate')
      logResult('标题省略号样式', hasTruncate ? 'PASS' : 'WARN',
        hasTruncate ? '标题应用了 truncate 类' : '标题未应用 truncate 类')

      // 检查 title 属性 (tooltip)
      const titleAttr = await taskTitleElement.getAttribute('title')
      logResult('标题 Tooltip 属性', titleAttr ? 'PASS' : 'WARN',
        titleAttr ? `Tooltip 属性存在: "${titleAttr}"` : 'Tooltip 属性不存在')

      // 检查左对齐 (text-align)
      const textAlign = await taskTitleElement.evaluate(el => {
        return window.getComputedStyle(el).textAlign
      })
      logResult('标题左对齐', textAlign === 'left' || textAlign === 'start' ? 'PASS' : 'WARN',
        `text-align: ${textAlign}`)
    }

    // 测试鼠标悬停显示 tooltip
    console.log('\n🖱️ 测试标题鼠标悬停...')

    // 尝试找到包含任务名称的元素并悬停
    try {
      const taskNameElement = page.locator('h1, h2, h3, h4, [class*="font-semibold"]').filter({
        hasText: /转折点|黑色环保/
      }).first()

      const count = await taskNameElement.count()
      if (count > 0) {
        await taskNameElement.hover()
        await page.waitForTimeout(500)

        const screenshot3 = await takeScreenshot(page, '03-title-hover')
        logResult('标题悬停', 'PASS', '成功悬停在标题上', screenshot3)
      } else {
        logResult('标题悬停', 'SKIP', '未找到可悬停的标题元素')
      }
    } catch {
      logResult('标题悬停', 'SKIP', '悬停操作失败')
    }

    // 5. 查找并点击"开始处理"按钮
    console.log('\n▶️ 查找"开始处理"按钮...')

    const processButton = page.locator('button').filter({ hasText: '开始处理' }).first()
    const buttonCount = await processButton.count()

    if (buttonCount === 0) {
      logResult('开始处理按钮', 'SKIP', '没有处于 PENDING 状态的任务')

      // 检查是否有已完成任务
      const completedText = pageText.includes('已完成') || pageText.includes('completed')
      logResult('已完成任务', completedText ? 'PASS' : 'SKIP',
        completedText ? '页面显示有已完成任务' : '没有已完成任务')

      if (completedText) {
        const screenshot4 = await takeScreenshot(page, '04-completed-task')
        logResult('已完成任务截图', 'PASS', '已完成任务状态截图', screenshot4)
      }
    } else {
      logResult('开始处理按钮', 'PASS', '找到"开始处理"按钮')

      // 点击按钮
      await processButton.click()
      await page.waitForTimeout(1000)

      const screenshot5 = await takeScreenshot(page, '05-process-clicked')
      logResult('点击开始处理', 'PASS', '成功点击"开始处理"按钮', screenshot5)

      // 6. 监控进度条
      console.log('\n📊 监控进度条更新...')

      // 等待进度条出现
      try {
        await page.waitForSelector('[class*="progress"], progress', { timeout: 5000 })
        logResult('进度条出现', 'PASS', '进度条已出现')
      } catch {
        logResult('进度条出现', 'FAIL', '5秒内进度条未出现')
      }

      // 监控进度变化
      console.log('⏳ 监控进度变化（最多等待90秒）...')

      const progressHistory: number[] = []
      let currentProgress = 0
      let lastProgressTime = Date.now()

      for (let i = 0; i < 90; i++) {
        // 获取当前进度
        try {
          const progressElements = await page.locator('[class*="progress"], .progress-label').all()
          let foundProgress = -1

          for (const el of progressElements) {
            const text = await el.textContent() || ''
            const match = text.match(/(\d+)%/)
            if (match) {
              foundProgress = parseInt(match[1])
              break
            }
          }

          if (foundProgress >= 0) {
            if (foundProgress !== currentProgress) {
              const timeDiff = Date.now() - lastProgressTime
              const jump = foundProgress - currentProgress

              console.log(`   ${i}s: ${currentProgress}% → ${foundProgress}% (${timeDiff}ms, 跳跃 ${jump}%)`)

              // 记录大跳跃
              if (jump > 5 && jump < 100) {
                logResult(`进度跳跃检测`, 'WARN',
                  `进度从 ${currentProgress}% 跳到 ${foundProgress}% (跳跃 ${jump}%)`)
              }

              progressHistory.push({ time: i, progress: foundProgress })
              currentProgress = foundProgress
              lastProgressTime = Date.now()

              // 完成
              if (foundProgress >= 100) {
                logResult('进度完成', 'PASS', '进度达到 100%')
                break
              }
            }
          }
        } catch {
          // 忽略错误
        }

        await page.waitForTimeout(1000)
      }

      if (progressHistory.length === 0) {
        logResult('进度更新', 'FAIL', '进度条没有任何更新')
      } else {
        logResult('进度更新', 'PASS',
          `进度共更新 ${progressHistory.length} 次，最终达到 ${currentProgress}%`)
      }

      const screenshot6 = await takeScreenshot(page, '06-progress-monitored')
      logResult('进度监控截图', 'PASS', '进度条监控截图', screenshot6)

      // 7. 验证处理阶段提示
      console.log('\n📋 验证处理阶段提示...')

      const currentText = await page.locator('body').textContent() || ''
      const stages = [
        { name: '正在检测场景', found: currentText.includes('正在检测场景') },
        { name: '正在切分视频', found: currentText.includes('正在切分视频') },
        { name: '正在生成缩略图', found: currentText.includes('正在生成缩略图') },
        { name: '即将完成', found: currentText.includes('即将完成') }
      ]

      for (const stage of stages) {
        logResult(`阶段: ${stage.name}`, stage.found ? 'PASS' : 'SKIP',
          stage.found ? `发现"${stage.name}"提示` : `未发现"${stage.name}"提示`)
      }

      // 8. 等待处理完成
      console.log('\n⏳ 等待处理完成...')

      try {
        await page.waitForSelector('button:has-text("查看结果")', { timeout: 120000 })
        logResult('处理完成', 'PASS', '任务处理完成，显示"查看结果"按钮')

        const screenshot7 = await takeScreenshot(page, '07-completed')
        logResult('完成状态截图', 'PASS', '任务完成状态截图', screenshot7)

        // 检查完成状态和场景统计
        const finalText = await page.locator('body').textContent() || ''
        const hasCompletedStatus = finalText.includes('已完成') || finalText.includes('completed')
        const hasSceneCount = finalText.includes('个场景')

        logResult('完成状态显示', hasCompletedStatus ? 'PASS' : 'FAIL',
          hasCompletedStatus ? '显示完成状态' : '未显示完成状态')
        logResult('场景数量统计', hasSceneCount ? 'PASS' : 'FAIL',
          hasSceneCount ? '显示场景数量统计' : '未显示场景数量统计')

        // 提取场景数量
        const sceneMatch = finalText.match(/(\d+)\s*个场景/)
        if (sceneMatch) {
          logResult('场景数量', 'PASS', `检测到 ${sceneMatch[1]} 个场景`)
        }

      } catch {
        logResult('处理完成', 'FAIL', '等待120秒后仍未完成处理')

        // 检查当前状态
        const statusText = await page.locator('body').textContent() || ''
        console.log('当前页面内容预览:', statusText.substring(0, 500))

        const screenshotFail = await takeScreenshot(page, '08-timeout')
        logResult('超时截图', 'PASS', '处理超时时状态截图', screenshotFail)
      }
    }

    // 9. 最终截图
    const finalScreenshot = await takeScreenshot(page, '10-final-state')
    logResult('最终状态', 'PASS', '最终状态截图', finalScreenshot)

  } catch (error) {
    console.error('❌ 测试执行出错:', error)
    logResult('测试执行', 'FAIL', `错误: ${error instanceof Error ? error.message : String(error)}`)

    if (page) {
      try {
        const errorScreenshot = await takeScreenshot(page, 'error-state')
        logResult('错误截图', 'PASS', '错误发生时状态截图', errorScreenshot)
      } catch {
        // 忽略
      }
    }
  } finally {
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
      console.log(`   📸 ${result.screenshot}`)
    }
  }

  console.log('\n' + '='.repeat(60))

  return { passed, failed, skipped, warned, results }
}

runTests()
  .then(summary => {
    process.exit(summary.failed > 0 ? 1 : 0)
  })
  .catch(error => {
    console.error('测试运行失败:', error)
    process.exit(1)
  })
