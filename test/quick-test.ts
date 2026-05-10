// ============================================================
// Video QA Tester — Quick Integration Test
// ============================================================
// Run: npx tsx test/quick-test.ts
// Requires a YouTube video URL

import { quickTest, createTestEngine, DEFAULT_SCENARIOS, AnalyticsValidator } from '@videoqa/core';

const VIDEO_URL = process.env.VIDEO_URL || 'https://www.youtube.com/watch?v=dQw4w9WgXcQ';

async function main() {
  console.log('🎬 Video QA Tester — Integration Test\n');

  // === Test 1: Quick test ===
  console.log('📌 Test 1: Quick playback test');
  try {
    const result = await quickTest(VIDEO_URL);
    console.log(`   Status: ${result.status}`);
    console.log(`   Duration: ${result.durationMs}ms`);
    console.log(`   Actions: ${result.actions.length}`);
    console.log(`   Errors: ${result.errors.length}`);
  } catch (err) {
    console.error(`   ❌ Failed: ${err}`);
  }

  // === Test 2: Full scenario ===
  console.log('\n📌 Test 2: Full interaction scenario');
  try {
    const engine = createTestEngine();
    await engine.browserPool.initialize();

    const scenario = DEFAULT_SCENARIOS[1]; // fullInteraction
    const { browser, context } = await engine.browserPool.acquireContext({
      traffic_type: 'internal_testing',
      test_run_id: `integration-${Date.now()}`,
      scenario_name: scenario.name,
      worker_id: 'integration-test',
      timestamp: new Date().toISOString(),
      environment: 'qa',
    });

    const page = await context.newPage();
    const runner = new engine.runner(page, scenario.name, 'integration-test');

    const adaptedScenario = {
      ...scenario,
      actions: scenario.actions.map((a) => {
        if ((a.params.url as string)?.includes('{{VIDEO_URL}}')) {
          return { ...a, params: { url: VIDEO_URL } };
        }
        return a;
      }),
    };

    const result = await runner.execute(adaptedScenario);
    engine.metricsCollector.record(result);

    // Validate analytics
    const validator = new AnalyticsValidator();
    const audit = validator.auditAnalyticsPipeline([result], [
      'navigate', 'play', 'pause', 'resume', 'seek',
    ]);

    console.log(`   Status: ${result.status}`);
    console.log(`   Duration: ${result.durationMs}ms`);
    console.log(`   Metrics: ${JSON.stringify(result.metrics)}`);

    // Print summary
    const summary = engine.metricsCollector.summarize();
    console.log(`   Summary:`);
    console.log(`     Total: ${summary.totalTests}`);
    console.log(`     Passed: ${summary.passed}`);
    console.log(`     Failed: ${summary.failed}`);
    console.log(`     Actions: ${summary.actionsExecuted}`);

    await engine.browserPool.releaseContext(context);
    await engine.shutdown();
  } catch (err) {
    console.error(`   ❌ Failed: ${err}`);
  }

  // === Test 3: Analytics validation ===
  console.log('\n📌 Test 3: Analytics validation');
  const validator = new AnalyticsValidator();
  const report = validator.validateWatchTime(30, 25);
  console.log(`   Metric: ${report.name}`);
  console.log(`   Status: ${report.status}`);
  console.log(`   Expected: ${report.expected}s`);
  console.log(`   Actual: ${report.actual}s`);

  console.log('\n✅ Integration test complete\n');
}

main().catch(console.error);
