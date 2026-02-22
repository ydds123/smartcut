import { chromium, Browser, Page, BrowserContext } from 'playwright';

const TEST_VIDEO = '/Users/apple/Documents/Claude Code/01_项目/短片拉片工具/smartcut/backend/data/uploads/f9272ab5-85aa-42e5-9417-75a6bdcfd852_黑色环保动画短片《转折点》，当人类成为濒危动物时，世界会怎样？.mp4';

interface TestResult {
  name: string;
  status: 'PASS' | 'FAIL' | 'WARN' | 'SKIP';
  message: string;
  timestamp: string;
}

const results: TestResult[] = [];

function log(name: string, status: TestResult['status'], message: string) {
  const result: TestResult = { name, status, message, timestamp: new Date().toISOString() };
  results.push(result);
  console.log(`[${status}] ${name}: ${message}`);
}

async function sleep(ms: number) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

async function runTests() {
  let browser: Browser | null = null;
  let context: BrowserContext | null = null;
  let page: Page | null = null;

  try {
    console.log('\n=== SmartCut E2E 测试开始 ===\n');

    browser = await chromium.launch({ headless: false });
    context = await browser.newContext({ viewport: { width: 1920, height: 1080 } });
    page = await context.newPage();

    // 监控错误
    page.on('console', msg => {
      if (msg.type() === 'error') {
        console.log(`🔴 Console: ${msg.text()}`);
      }
    });

    page.on('response', response => {
      if (response.status() >= 400) {
        console.log(`❌ Request: ${response.url()} → ${response.status()}`);
      }
    });

    // === 测试 1: 首页加载 ===
    log('首页加载', 'RUNNING', '导航到首页');
    await page.goto('http://localhost:5173', { waitUntil: 'networkidle' });
    await page.screenshot({ path: 'test-results/01-homepage.png' });
    log('首页加载', 'PASS', '首页加载成功');

    // === 测试 2: 检查上传区域 ===
    log('上传区域检查', 'RUNNING', '查找上传元素');
    const fileInput = page.locator('input[type="file"]');
    if (await fileInput.count() > 0) {
      log('上传区域检查', 'PASS', '上传区域存在');
    } else {
      log('上传区域检查', 'FAIL', '未找到上传区域');
    }

    // === 测试 3: 上传视频 ===
    log('视频上传', 'RUNNING', '上传测试视频');
    await fileInput.setInputFiles(TEST_VIDEO);
    await sleep(3000);
    await page.screenshot({ path: 'test-results/02-after-upload.png' });

    // 检查 Toast
    const toast = page.locator('[class*="toast"]').first();
    if (await toast.count() > 0) {
      log('Toast 通知', 'PASS', '上传后 Toast 显示');
    } else {
      log('Toast 通知', 'WARN', '未检测到 Toast');
    }

    // === 测试 4: 开始处理任务 ===
    log('任务处理', 'RUNNING', '点击开始处理');
    const startButton = page.locator('button:has-text("开始处理"), button:has-text("Start")').first();

    if (await startButton.count() > 0) {
      await startButton.click();
      log('任务处理', 'PASS', '已点击开始处理');

      // 等待处理完成
      console.log('等待处理完成（最长5分钟）...');
      for (let i = 0; i < 60; i++) {
        await sleep(5000);
        const statusText = await page.locator('[class*="status"], [class*="badge"]').first().textContent();

        if (statusText && (
          statusText.includes('完成') ||
          statusText.includes('COMPLETED') ||
          statusText.includes('SUCCESS')
        )) {
          log('任务处理完成', 'PASS', `处理完成，耗时: ${i * 5}秒`);
          break;
        }

        if (i % 6 === 0) {
          console.log(`处理中... ${i * 5}秒, 状态: ${statusText || '未知'}`);
        }
      }

      await page.screenshot({ path: 'test-results/03-after-processing.png' });
    } else {
      log('任务处理', 'SKIP', '未找到开始处理按钮（任务可能已完成）');
    }

    // === 测试 5: Timeline Modal ===
    log('Timeline Modal', 'RUNNING', '打开结果查看弹窗');
    const resultButton = page.locator('button:has-text("查看结果"), button:has-text("View"), button:has-text("Timeline")').first();

    if (await resultButton.count() > 0) {
      await resultButton.click();
      await sleep(2000);
      await page.screenshot({ path: 'test-results/04-timeline-modal.png' });
      log('Timeline Modal', 'PASS', 'Modal 已打开');

      // === 测试 6: 缩略图加载 ===
      log('缩略图加载', 'RUNNING', '检查图片加载状态');
      const images = await page.locator('img').all();
      let loaded = 0, broken = 0;

      for (const img of images) {
        const src = await img.getAttribute('src');
        const naturalWidth = await img.evaluate(el => el.naturalWidth);

        if (naturalWidth > 0) {
          loaded++;
        } else if (src && src.includes('localhost:8000')) {
          broken++;
          console.log(`❌ 缩略图失败: ${src}`);
        }
      }

      log('缩略图加载', broken === 0 ? 'PASS' : 'FAIL', `已加载: ${loaded}, 失败: ${broken}`);

      if (broken > 0) {
        log('缩略图问题', 'FAIL', `检测到 ${broken} 个失败的缩略图`);
      }

      // 检查 Modal z-index
      const modal = page.locator('[class*="modal"], [role="dialog"]').first();
      if (await modal.count() > 0) {
        const zIndex = await modal.evaluate(el => window.getComputedStyle(el).zIndex);
        console.log(`Modal z-index: ${zIndex}`);
      }

      // 关闭 Modal
      const closeButton = page.locator('button[aria-label="Close"], button:has-text("关闭"), button:has-text("Close")').first();
      if (await closeButton.count() > 0) {
        await closeButton.click();
        await sleep(500);
      }
    } else {
      log('Timeline Modal', 'SKIP', '未找到查看结果按钮');
    }

    // === 测试 7: Toast 样式检查 ===
    log('Toast 样式', 'RUNNING', '检查 Toast 元素和 z-index');
    const toasts = await page.locator('[class*="toast"], [role="alert"]').all();

    if (toasts.length > 0) {
      for (let i = 0; i < toasts.length; i++) {
        const toast = toasts[i];
        const zIndex = await toast.evaluate(el => window.getComputedStyle(el).zIndex);
        const position = await toast.evaluate(el => window.getComputedStyle(el).position);

        console.log(`Toast ${i + 1}: z-index=${zIndex}, position=${position}`);

        if (parseInt(zIndex) < 9999) {
          log(`Toast ${i + 1} z-index`, 'WARN', `z-index 过低: ${zIndex}`);
        }
      }
      log('Toast 样式', 'PASS', `检查了 ${toasts.length} 个 Toast`);
    } else {
      log('Toast 样式', 'WARN', '未找到 Toast 元素');
    }

    // 最终截图
    await page.screenshot({ path: 'test-results/05-final.png', fullPage: true });

  } catch (error) {
    log('测试执行', 'ERROR', error instanceof Error ? error.message : String(error));
  } finally {
    if (page) await page.close();
    if (context) await context.close();
    if (browser) await browser.close();
  }

  return results;
}

// 运行测试
runTests().then(results => {
  const fs = require('fs');
  fs.mkdirSync('test-results', { recursive: true });
  fs.writeFileSync('test-results/results.json', JSON.stringify(results, null, 2));

  console.log('\n=== 测试结果 ===');
  console.log(`总计: ${results.length}`);
  console.log(`通过: ${results.filter(r => r.status === 'PASS').length}`);
  console.log(`失败: ${results.filter(r => r.status === 'FAIL').length}`);
  console.log(`警告: ${results.filter(r => r.status === 'WARN').length}`);
  console.log(`跳过: ${results.filter(r => r.status === 'SKIP').length}`);

  const issues = results.filter(r => r.status === 'FAIL');
  if (issues.length > 0) {
    console.log('\n⚠️ 发现的问题:');
    issues.forEach(i => console.log(`  - ${i.name}: ${i.message}`));
  }
}).catch(err => {
  console.error('Fatal error:', err);
  process.exit(1);
});
