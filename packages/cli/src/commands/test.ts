// ============================================================
// CLI: Test Command
// ============================================================

import { quickTest, DEFAULT_SCENARIOS, createTestEngine, TestResult, MetricsCollector, TestScenario } from '@videoqa/core';
import chalk from 'chalk';
import ora from 'ora';
import Table from 'cli-table3';

export async function runTestCommand(
  videoUrl: string,
  options: {
    scenario?: string;
    timeout?: string;
    headless?: boolean;
    headed?: boolean;
    debug?: boolean;
  }
) {
  if (options.debug) {
    process.env.LOG_LEVEL = 'debug';
  }

  console.log(chalk.bold('\n🎬 Video QA Tester — Test Run\n'));
  console.log(chalk.dim(`  URL: ${videoUrl}`));
  console.log(chalk.dim(`  Scenario: ${options.scenario || 'basic (default)'}`));
  console.log(chalk.dim(`  Timeout: ${options.timeout}ms`));
  console.log('');

  // Find scenario
  const scenarioName = options.scenario || 'basic';
  const scenario = DEFAULT_SCENARIOS.find(
    (s) => s.id.includes(scenarioName) || s.name.toLowerCase().includes(scenarioName.toLowerCase())
  );

  const spinner = ora('Setting up test environment...').start();

  try {
    if (scenario) {
      // Run full scenario with browser pool
      spinner.text = 'Running scenario...';
      const engine = createTestEngine();
      await engine.browserPool.initialize();

      const { browser, context } = await engine.browserPool.acquireContext(
        {
          traffic_type: 'internal_testing',
          test_run_id: `cli-${Date.now()}`,
          scenario_name: scenario.name,
          worker_id: 'cli',
          timestamp: new Date().toISOString(),
          environment: 'qa',
        }
      );

      const page = await context.newPage();
      const runner = new engine.runner(page, scenario.name, 'cli');

      // Adapt scenario: replace placeholders with actual video URL
      const adaptedScenario: TestScenario = {
        ...scenario,
        actions: scenario.actions.map((action) => {
          if (action.type === 'navigate') {
            let url = action.params.url as string;
            if (url?.includes('{{VIDEO_URL}}')) {
              url = url.replace('{{VIDEO_URL}}', videoUrl);
            }
            if (url?.includes('{{PLATFORM_URL}}')) {
              url = url.replace('{{PLATFORM_URL}}', new URL(videoUrl).origin);
            }
            return { ...action, params: { url } };
          }
          return action;
        }),
      };

      spinner.succeed('Test environment ready');

      const progressSpinner = ora('Executing actions...').start();
      const result = await runner.execute(adaptedScenario);
      progressSpinner.succeed(`Test completed: ${result.status}`);

      // Collect metrics
      engine.metricsCollector.record(result);
      const summary = engine.metricsCollector.summarize();

      // Print results
      printTestResult(result, summary);

      await engine.browserPool.releaseContext(context);
      await engine.shutdown();
    } else {
      // Quick test
      spinner.text = 'Running quick test...';
      const result = await quickTest(videoUrl);
      spinner.succeed('Quick test completed');
      printTestResult(result, { totalTests: 1, passed: result.status === 'passed' ? 1 : 0, failed: result.status === 'failed' ? 1 : 0, errored: result.status === 'error' ? 1 : 0, totalDurationMs: result.durationMs, avgDurationMs: result.durationMs, actionsExecuted: result.actions.length, errorsTotal: result.errors.length, byScenario: {}, byCategory: {} });
    }
  } catch (err) {
    spinner.fail('Test failed');
    console.error(chalk.red('\n  ✗ Error:'), err instanceof Error ? err.message : 'Unknown error');
    console.error(chalk.dim('  Use --debug for detailed logs'));
    process.exit(1);
  }
}

function printTestResult(result: TestResult, summary: any) {
  // Status badge
  const statusColor = result.status === 'passed' ? chalk.green : result.status === 'failed' ? chalk.red : chalk.yellow;
  console.log(`\n  ${statusColor.bold('●')} Status: ${statusColor.bold(result.status.toUpperCase())}`);
  console.log(`    Duration: ${chalk.cyan(`${result.durationMs}ms`)}`);
  console.log(`    Actions: ${chalk.cyan(result.actions.length)}`);
  console.log(`    Errors: ${result.errors.length > 0 ? chalk.red(result.errors.length) : chalk.green('0')}`);

  // Action details table
  if (result.actions.length > 0) {
    const table = new Table({
      head: ['#', 'Action', 'Status', 'Duration', 'Details'],
      style: { compact: true },
    });

    result.actions.forEach((action, i) => {
      const details = action.details
        ? JSON.stringify(action.details).substring(0, 50)
        : '—';
      table.push([
        i + 1,
        action.actionType,
        action.status === 'success' ? chalk.green('✓') : chalk.red('✗'),
        `${action.durationMs}ms`,
        details,
      ]);
    });

    console.log(`\n  ${chalk.bold('Actions:')}`);
    console.log(table.toString());
  }

  // Summary
  console.log(`\n  ${chalk.bold('Summary:')}`);
  console.log(`    ${chalk.green(`✓ ${summary.passed} passed`)}` +
    (summary.failed > 0 ? `, ${chalk.red(`✗ ${summary.failed} failed`)}` : '') +
    (summary.errored > 0 ? `, ${chalk.yellow(`! ${summary.errored} errors`)}` : ''));
  console.log(`    ${chalk.cyan(`${summary.actionsExecuted}`)} actions executed`);
  console.log(`    ${chalk.cyan(`${(summary.totalDurationMs / 1000).toFixed(1)}s`)} total test time`);
  console.log('');
}
