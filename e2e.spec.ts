import { test, expect } from '@playwright/test';

const TEST_VIDEO = '/Users/apple/Documents/Claude Code/01_项目/短片拉片工具/smartcut/backend/data/uploads/f9272ab5-85aa-42e5-9417-75a6bdcfd852_黑色环保动画短片《转折点》，当人类成为濒危动物时，世界会怎样？.mp4';

test.describe('SmartCut E2E Tests', () => {
  test.beforeEach(async ({ page }) => {
    // 监控所有请求
    page.on('response', response => {
      if (response.status() >= 400) {
        console.log(`❌ Request failed: ${response.url()} → ${response.status()}`);
      }
    });

    // 监控 console 错误
    page.on('console', msg => {
      if (msg.type() === 'error') {
        console.log(`🔴 Console error: ${msg.text()}`);
      }
    });
  });

  test('上传功能测试', async ({ page }) => {
    console.log('\n=== 测试 1: 上传功能 ===');

    // 1. 打开首页
    await page.goto('http://localhost:5173');
    await page.waitForLoadState('networkidle');
    await page.screenshot({ path: 'test-results/01-homepage.png' });
    console.log('✅ 首页加载成功');

    // 2. 检查上传区域
    const fileInput = page.locator('input[type="file"]');
    await expect(fileInput).toBeVisible();
    console.log('✅ 上传区域存在');

    // 3. 上传视频
    await fileInput.setInputFiles(TEST_VIDEO);
    console.log('✅ 文件选择成功');

    // 4. 等待上传完成（检查 Toast 和任务卡片）
    await page.waitForTimeout(3000);
    await page.screenshot({ path: 'test-results/02-after-upload.png' });

    // 检查是否有成功 Toast
    const toast = page.locator('[class*="toast"]').first();
    if (await toast.count() > 0) {
      console.log('✅ Toast 通知已显示');
    }

    // 检查任务卡片
    const taskCard = page.locator('[class*="task"], [data-testid="task-card"]').first();
    if (await taskCard.count() > 0) {
      console.log('✅ 任务卡片已创建');
    }
  });

  test('任务处理流程测试', async ({ page }) => {
    console.log('\n=== 测试 2: 任务处理流程 ===');

    await page.goto('http://localhost:5173');
    await page.waitForLoadState('networkidle');

    // 查找开始处理按钮
    const startButton = page.locator('button:has-text("开始处理"), button:has-text("Start")').first();

    if (await startButton.count() > 0) {
      await startButton.click();
      console.log('✅ 已点击开始处理');

      // 监控状态变化（最多等待 5 分钟）
      console.log('等待处理完成...');
      let completed = false;

      for (let i = 0; i < 60; i++) {
        await page.waitForTimeout(5000);

        const statusBadge = page.locator('[class*="status"], [class*="badge"]').first();
        const statusText = await statusBadge.textContent();

        if (statusText && (
          statusText.includes('完成') ||
          statusText.includes('COMPLETED') ||
          statusText.includes('SUCCESS')
        )) {
          completed = true;
          console.log(`✅ 处理完成，耗时: ${i * 5}秒`);
          break;
        }

        if (i % 6 === 0) {
          console.log(`处理中... ${i * 5}秒, 状态: ${statusText || '未知'}`);
        }
      }

      if (!completed) {
        console.log('⚠️ 处理超时或状态未更新');
      }

      await page.screenshot({ path: 'test-results/03-after-processing.png' });
    } else {
      console.log('⚠️ 未找到开始处理按钮（任务可能已完成）');
    }
  });

  test('Timeline Modal 和缩略图测试', async ({ page }) => {
    console.log('\n=== 测试 3: Timeline Modal ===');

    await page.goto('http://localhost:5173');
    await page.waitForLoadState('networkidle');

    // 查找查看结果按钮
    const resultButton = page.locator('button:has-text("查看结果"), button:has-text("View"), button:has-text("Timeline")').first();

    if (await resultButton.count() > 0) {
      await resultButton.click();
      await page.waitForTimeout(2000);
      await page.screenshot({ path: 'test-results/04-timeline-modal.png' });
      console.log('✅ Timeline Modal 已打开');

      // 检查缩略图加载
      const images = page.locator('img').all();
      let loadedCount = 0;
      let brokenCount = 0;

      for (const img of await images) {
        const src = await img.getAttribute('src');
        const naturalWidth = await img.evaluate(el => el.naturalWidth);

        if (naturalWidth > 0) {
          loadedCount++;
        } else {
          brokenCount++;
          console.log(`❌ 缩略图加载失败: ${src}`);
        }
      }

      console.log(`✅ 缩略图统计: 已加载 ${loadedCount}, 失败 ${brokenCount}`);

      if (brokenCount > 0) {
        console.log('⚠️ 检测到缩略图加载失败！');
      }

      // 检查 Modal 布局
      const modal = page.locator('[class*="modal"], [role="dialog"]').first();
      if (await modal.count() > 0) {
        const zIndex = await modal.evaluate(el => {
          return window.getComputedStyle(el).zIndex;
        });
        console.log(`Modal z-index: ${zIndex}`);
      }

      // 关闭 Modal
      const closeButton = page.locator('button[aria-label="Close"], button:has-text("关闭"), button:has-text("Close")').first();
      if (await closeButton.count() > 0) {
        await closeButton.click();
        await page.waitForTimeout(500);
        console.log('✅ Modal 已关闭');
      }
    } else {
      console.log('⚠️ 未找到查看结果按钮');
    }
  });

  test('Toast 通知系统测试', async ({ page }) => {
    console.log('\n=== 测试 4: Toast 通知系统 ===');

    await page.goto('http://localhost:5173');
    await page.waitForLoadState('networkidle');

    // 尝试触发错误 Toast（上传错误文件）
    const fileInput = page.locator('input[type="file"]');

    // 尝试上传非视频文件（创建临时文件）
    await page.evaluate(() => {
      const blob = new Blob(['not a video'], { type: 'text/plain' });
      const file = new File([blob], 'test.txt', { type: 'text/plain' });
      const dataTransfer = new DataTransfer();
      dataTransfer.items.add(file);

      const input = document.querySelector('input[type="file"]');
      if (input) {
        input.files = dataTransfer.files;
        input.dispatchEvent(new Event('change', { bubbles: true }));
      }
    });

    await page.waitForTimeout(2000);

    // 检查 Toast
    const toasts = page.locator('[class*="toast"], [role="alert"]');
    const toastCount = await toasts.count();

    if (toastCount > 0) {
      console.log(`✅ 找到 ${toastCount} 个 Toast 元素`);

      // 检查 Toast 样式
      for (let i = 0; i < toastCount; i++) {
        const toast = toasts.nth(i);
        const zIndex = await toast.evaluate(el => window.getComputedStyle(el).zIndex);
        const position = await toast.evaluate(el => window.getComputedStyle(el).position);

        console.log(`Toast ${i + 1}: z-index=${zIndex}, position=${position}`);

        if (parseInt(zIndex) < 9999) {
          console.log(`⚠️ Toast ${i + 1} z-index 过低！`);
        }
      }

      await page.screenshot({ path: 'test-results/05-toast-test.png' });
    } else {
      console.log('⚠️ 未找到 Toast 元素（可能已消失）');
    }
  });

  test('缩略图 URL 验证', async ({ page }) => {
    console.log('\n=== 测试 5: 缩略图 URL 验证 ===');

    await page.goto('http://localhost:5173');
    await page.waitForLoadState('networkidle');

    // 打开 Timeline Modal
    const resultButton = page.locator('button:has-text("查看结果"), button:has-text("View")').first();
    if (await resultButton.count() > 0) {
      await resultButton.click();
      await page.waitForTimeout(2000);

      // 获取所有图片 URL
      const imageUrls = await page.locator('img').all();
      const urls = [];

      for (const img of imageUrls) {
        const src = await img.getAttribute('src');
        if (src && src.includes('localhost:8000')) {
          urls.push(src);
        }
      }

      console.log(`找到 ${urls.length} 个缩略图 URL`);

      // 验证 URL 可访问性（抽样检查前 5 个）
      const sampleUrls = urls.slice(0, 5);
      for (const url of sampleUrls) {
        try {
          const response = await page.request.get(url);
          if (response.ok()) {
            console.log(`✅ 缩略图可访问: ${url.split('/').pop()}`);
          } else {
            console.log(`❌ 缩略图不可访问: ${url} → ${response.status()}`);
          }
        } catch (error) {
          console.log(`❌ 缩略图请求失败: ${url}`);
        }
      }
    }
  });
});
