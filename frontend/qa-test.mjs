import { chromium } from 'playwright';

(async () => {
  const browser = await chromium.launch({ headless: false });
  const context = await browser.newContext({ viewport: { width: 1920, height: 1080 } });
  const page = await context.newPage();

  console.log('🌐 Navigating to SmartCut...');
  await page.goto('http://localhost:5173', { waitUntil: 'networkidle' });
  await page.screenshot({ path: '/tmp/qa-01-initial.png' });
  console.log('✅ Page loaded');

  // Step 1: Upload video
  console.log('📤 Uploading video...');
  const fileInput = await page.locator('input[type="file"]').first();
  const VIDEO_PATH = '/Users/apple/Downloads/Downie4 下载/黑色环保动画短片《转折点》，当人类成为濒危动物时，世界会怎样？.mp4';
  await fileInput.setInputFiles(VIDEO_PATH);

  // Wait for upload to complete
  await page.waitForTimeout(5000);
  await page.screenshot({ path: '/tmp/qa-02-after-upload.png' });
  console.log('✅ Video uploaded');

  // Step 2: Check title display
  console.log('📝 Checking title display...');
  const titleElement = await page.locator('h3').first();
  const titleText = await titleElement.textContent();
  const titleAttr = await titleElement.getAttribute('title');
  console.log(`Title: ${titleText}`);
  console.log(`Title attribute: ${titleAttr}`);

  // Hover over title
  await titleElement.hover();
  await page.waitForTimeout(500);
  await page.screenshot({ path: '/tmp/qa-03-title-hover.png' });
  console.log('✅ Title hover tested');

  // Step 3: Click start processing
  console.log('▶️ Clicking start processing...');
  await page.waitForTimeout(2000);
  const startButton = await page.locator('button:has-text("开始处理")').first();
  await startButton.click();
  await page.waitForTimeout(2000);
  await page.screenshot({ path: '/tmp/qa-04-after-start.png' });
  console.log('✅ Start button clicked');

  // Step 4: Monitor progress
  console.log('📊 Monitoring progress...');
  let progress = 0;
  let iterations = 0;
  const maxIterations = 120;
  const progressSnapshots = [];

  while (iterations < maxIterations) {
    iterations++;

    const progressData = await page.evaluate(() => {
      const progressText = document.body.textContent;
      const progressMatch = progressText.match(/(\d+)%/);
      const stageMatch = progressText.match(/(正在检测场景|正在切分视频|正在生成缩略图|即将完成)/);
      return {
        percent: progressMatch ? parseInt(progressMatch[1]) : null,
        stage: stageMatch ? stageMatch[1] : null,
        bodyText: progressText
      };
    });

    if (progressData.percent !== null) {
      const diff = progressData.percent - progress;
      if (diff > 5 && progress > 0) {
        console.log(`⚠️ Large jump: ${progress}% → ${progressData.percent}% (${diff}%)`);
      }
      progress = progressData.percent;
      console.log(`Progress: ${progress}% | Stage: ${progressData.stage || 'N/A'}`);

      if ([10, 50, 90, 100].includes(progress) && !progressSnapshots.includes(progress)) {
        await page.screenshot({ path: `/tmp/qa-05-progress-${progress}.png` });
        progressSnapshots.push(progress);
      }

      if (progress >= 100) break;
    }

    if (progressData.bodyText.includes('已完成') || progressData.bodyText.includes('查看结果')) {
      console.log('✅ Completion detected');
      break;
    }

    await page.waitForTimeout(1000);
  }

  await page.screenshot({ path: '/tmp/qa-06-final.png' });

  // Step 5: Verify completion state
  console.log('🏁 Verifying completion state...');
  const completionData = await page.evaluate(() => {
    const hasViewResults = document.body.textContent.includes('查看结果');
    const hasCompleted = document.body.textContent.includes('已完成');
    const sceneMatch = document.body.textContent.match(/(\d+)\s*个场景/);
    return {
      hasViewResults,
      hasCompleted,
      sceneCount: sceneMatch ? sceneMatch[1] : null
    };
  });

  console.log(`View Results: ${completionData.hasViewResults ? 'YES' : 'NO'}`);
  console.log(`Completed: ${completionData.hasCompleted ? 'YES' : 'NO'}`);
  console.log(`Scene Count: ${completionData.sceneCount || 'N/A'}`);

  await page.screenshot({ path: '/tmp/qa-07-completion.png' });

  console.log('✅ Test completed!');
  await browser.close();
})();
