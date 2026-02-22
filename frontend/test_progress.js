const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

// 确保截图目录存在
const screenshotDir = path.join(__dirname, 'test-screenshots');
if (!fs.existsSync(screenshotDir)) {
  fs.mkdirSync(screenshotDir, { recursive: true });
}

// 进度值记录
const progressValues = [];
const networkRequests = [];

async function testProgressBar() {
  const browser = await chromium.launch({
    headless: false,
    slowMo: 100
  });
  
  const context = await browser.newContext();
  const page = await context.newPage();
  
  // 监听网络请求
  page.on('response', async (response) => {
    const url = response.url();
    if (url.includes('/progress') || url.includes('/process')) {
      try {
        const data = await response.json().catch(() => null);
        if (data && data.progress !== undefined) {
          const progressValue = data.progress;
          progressValues.push({
            timestamp: new Date().toISOString(),
            value: progressValue,
            url: url
          });
          console.log(`📊 Progress: ${progressValue}% at ${new Date().toLocaleTimeString()}`);
        }
      } catch (e) {
        // 忽略 JSON 解析错误
      }
    }
  });
  
  // 监听控制台消息
  page.on('console', msg => {
    if (msg.text().includes('progress') || msg.text().includes('Progress')) {
      console.log(`🖥️ Console: ${msg.text()}`);
    }
  });
  
  try {
    console.log('🌐 正在导航到前端页面...');
    await page.goto('http://localhost:5173', { waitUntil: 'networkidle' });
    
    console.log('📸 截图1: 初始状态');
    await page.screenshot({ 
      path: path.join(screenshotDir, '01_initial_state.png'),
      fullPage: true 
    });
    
    // 等待页面加载
    await page.waitForTimeout(2000);
    
    // 检查是否有视频列表
    console.log('🔍 检查视频列表...');
    const videoCount = await page.locator('video, [data-testid*="video"], .video-item, .video-card').count();
    console.log(`📹 找到 ${videoCount} 个视频元素`);
    
    // 检查是否有上传按钮或视频卡片
    const hasUploadButton = await page.locator('button, [role="button"]').filter({ hasText: /上传|upload|添加/i }).count();
    console.log(`📤 找到 ${hasUploadButton} 个上传按钮`);
    
    // 如果有视频卡片，点击第一个
    if (videoCount > 0 || await page.locator('[class*="video"], [class*="card"]').count() > 0) {
      console.log('🎬 尝试选择第一个视频...');
      
      // 尝试多种选择器
      const selectors = [
        '.video-card:first-child',
        '[data-testid*="video"]:first-child',
        'article:first-child',
        '.video-item:first-child',
        'button:has-text("处理")',
        '[role="listitem"]:first-child'
      ];
      
      let clicked = false;
      for (const selector of selectors) {
        try {
          const element = page.locator(selector).first();
          if (await element.count() > 0) {
            console.log(`🖱️ 点击元素: ${selector}`);
            await element.click();
            clicked = true;
            await page.waitForTimeout(1000);
            break;
          }
        } catch (e) {
          // 继续尝试下一个选择器
        }
      }
      
      // 截图：选择视频后
      console.log('📸 截图2: 选择视频后');
      await page.screenshot({ 
        path: path.join(screenshotDir, '02_after_select.png'),
        fullPage: true 
      });
    }
    
    // 检查是否有开始处理按钮
    console.log('🔍 查找开始处理按钮...');
    const processButtons = await page.locator('button').filter(async (el) => {
      const text = await el.textContent();
      return text && /开始|处理|start|process|分析/i.test(text);
    }).all();
    
    console.log(`🔘 找到 ${processButtons.length} 个可能的处理按钮`);
    
    if (processButtons.length > 0) {
      console.log('▶️ 点击开始处理按钮');
      await processButtons[0].click();
      
      // 等待进度条出现
      await page.waitForTimeout(2000);
      
      console.log('📸 截图3: 点击处理后');
      await page.screenshot({ 
        path: path.join(screenshotDir, '03_after_start.png'),
        fullPage: true 
      });
      
      // 监控进度条30秒
      console.log('⏱️ 开始监控进度条30秒...');
      
      for (let i = 0; i < 15; i++) {
        await page.waitForTimeout(2000);
        
        // 检查进度条值
        const progressText = await page.locator('[role="progressbar"], .progress, [class*="progress"]').first().textContent().catch(() => 'Not found');
        console.log(`📊 第${(i+1)*2}秒: ${progressText}`);
        
        // 每10秒截图一次
        if ((i + 1) % 5 === 0) {
          await page.screenshot({ 
            path: path.join(screenshotDir, `04_progress_${(i+1)*2}s.png`),
            fullPage: true 
          });
        }
        
        // 检查是否完成
        if (progressText.includes('100') || progressText.includes('完成') || progressText.includes('Complete')) {
          console.log('✅ 处理完成！');
          break;
        }
      }
      
      // 最终截图
      console.log('📸 截图5: 最终状态');
      await page.screenshot({ 
        path: path.join(screenshotDir, '05_final_state.png'),
        fullPage: true 
      });
    } else {
      console.log('⚠️ 没有找到处理按钮，可能需要先上传视频');
    }
    
    // 获取控制台日志
    console.log('\n📋 进度值汇总:');
    progressValues.forEach((v, i) => {
      console.log(`  ${i+1}. ${v.value}% at ${v.timestamp}`);
    });
    
    // 保存测试报告
    const report = {
      testTime: new Date().toISOString(),
      screenshots: fs.readdirSync(screenshotDir),
      progressValues: progressValues,
      summary: {
        totalProgressUpdates: progressValues.length,
        uniqueValues: [...new Set(progressValues.map(v => v.value))].length,
        hasDecimals: progressValues.some(v => v.value % 1 !== 0)
      }
    };
    
    fs.writeFileSync(
      path.join(screenshotDir, 'test-report.json'),
      JSON.stringify(report, null, 2)
    );
    console.log('\n📄 测试报告已保存到:', path.join(screenshotDir, 'test-report.json'));
    
  } catch (error) {
    console.error('❌ 测试失败:', error.message);
  } finally {
    await browser.close();
  }
}

testProgressBar();
