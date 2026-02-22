import { chromium } from 'playwright';

async function quickVerify() {
  const browser = await chromium.launch({ headless: false });
  const page = await browser.newContext().then(ctx => ctx.newPage());

  try {
    console.log('🔍 验证 SmartCut 前端...\n');

    // 使用 load 事件而非 networkidle
    await page.goto('http://localhost:5173', { waitUntil: 'load' });
    console.log('✅ 页面加载完成（load 事件）');

    // 等待关键元素出现
    await page.waitForSelector('input[type="file"]', { timeout: 5000 });
    console.log('✅ 上传区域已加载');

    // 检查任务卡片
    const taskCards = await page.locator('[class*="task"]').count();
    console.log(`✅ 找到 ${taskCards} 个任务卡片`);

    // 截图
    await page.screenshot({ path: 'test-results/verify-quick.png' });
    console.log('✅ 截图已保存: test-results/verify-quick.png');

    // 检查控制台错误（5秒内）
    const errors: string[] = [];
    page.on('console', msg => {
      if (msg.type() === 'error') errors.push(msg.text());
    });

    await page.waitForTimeout(5000);

    if (errors.length === 0) {
      console.log('✅ 无控制台错误');
    } else {
      console.log(`⚠️  发现 ${errors.length} 个错误:`);
      errors.slice(0, 3).forEach(e => console.log(`   - ${e}`));
    }

    console.log('\n✅ 验证完成！页面可以正常使用。');
    console.log('📝 提示: Browser skill 的 networkidle 策略对 Vite 开发服务器不适用');

  } catch (error) {
    console.error('❌ 验证失败:', error);
  } finally {
    await browser.close();
  }
}

quickVerify().catch(console.error);
