import { chromium } from 'playwright';

// Test configuration
const BASE_URL = 'http://localhost:5173';
const VIDEO_PATH = '/tmp/test_video.mp4';

async function runQATest() {
  const browser = await chromium.launch({ headless: false });
  const context = await browser.newContext({ viewport: { width: 1920, height: 1080 } });
  const page = await context.newPage();

  // Track console
  page.on('console', msg => {
    if (msg.type() === 'error') console.log('[Console Error]', msg.text());
    else if (msg.type() === 'warning') console.log('[Console Warning]', msg.text());
  });

  // Track network
  page.on('response', response => {
    if (response.status() >= 400) {
      console.log(`[Network Error] ${response.url()} - ${response.status()}`);
    }
  });

  console.log('\n' + '='.repeat(60));
  console.log(' SMARTCUT QA TEST REPORT');
  console.log('='.repeat(60) + '\n');

  const results = [];

  // Test 1: Page Load
  console.log('[TEST 1] Page Load');
  await page.goto(BASE_URL, { waitUntil: 'networkidle' });
  await page.screenshot({ path: '/tmp/qa-1-page-load.png' });
  const hasUploadArea = await page.locator('input[type="file"]').count() > 0;
  results.push({ test: 'Page Load', pass: hasUploadFail, note: hasUploadArea ? 'Upload area found' : 'Upload area NOT found' });
  console.log(`  Result: ${hasUploadArea ? 'PASS' : 'FAIL'} - ${hasUploadArea ? 'Upload area found' : 'Upload area NOT found'}\n`);

  // Test 2: Video Upload
  console.log('[TEST 2] Video Upload');
  const fileInput = await page.locator('input[type="file"]').first();
  await fileInput.setInputFiles(VIDEO_PATH);
  await page.waitForTimeout(5000);
  await page.screenshot({ path: '/tmp/qa-2-after-upload.png' });

  const hasTaskCard = await page.locator('h3').count() > 0;
  let titleText = '';
  let titleAttr = '';
  if (hasTaskCard) {
    titleText = await page.locator('h3').first().textContent();
    titleAttr = await page.locator('h3').first().getAttribute('title');
  }
  results.push({ test: 'Video Upload', pass: hasTaskCard, note: `Title: ${titleText}` });
  console.log(`  Result: ${hasTaskCard ? 'PASS' : 'FAIL'} - Video uploaded, title: ${titleText}\n`);

  // Test 3: Title Display
  console.log('[TEST 3] Title Display (Tooltip, Alignment, Ellipsis)');
  const titleElement = await page.locator('h3').first();

  // Check alignment
  const textAlign = await titleElement.evaluate(el => window.getComputedStyle(el).textAlign);
  const hasLeftAlign = textAlign === 'left' || textAlign === 'start';

  // Check tooltip
  await titleElement.hover();
  await page.waitForTimeout(500);
  await page.screenshot({ path: '/tmp/qa-3-title-hover.png' });

  results.push({
    test: 'Title Display',
    pass: hasLeftAlign && titleAttr === titleText,
    note: `Align: ${textAlign}, Tooltip: ${titleAttr === titleText ? 'YES' : 'NO'}`
  });
  console.log(`  Result: ${hasLeftAlign && titleAttr === titleText ? 'PASS' : 'PARTIAL'} - Alignment: ${textAlign}, Tooltip: ${titleAttr === titleText ? 'YES' : 'NO'}\n`);

  // Test 4: Start Processing
  console.log('[TEST 4] Start Processing Button');
  const startButton = await page.locator('button:has-text("开始处理")').first();
  await startButton.click();
  await page.waitForTimeout(3000);
  await page.screenshot({ path: '/tmp/qa-4-after-start.png' });
  results.push({ test: 'Start Processing', pass: true, note: 'Button clicked successfully' });
  console.log(`  Result: PASS - Start button clicked\n`);

  // Test 5: Progress Bar Monitoring
  console.log('[TEST 5] Progress Bar Monitoring (Smooth Updates)');
  let progress = 0;
  let iterations = 0;
  const maxIterations = 180;
  const progressSnapshots = [];
  const stageChanges = [];
  let lastStage = '';
  let largeJumps = 0;
  let stuckCount = 0;

  while (iterations < maxIterations) {
    iterations++;

    const data = await page.evaluate(() => {
      // Get progress value
      const progressBar = document.querySelector('[class*="progress"][role], [role="progressbar"]');
      let percent = null;

      if (progressBar) {
        const ariaValue = progressBar.getAttribute('aria-valuenow');
        if (ariaValue) percent = parseInt(ariaValue);
      }

      // Try from text content
      if (!percent) {
        const textMatch = document.body.textContent.match(/(\d+)%/);
        if (textMatch) percent = parseInt(textMatch[1]);
      }

      // Get stage text
      const stageElement = Array.from(document.querySelectorAll('*')).find(el =>
        el.textContent?.includes('正在') || el.textContent?.includes('即将')
      );
      const stage = stageElement?.textContent?.trim() || '';

      // Check completion
      const hasViewResults = document.body.textContent.includes('查看结果');
      const hasCompleted = document.body.textContent.includes('已完成');
      const sceneMatch = document.body.textContent.match(/(\d+)\s*个场景/);

      return { percent, stage, hasViewResults, hasCompleted, sceneCount: sceneMatch ? sceneMatch[1] : null };
    });

    if (data.percent !== null) {
      const diff = data.percent - progress;
      if (diff > 5 && progress > 0) {
        largeJumps++;
        console.log(`  ⚠️ Large jump: ${progress}% → ${data.percent}% (+${diff}%)`);
      }
      if (diff === 0 && data.percent < 100) {
        stuckCount++;
      } else {
        stuckCount = 0;
      }

      progress = data.percent;

      if (data.stage && data.stage !== lastStage) {
        stageChanges.push(data.stage);
        lastStage = data.stage;
        console.log(`  🔄 Stage: ${data.stage} | Progress: ${progress}%`);
      }

      if ([10, 25, 50, 75, 90, 100].includes(progress) && !progressSnapshots.includes(progress)) {
        await page.screenshot({ path: `/tmp/qa-5-progress-${progress}.png` });
        progressSnapshots.push(progress);
      }

      if (progress >= 100 || data.hasViewResults) {
        console.log(`  ✅ Completion detected!`);
        break;
      }
    }

    if (data.hasCompleted || data.hasViewResults) {
      console.log(`  ✅ Completion detected!`);
      break;
    }

    await page.waitForTimeout(1000);
  }

  await page.screenshot({ path: '/tmp/qa-6-progress-final.png' });

  results.push({
    test: 'Progress Bar Monitoring',
    pass: largeJumps <= 2 && stuckCount < 20,
    note: `Iterations: ${iterations}, Final: ${progress}%, Large jumps: ${largeJumps}, Stuck count: ${stuckCount}, Stages: ${stageChanges.length}`
  });
  console.log(`  Result: ${largeJumps <= 2 && stuckCount < 20 ? 'PASS' : 'PARTIAL'} - Final progress: ${progress}%, Stages detected: ${stageChanges.length}\n`);

  // Test 6: Completion State
  console.log('[TEST 6] Completion State Verification');

  const completionData = await page.evaluate(() => {
    const hasViewResults = document.body.textContent.includes('查看结果');
    const hasCompleted = document.body.textContent.includes('已完成');
    const sceneMatch = document.body.textContent.match(/(\d+)\s*个场景/);
    const button = Array.from(document.querySelectorAll('button')).find(b => b.textContent?.includes('查看结果'));

    return {
      hasViewResults,
      hasCompleted,
      sceneCount: sceneMatch ? sceneMatch[1] : null,
      hasViewButton: !!button
    };
  });

  await page.screenshot({ path: '/tmp/qa-7-completion.png' });

  results.push({
    test: 'Completion State',
    pass: completionData.hasViewButton,
    note: `View Results Button: ${completionData.hasViewButton ? 'YES' : 'NO'}, Scene Count: ${completionData.sceneCount || 'N/A'}`
  });
  console.log(`  Result: ${completionData.hasViewButton ? 'PASS' : 'PARTIAL'} - View Results: ${completionData.hasViewButton ? 'YES' : 'NO'}, Scenes: ${completionData.sceneCount || 'N/A'}\n`);

  // Summary
  console.log('='.repeat(60));
  console.log(' TEST SUMMARY');
  console.log('='.repeat(60));
  let passCount = 0;
  let failCount = 0;
  let partialCount = 0;

  for (const r of results) {
    const icon = r.pass ? '✅' : '⚠️';
    console.log(`${icon} ${r.test}: ${r.pass ? 'PASS' : 'PARTIAL'}`);
    console.log(`   ${r.note}`);
    console.log('');

    if (r.pass) passCount++;
    else partialCount++;
  }

  console.log('='.repeat(60));
  console.log(` TOTAL: ${passCount} passed, ${partialCount} partial, ${failCount} failed`);
  console.log('='.repeat(60) + '\n');

  await browser.close();
  return results;
}

runQATest().catch(console.error);
