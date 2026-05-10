// ============================================================
// Testing Metadata Factory
// ============================================================
// Every request from this system MUST include internal_testing
// metadata to prevent contamination of production analytics.

import { v4 as uuidv4 } from 'uuid';
import { TestingMetadata } from '../types';

export function createTestingMetadata(
  scenarioName: string,
  workerId: string,
  environment: 'dev' | 'staging' | 'qa' = 'qa'
): TestingMetadata {
  return {
    traffic_type: 'internal_testing',
    test_run_id: uuidv4(),
    scenario_name: scenarioName,
    worker_id: workerId,
    timestamp: new Date().toISOString(),
    environment,
  };
}

/**
 * Returns HTTP headers that MUST be sent with every request
 * during testing to identify the traffic as internal QA.
 */
export function getTestingHeaders(metadata: TestingMetadata): Record<string, string> {
  return {
    'X-Traffic-Type': metadata.traffic_type,
    'X-Test-Run-ID': metadata.test_run_id,
    'X-Test-Scenario': metadata.scenario_name,
    'X-Worker-ID': metadata.worker_id,
  };
}

/**
 * Creates a query parameter payload for analytics events
 * to mark them as test events.
 */
export function getAnalyticsPayload(metadata: TestingMetadata): Record<string, string> {
  return {
    _test: '1',
    _test_run_id: metadata.test_run_id,
    _scenario: metadata.scenario_name,
  };
}
