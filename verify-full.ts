import { chromium } from 'playwright';

interface TestResult {
  name: string;
  status: 'PASS' | 'FAIL' | 'WARN';
  message: string;
}

const results: TestResult[] = [];

function log(name: string, status: TestResult['status'], message: string) {
  results.push({ name, status, message });
  const icon = status === 'PASS' ? '✅' : status === 'FAIL' ? '❌' : '⚠️';
  console.log(`${icon} ${name}: ${message}`);
}

async function runTests() {
  const browser = await chromium.launch({ headless: false });
  const page = await browser.newContext().then(ctx => ctx.newPage());

  // 收集控制台错误
  const consoleErrors: string[] = [];
  page.on('console', msg => {
    if (msg.type() === 'error') consoleErrors.push(msg.text());
  });

  // 收集网络错误
  const networkErrors: string[] = [];
  page.on('response', response => {
    if (response.status() >= 400) {
      networkErrors.push(`${response.url()} → ${response.status()}`);
    }
  });

  try {
    console.log('\n=== SmartCut 功能验证 ===\n');

    // 测试 1: 页面加载
    log('页面加载', 'RUNNING', '使用 load 事件等待');
    await page.goto('http://localhost:5173', { waitUntil: 'load' });
    log('页面加载', 'PASS', 'load 事件触发');

    // 测试 2: 上传区域
    log('上传区域', 'RUNNING', '检查文件输入');
    await page.waitForSelector('input[type="file"]', { timeout: 5000 });
    log('上传区域', 'PASS', '文件输入存在');

    // 测试 3: API 连接
    log('API 连接', 'RUNNING', '测试后端通信');
    const apiTest = await page.evaluate(async () => {
      try {
        const response = await fetch('http://localhost:8000/api/tasks');
        const data = await response.json();
        return { success: true, count: data.length };
      } catch (error) {
        return { success: false, error: String(error) };
      }
    });
    if (apiTest.success) {
      log('API 连接', 'PASS', `获取到 ${apiTest.count} 个任务`);
    } else {
      log('API 连接', 'FAIL', apiTest.error || '未知错误');
    }

    // 测试 4: 任务列表渲染
    log('任务列表', 'RUNNING', '检查任务卡片');
    const taskCount = await page.locator('[class*="task"], [data-testid="task-card"]').count();
    log('任务列表', taskCount > 0 ? 'PASS' : 'WARN', `显示 ${taskCount} 个任务`);

    // 测试 5: Timeline Modal（如果有已完成任务）
    if (taskCount > 0) {
      log('Timeline Modal', 'RUNNING', '尝试打开 Modal');
      const viewButton = page.locator('button:has-text("查看结果"), button:has-text("View")').first();

      if (await viewButton.count() > 0) {
        await viewButton.click();
        await page.waitForTimeout(1000);

        const modal = page.locator('[class*="modal"], [role="dialog"]').first();
        if (await modal.count() > 0) {
          log('Timeline Modal', 'PASS', 'Modal 已打开');

          // 检查场景显示
          const scenes = page.locator('[class*="scene"]').count();
          log('场景显示', scenes > 0 ? 'PASS' : 'WARN', `显示 ${scenes} 个场景`);

          // 关闭 Modal
          const closeButton = page.locator('button[aria-label="Close"], button:has-text("关闭")').first();
          if (await closeButton.count() > 0) {
            await closeButton.click();
            await page.waitForTimeout(500);
          }
        } else {
          log('Timeline Modal', 'FAIL', 'Modal 未打开');
        }
      } else {
        log('Timeline Modal', 'SKIP', '没有可查看的结果');
      }
    }

    // 测试 6: 静态资源访问
    log('静态资源', 'RUNNING', '测试缩略图访问');
    const staticTest = await page.evaluate(async () => {
      try {
        const response = await fetch('http://localhost:8000/data/tasks/f9272ab5-85aa-42e5-9417-75a6bdcfd852/scenes/scene_000_thumb.jpg');
        return { success: response.ok, status: response.status };
      } catch {
        return { success: false, status: 0 };
      }
    });
    if (staticTest.success) {
      log('静态资源', 'PASS', '缩略图可访问');
    } else {
      log('静态资源', 'FAIL', `HTTP ${staticTest.status}`);
    }

    // 最终截图
    await page.screenshot({ path: 'test-results/verify-final.png', fullPage: true });

  } catch (error) {
    log('测试执行', 'ERROR', error instanceof Error ? error.message : String(error));
  } finally {
    await browser.close();
  }

  // 报告
  console.log('\n=== 测试结果 ===');
  console.log(`总计: ${results.length}`);
  console.log(`通过: ${results.filter(r => r.status === 'PASS').length}`);
  console.log(`警告: ${results.filter(r => r.status === 'WARN').length}`);
  console.log(`失败: ${results.filter(r => r.status === 'FAIL').length}`);

  if (consoleErrors.length > 0) {
    console.log(`\n⚠️  控制台错误 (${consoleErrors.length}):`);
    consoleErrors.slice(0, 5).forEach(e => console.log(`   - ${e}`));
  }

  if (networkErrors.length > 0) {
    console.log(`\n⚠️  网络错误 (${networkErrors.length}):`);
    networkErrors.slice(0, 5).forEach(e => console.log(`   - ${e}`));
  }

  return results;
}

runTests().then(results => {
  const hasFailures = results.some(r => r.status === 'FAIL');
  process.exit(hasFailures ? 1 : 0);
}).catch(err => {
  console.error('Fatal error:', err);
  process.exit(1);
});
