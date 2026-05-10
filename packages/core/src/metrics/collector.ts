// ============================================================
// Metrics Collector
// ============================================================
// Collects and exports metrics from test runs. Integrates
// with Prometheus for production monitoring.

import { logger } from '../utils/logger';
import { TestResult, DashboardMetric } from '../types';

export interface MetricsSummary {
  totalTests: number;
  passed: number;
  failed: number;
  errored: number;
  totalDurationMs: number;
  avgDurationMs: number;
  actionsExecuted: number;
  errorsTotal: number;
  byScenario: Record<string, ScenarioMetrics>;
  byCategory: Record<string, CategoryMetrics>;
}

export interface ScenarioMetrics {
  total: number;
  passed: number;
  failed: number;
  avgDurationMs: number;
  avgActions: number;
}

export interface CategoryMetrics {
  total: number;
  passed: number;
  passedRate: number;
}

export class MetricsCollector {
  private results: TestResult[] = [];
  private dashboardMetrics: DashboardMetric[] = [];
  private startTime = Date.now();

  /**
   * Records a test result.
   */
  record(result: TestResult): void {
    this.results.push(result);
    this.emitPrometheusMetrics(result);
  }

  /**
   * Records multiple test results at once.
   */
  recordBatch(results: TestResult[]): void {
    for (const result of results) {
      this.record(result);
    }
  }

  /**
   * Generates a comprehensive metrics summary.
   */
  summarize(): MetricsSummary {
    const passed = this.results.filter((r) => r.status === 'passed').length;
    const failed = this.results.filter((r) => r.status === 'failed').length;
    const errored = this.results.filter((r) => r.status === 'error').length;
    const totalDuration = this.results.reduce((sum, r) => sum + r.durationMs, 0);

    const byScenario: Record<string, ScenarioMetrics> = {};
    const byCategory: Record<string, CategoryMetrics> = {};

    for (const result of this.results) {
      // By scenario
      if (!byScenario[result.scenarioId]) {
        byScenario[result.scenarioId] = {
          total: 0,
          passed: 0,
          failed: 0,
          avgDurationMs: 0,
          avgActions: 0,
        };
      }
      byScenario[result.scenarioId].total++;
      if (result.status === 'passed') byScenario[result.scenarioId].passed++;
      if (result.status === 'failed') byScenario[result.scenarioId].failed++;
      byScenario[result.scenarioId].avgDurationMs += result.durationMs;
      byScenario[result.scenarioId].avgActions += result.actions.length;

      // By category (extracted from scenarioId prefix)
      const category = result.scenarioId.split('-')[0] || 'unknown';
      if (!byCategory[category]) {
        byCategory[category] = { total: 0, passed: 0, passedRate: 0 };
      }
      byCategory[category].total++;
      if (result.status === 'passed') byCategory[category].passed++;
    }

    // Calculate averages
    for (const [key, val] of Object.entries(byScenario)) {
      val.avgDurationMs = val.total > 0 ? Math.round(val.avgDurationMs / val.total) : 0;
      val.avgActions = val.total > 0 ? Math.round(val.avgActions / val.total) : 0;
    }

    for (const [key, val] of Object.entries(byCategory)) {
      val.passedRate = val.total > 0 ? (val.passed / val.total) * 100 : 0;
    }

    const totalErrors = this.results.reduce((sum, r) => sum + r.errors.length, 0);
    const totalActions = this.results.reduce((sum, r) => sum + r.actions.length, 0);

    return {
      totalTests: this.results.length,
      passed,
      failed,
      errored,
      totalDurationMs: totalDuration,
      avgDurationMs: this.results.length > 0 ? Math.round(totalDuration / this.results.length) : 0,
      actionsExecuted: totalActions,
      errorsTotal: totalErrors,
      byScenario,
      byCategory,
    };
  }

  /**
   * Returns dashboard metrics formatted for Grafana/Prometheus.
   */
  getDashboardMetrics(): DashboardMetric[] {
    return this.dashboardMetrics;
  }

  /**
   * Exports summary as Prometheus-compatible text format.
   */
  exportPrometheus(): string {
    const summary = this.summarize();
    const lines: string[] = [];

    lines.push('# HELP videoqa_tests_total Total tests executed');
    lines.push('# TYPE videoqa_tests_total counter');
    lines.push(`videoqa_tests_total{status="passed"} ${summary.passed}`);
    lines.push(`videoqa_tests_total{status="failed"} ${summary.failed}`);
    lines.push(`videoqa_tests_total{status="error"} ${summary.errored}`);

    lines.push('');
    lines.push('# HELP videoqa_test_duration_seconds Test execution duration');
    lines.push('# TYPE videoqa_test_duration_seconds histogram');
    lines.push(`videoqa_test_duration_seconds_sum ${summary.totalDurationMs / 1000}`);
    lines.push(`videoqa_test_duration_seconds_count ${summary.totalTests}`);

    lines.push('');
    lines.push('# HELP videoqa_actions_total Total actions executed');
    lines.push('# TYPE videoqa_actions_total counter');
    lines.push(`videoqa_actions_total ${summary.actionsExecuted}`);

    lines.push('');
    lines.push('# HELP videoqa_errors_total Total errors');
    lines.push('# TYPE videoqa_errors_total counter');
    lines.push(`videoqa_errors_total ${summary.errorsTotal}`);

    lines.push('');
    lines.push('# HELP videoqa_scenario_info Scenario information');
    lines.push('# TYPE videoqa_scenario_info gauge');

    for (const [scenario, metrics] of Object.entries(summary.byScenario)) {
      const passRate = metrics.total > 0
        ? ((metrics.passed / metrics.total) * 100).toFixed(2)
        : '0';

      lines.push(
        `videoqa_scenario_info{scenario="${scenario}",pass_rate="${passRate}%",avg_duration="${metrics.avgDurationMs}ms"} 1`
      );
    }

    return lines.join('\n');
  }

  /**
   * Reset collector between test runs.
   */
  reset(): void {
    this.results = [];
    this.dashboardMetrics = [];
    this.startTime = Date.now();
  }

  private emitPrometheusMetrics(result: TestResult): void {
    const now = new Date().toISOString();

    this.dashboardMetrics.push(
      {
        timestamp: now,
        metric: 'videoqa_test_duration_ms',
        value: result.durationMs,
        labels: {
          scenario: result.scenarioId,
          status: result.status,
          worker: result.workerId,
        },
      },
      {
        timestamp: now,
        metric: 'videoqa_actions_count',
        value: result.actions.length,
        labels: {
          scenario: result.scenarioId,
        },
      },
      {
        timestamp: now,
        metric: 'videoqa_errors_count',
        value: result.errors.length,
        labels: {
          scenario: result.scenarioId,
          severity: result.errors[0]?.severity || 'none',
        },
      }
    );

    // Track individual metrics from test result
    for (const [key, value] of Object.entries(result.metrics)) {
      this.dashboardMetrics.push({
        timestamp: now,
        metric: `videoqa_custom_${key}`,
        value,
        labels: {
          scenario: result.scenarioId,
          testRunId: result.testRunId,
        },
      });
    }
  }
}
