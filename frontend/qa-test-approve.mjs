import { chromium } from 'playwright';

const API_BASE = 'http://127.0.0.1:8000';

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();

  const result = await page.evaluate(async (apiBase) => {
    const tasksRes = await fetch(`${apiBase}/api/tasks`);
    if (!tasksRes.ok) return { error: `GET /api/tasks failed: ${tasksRes.status}` };
    const tasks = await tasksRes.json();

    const target = tasks.find(t => t.status === 'TIMELINE_READY');
    if (!target) return { skip: true, reason: 'No TIMELINE_READY task found' };

    const approveRes = await fetch(`${apiBase}/api/tasks/${target.id}/approve`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
    });
    const body = await approveRes.json();

    return {
      taskId: target.id,
      statusCode: approveRes.status,
      body,
      pass: approveRes.status === 200 && body.status === 'REVIEW_APPROVED',
    };
  }, API_BASE);

  await page.screenshot({ path: '/tmp/qa-approve-result.png' });
  await browser.close();

  if (result.error) {
    console.log(`❌ ERROR: ${result.error}`);
    process.exit(1);
  }

  if (result.skip) {
    console.log(`⚠️  SKIP: ${result.reason}`);
    process.exit(0);
  }

  const icon = result.pass ? '✅' : '❌';
  console.log(`${icon} approve TIMELINE_READY task`);
  console.log(`   Task ID:     ${result.taskId}`);
  console.log(`   Status Code: ${result.statusCode} (expected 200)`);
  console.log(`   Response:    ${JSON.stringify(result.body)}`);
  console.log(`   Result:      ${result.pass ? 'PASS' : 'FAIL'}`);

  process.exit(result.pass ? 0 : 1);
})();
