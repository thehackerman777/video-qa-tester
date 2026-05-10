// ============================================================
// CLI: Anti-Abuse Test Command
// ============================================================

import { createTestEngine, AntiAbuseTester } from '@videoqa/core';
import chalk from 'chalk';
import ora from 'ora';
import Table from 'cli-table3';

export async function antiAbuseCommand(
  videoUrl: string,
  options: {
    accounts?: string;
    headless?: boolean;
  }
) {
  console.log(chalk.bold('\n🛡️  Video QA Tester — Anti-Abuse Audit\n'));
  console.log(chalk.dim(`  URL: ${videoUrl}`));

  const testAccounts = options.accounts
    ? options.accounts.split(',').map((s) => s.trim())
    : ['qa-test-1@videoqa.local'];

  const engine = createTestEngine();
  await engine.browserPool.initialize();

  const spinner = ora('Running anti-abuse test suite...').start();

  try {
    const tester = new AntiAbuseTester(
      engine.browserPool,
      videoUrl
    );

    const report = await tester.runFullTestSuite(videoUrl, testAccounts);
    spinner.succeed('Anti-abuse tests completed');

    // Print report
    console.log(chalk.bold('\n📊 Anti-Abuse Report\n'));

    const table = new Table({
      head: ['Test', 'Triggered', 'Response Time', 'Status'],
      style: { compact: true },
      colWidths: [40, 15, 18, 10],
    });

    report.tests.forEach((test) => {
      table.push([
        test.description.substring(0, 38),
        test.triggered ? chalk.yellow('✓ Triggered') : chalk.dim('—'),
        `${test.responseTime}ms`,
        test.passed ? chalk.green('PASS') : chalk.red('FAIL'),
      ]);
    });

    console.log(table.toString());
    console.log(`\n  Summary: ${chalk.green(`${report.summary.passed} passed`)} / ${chalk.red(`${report.summary.failed} failed`)}`);
    console.log('');
  } finally {
    await engine.shutdown();
  }
}
