// ============================================================
// CLI: Load Test Command
// ============================================================

import { createTestEngine, DEFAULT_SCENARIOS, TestScenario } from '@videoqa/core';
import chalk from 'chalk';
import ora from 'ora';
import Table from 'cli-table3';

export async function loadTestCommand(
  videoUrl: string,
  options: {
    users?: string;
    rampUp?: string;
    duration?: string;
    scenario?: string;
    headless?: boolean;
    quiet?: boolean;
  }
) {
  const numUsers = parseInt(options.users || '100', 10);
  const rampUpSec = parseInt(options.rampUp || '30', 10);
  const durationSec = parseInt(options.duration || '120', 10);

  console.log(chalk.bold('\n🚀 Video QA Tester — Load Test\n'));
  console.log(chalk.dim(`  URL: ${videoUrl}`));
  console.log(chalk.dim(`  Users: ${chalk.yellow(numUsers)}`));
  console.log(chalk.dim(`  Ramp-up: ${rampUpSec}s`));
  console.log(chalk.dim(`  Duration: ${durationSec}s`));

  // Validate load level
  if (numUsers > 500 && !options.quiet) {
    console.log(chalk.yellow(`\n  ⚠ Load test with ${numUsers} users is resource-intensive.`));
    console.log(chalk.yellow('  Ensure your platform is in a test environment.'));
    console.log(chalk.yellow('  Recommended: Run on a dedicated VPS or K8s cluster.\n'));

    if (!options.quiet && !process.env.CI) {
      console.log(chalk.dim('  Press Ctrl+C within 5 seconds to cancel...'));
      await new Promise((r) => setTimeout(r, 3000));
    }
  }

  const scenarioName = options.scenario || 'basic';
  const scenario = DEFAULT_SCENARIOS.find(
    (s) =>
      s.id.includes(scenarioName) || s.name.toLowerCase().includes(scenarioName.toLowerCase())
  ) || DEFAULT_SCENARIOS[0];

  const engine = createTestEngine();
  await engine.browserPool.initialize();

  try {
    const startTime = Date.now();
    const usersPerSecond = numUsers / rampUpSec;
    let activeUsers = 0;
    const allResults: any[] = [];

    const loadSpinner = ora('Ramping up users...').start();

    // Phase 1: Ramp-up
    const rampUpInterval = setInterval(async () => {
      const elapsed = (Date.now() - startTime) / 1000;
      const targetUsers = Math.min(
        Math.floor(elapsed * usersPerSecond),
        numUsers
      );

      if (targetUsers > activeUsers) {
        const toSpawn = targetUsers - activeUsers;
        for (let i = 0; i < toSpawn; i++) {
          spawnUser(videoUrl, scenario, engine, allResults);
          activeUsers++;
        }

        loadSpinner.text = `Users: ${activeUsers}/${numUsers} active, ${allResults.filter(r => r.status).length} completed`;
      }

      if (activeUsers >= numUsers) {
        clearInterval(rampUpInterval);
        loadSpinner.succeed(`Ramp-up complete: ${activeUsers} users active`);
      }
    }, 200);

    // Phase 2: Steady state
    await new Promise((r) => setTimeout(r, rampUpSec * 1000));

    const steadySpinner = ora('Steady state...').start();
    const steadyEnd = Date.now() + durationSec * 1000;

    const steadyInterval = setInterval(() => {
      const remaining = Math.round((steadyEnd - Date.now()) / 1000);
      steadySpinner.text = `Steady state — ${remaining}s remaining — ${allResults.filter(r => r.status).length} tests completed`;
      if (Date.now() >= steadyEnd) {
        clearInterval(steadyInterval);
        steadySpinner.succeed('Steady state complete');
      }
    }, 1000);

    await new Promise((r) => setTimeout(r, durationSec * 1000));

    // Print results
    printLoadTestReport(numUsers, rampUpSec, durationSec, allResults, Date.now() - startTime);
  } finally {
    await engine.shutdown();
  }
}

async function spawnUser(
  videoUrl: string,
  scenario: TestScenario,
  engine: any,
  results: any[]
) {
  try {
    const { browser, context } = await engine.browserPool.acquireContext(
      {
        traffic_type: 'internal_testing',
        test_run_id: `load-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
        scenario_name: scenario.name,
        worker_id: `load-worker-${Math.random().toString(36).slice(2, 6)}`,
        timestamp: new Date().toISOString(),
        environment: 'qa',
      }
    );

    const page = await context.newPage();
    const runner = new engine.runner(page, scenario.name, 'load-worker');

    // Adapt scenario for this video
    const adaptedScenario: TestScenario = {
      ...scenario,
      actions: scenario.actions.map((action: any) => {
        if (action.type === 'navigate' && action.params.url?.includes('{{VIDEO_URL}}')) {
          return { ...action, params: { url: videoUrl } };
        }
        return action;
      }),
    };

    const result = await runner.execute(adaptedScenario);
    results.push({ ...result, userId: `user-${results.length}` });
    engine.metricsCollector.record(result);

    await engine.browserPool.releaseContext(context);
  } catch (err: any) {
    results.push({
      status: 'error',
      durationMs: 0,
      actions: [],
      errors: [{ message: err.message }],
      userId: `user-${results.length}`,
    });
  }
}

function printLoadTestReport(
  users: number,
  rampUp: number,
  duration: number,
  results: any[],
  totalTimeMs: number
) {
  console.log(chalk.bold('\n📊 Load Test Results\n'));

  const passed = results.filter((r) => r.status === 'passed').length;
  const failed = results.filter((r) => r.status === 'failed').length;
  const errors = results.filter((r) => r.status === 'error').length;

  const avgDuration = results.length > 0
    ? Math.round(results.reduce((s, r) => s + (r.durationMs || 0), 0) / results.length)
    : 0;

  const maxDuration = results.length > 0
    ? Math.max(...results.map((r) => r.durationMs || 0))
    : 0;

  const p99Duration = results.length > 0
    ? results.map((r) => r.durationMs || 0).sort((a: number, b: number) => a - b)[
        Math.floor(results.length * 0.99)
      ]
    : 0;

  const throughput = totalTimeMs > 0
    ? Math.round((results.length / (totalTimeMs / 1000)) * 100) / 100
    : 0;

  const table = new Table({
    style: { head: ['cyan'], compact: true },
    colWidths: [25, 15],
  });

  table.push(
    ['Configuration', ''],
    ['Total Users', users],
    ['Ramp-up Time', `${rampUp}s`],
    ['Duration', `${duration}s`],
    ['', ''],
    ['Results', ''],
    ['Completed', results.length],
    ['Passed', chalk.green(passed.toString())],
    ['Failed', chalk.red(failed.toString())],
    ['Errors', chalk.yellow(errors.toString())],
    ['Success Rate', `${results.length > 0 ? ((passed / results.length) * 100).toFixed(1) : '0'}%`],
    ['', ''],
    ['Performance', ''],
    ['Avg Duration', `${avgDuration}ms`],
    ['Max Duration', `${maxDuration}ms`],
    ['P99 Duration', `${p99Duration}ms`],
    ['Throughput', `${throughput} tests/s`],
    ['Total Time', `${(totalTimeMs / 1000).toFixed(1)}s`]
  );

  console.log(table.toString());
  console.log('');
}
