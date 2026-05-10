// ============================================================
// Analytics Validator
// ============================================================
// Compares observed metrics against expected values from
// the analytics pipeline. Validates that views, watch time,
// engagement, and other metrics are correctly tracked.

import { logger } from '../utils/logger';
import { TestResult, AnalyticsEvent } from '../types';

export interface ValidationReport {
  testRunId: string;
  timestamp: string;
  metrics: ValidatedMetric[];
  passed: boolean;
  summary: {
    total: number;
    passed: number;
    failed: number;
    warnings: number;
  };
}

export interface ValidatedMetric {
  name: string;
  expected: number | string | boolean;
  actual: number | string | boolean | undefined;
  status: 'passed' | 'failed' | 'warning' | 'not_found';
  tolerance?: number;
  details?: string;
}

export class AnalyticsValidator {
  /**
   * Validates that analytics events were properly tracked.
   */
  validateEvents(
    result: TestResult,
    expectedEvents: EventExpectation[]
  ): ValidationReport {
    const metrics: ValidatedMetric[] = [];

    for (const expectation of expectedEvents) {
      const validated = this.checkEvent(result, expectation);
      metrics.push(validated);
    }

    const summary = {
      total: metrics.length,
      passed: metrics.filter((m) => m.status === 'passed').length,
      failed: metrics.filter((m) => m.status === 'failed').length,
      warnings: metrics.filter((m) => m.status === 'warning').length,
    };

    return {
      testRunId: result.testRunId,
      timestamp: new Date().toISOString(),
      metrics,
      passed: summary.failed === 0,
      summary,
    };
  }

  /**
   * Validates view count increment over a period.
   * Playwright watches the DOM for view count changes.
   */
  async validateViewCount(
    initialViews: number,
    currentViews: number,
    minExpectedIncrement: number = 1
  ): Promise<ValidatedMetric> {
    const increment = currentViews - initialViews;
    const passed = increment >= minExpectedIncrement;

    logger.debug({
      msg: 'View count validation',
      initialViews,
      currentViews,
      increment,
      expected: `>= ${minExpectedIncrement}`,
      passed,
    });

    return {
      name: 'view_count_increment',
      expected: minExpectedIncrement,
      actual: increment,
      status: passed ? 'passed' : 'failed',
      details: `Views went from ${initialViews} to ${currentViews} (increment: ${increment})`,
    };
  }

  /**
   * Validates watch time is correctly recorded.
   */
  validateWatchTime(
    recordedWatchTime: number,
    minimumWatchTime: number
  ): ValidatedMetric {
    const passed = recordedWatchTime >= minimumWatchTime;

    return {
      name: 'watch_time',
      expected: minimumWatchTime,
      actual: recordedWatchTime,
      status: passed ? 'passed' : 'failed',
      details: `Recorded watch time: ${recordedWatchTime}s, minimum expected: ${minimumWatchTime}s`,
    };
  }

  /**
   * Validates that the analytics pipeline contains the testing metadata.
   */
  validateTestingMetadata(
    event: AnalyticsEvent | Record<string, unknown>
  ): ValidatedMetric {
    const hasTestFlag =
      (event as Record<string, unknown>)._test === '1' ||
      (event as { metadata?: { traffic_type: string } }).metadata?.traffic_type === 'internal_testing';

    return {
      name: 'testing_metadata_present',
      expected: true,
      actual: hasTestFlag,
      status: hasTestFlag ? 'passed' : 'failed',
      details: hasTestFlag
        ? 'Event correctly marked as internal testing traffic'
        : 'Missing testing metadata in analytics event',
    };
  }

  /**
   * Performs a complete analytics pipeline audit.
   * Validates that all expected events were generated.
   */
  auditAnalyticsPipeline(
    results: TestResult[],
    expectedEventTypes: string[]
  ): ValidationReport {
    const metrics: ValidatedMetric[] = [];
    const generatedEvents = new Set<string>();

    // Collect event types from results
    for (const result of results) {
      for (const action of result.actions) {
        generatedEvents.add(action.actionType);
      }
    }

    for (const eventType of expectedEventTypes) {
      const found = generatedEvents.has(eventType);
      metrics.push({
        name: `event_${eventType}`,
        expected: true,
        actual: found,
        status: found ? 'passed' : 'failed',
        details: found ? `Event '${eventType}' was generated` : `Event '${eventType}' was NOT generated`,
      });
    }

    const summary = {
      total: metrics.length,
      passed: metrics.filter((m) => m.status === 'passed').length,
      failed: metrics.filter((m) => m.status === 'failed').length,
      warnings: metrics.filter((m) => m.status === 'warning').length,
    };

    return {
      testRunId: results[0]?.testRunId || 'unknown',
      timestamp: new Date().toISOString(),
      metrics,
      passed: summary.failed === 0,
      summary,
    };
  }

  private checkEvent(
    result: TestResult,
    expectation: EventExpectation
  ): ValidatedMetric {
    // Check if the action type exists in the results
    const matchingActions = result.actions.filter(
      (a) => a.actionType === expectation.eventType
    );

    const found = matchingActions.length > 0;
    const count = matchingActions.length;

    let status: 'passed' | 'failed' | 'warning' | 'not_found' = 'not_found';

    if (expectation.minCount !== undefined) {
      status = count >= expectation.minCount ? 'passed' : 'failed';
    } else {
      status = found ? 'passed' : 'failed';
    }

    return {
      name: `event_${expectation.eventType}`,
      expected: expectation.minCount || 1,
      actual: count,
      status,
      details: `${expectation.eventType}: found ${count} occurrences`,
    };
  }
}

export interface EventExpectation {
  eventType: string;
  minCount?: number;
  eventProperties?: Record<string, unknown>;
}
