// ============================================================
// Video QA Tester — Core Package
// ============================================================
// Export all public APIs from the core testing engine.

// Types
export * from './types';

// Utils
export { createLogger, logger } from './utils/logger';
export { createTestingMetadata, getTestingHeaders, getAnalyticsPayload } from './utils/metadata';

// Engine
export { BrowserPool } from './engine/browser-pool';
export { ScenarioRunner } from './engine/scenario-runner';

// Scenarios
export {
  basicPlaybackScenario,
  fullInteractionScenario,
  seekHeavyScenario,
  resolutionHopperScenario,
  antiAbuseTriggerScenario,
  subscribeJourneyScenario,
  quickLoadScenario,
  viewCountingScenario,
  DEFAULT_SCENARIOS,
} from './scenarios/definitions';

// Analytics
export { AnalyticsValidator } from './analytics/validator';
export type { ValidationReport, ValidatedMetric, EventExpectation } from './analytics/validator';

// Anti-Abuse
export { AntiAbuseTester } from './antiabuse/tester';
export type { AntiAbuseTestResult, AntiAbuseReport } from './antiabuse/tester';

// Metrics
export { MetricsCollector } from './metrics/collector';
export type { MetricsSummary, ScenarioMetrics, CategoryMetrics } from './metrics/collector';

// ============================================================
// Convenience: run a single test scenario quickly
// ============================================================

import { chromium, Browser, Page } from 'playwright';
import { TestScenario, TestResult, PlatformConfig, BehaviorConfig, TestingMetadata } from './types';
import { ScenarioRunner } from './engine/scenario-runner';
import { BrowserPool } from './engine/browser-pool';
import { MetricsCollector } from './metrics/collector';
import { AntiAbuseTester } from './antiabuse/tester';
import { AnalyticsValidator } from './analytics/validator';
import { createTestingMetadata } from './utils/metadata';
import { logger } from './utils/logger';

/**
 * Quick-start: run a scenario against a URL.
 * Useful for one-off tests and debugging.
 */
export async function quickTest(
  videoUrl: string,
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  _platform?: Partial<PlatformConfig>,
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  _behavior?: Partial<BehaviorConfig>
): Promise<TestResult> {
  const metadata = createTestingMetadata('quick-test', 'local');
  let browser: Browser | null = null;

  try {
    browser = await chromium.launch({
      headless: true,
      args: ['--no-sandbox', '--autoplay-policy=no-user-gesture-required'],
    });

    const context = await browser.newContext({
      viewport: { width: 1920, height: 1080 },
      extraHTTPHeaders: {
        'X-Traffic-Type': metadata.traffic_type,
        'X-Test-Run-ID': metadata.test_run_id,
      },
    });

    const page = await context.newPage();
    const runner = new ScenarioRunner(page, 'quick-test', 'local');

    // Run a default playback scenario
    const scenario: TestScenario = {
      id: 'quick-test',
      name: 'Quick Test',
      description: 'One-off quick test',
      category: 'playback',
      actions: [
        { type: 'navigate', params: { url: videoUrl } },
        { type: 'wait', params: { ms: 3000 } },
        { type: 'play', params: {} },
        { type: 'wait', params: { ms: 10000 } },
        { type: 'pause', params: {} },
        { type: 'wait', params: { ms: 2000 } },
        { type: 'resume', params: {} },
        { type: 'wait', params: { ms: 10000 } },
      ],
      expectedOutcomes: [],
    };

    const result = await runner.execute(scenario);

    await context.close();
    logger.info({
      msg: 'Quick test completed',
      status: result.status,
      duration: `${result.durationMs}ms`,
    });

    return result;
  } catch (err) {
    logger.error({ msg: 'Quick test failed', err });
    throw err;
  } finally {
    if (browser) {
      await browser.close();
    }
  }
}

/**
 * Creates a configured test engine ready to run.
 * This is the main entry point for most use cases.
 */
export function createTestEngine() {
  const browserPool = new BrowserPool({ headless: true });
  const metricsCollector = new MetricsCollector();

  return {
    browserPool,
    metricsCollector,
    runner: ScenarioRunner,
    antiAbuseTester: (baseUrl: string) =>
      new AntiAbuseTester(browserPool, baseUrl),
    analyticsValidator: new AnalyticsValidator(),
    async shutdown() {
      await browserPool.shutdown();
    },
  };
}
