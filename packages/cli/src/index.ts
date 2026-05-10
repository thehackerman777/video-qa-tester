#!/usr/bin/env node

// ============================================================
// Video QA Tester — CLI
// ============================================================
// Command-line interface for running tests, scanning channels,
// and managing the testing infrastructure.

import { Command } from 'commander';
import { runTestCommand } from './commands/test';
import { scanCommand } from './commands/scan';
import { loadTestCommand } from './commands/loadtest';
import { antiAbuseCommand } from './commands/antiabuse';
import { dashboardCommand } from './commands/dashboard';
import { configCommand } from './commands/config';
import pkg from '../package.json';

const program = new Command();

program
  .name('videoqa')
  .description('Video QA Tester — Automated testing for video platforms')
  .version(pkg.version);

program
  .command('test')
  .description('Run a single test scenario against a video')
  .argument('<video-url>', 'URL of the video to test')
  .option('-s, --scenario <name>', 'Scenario to run (basic, full, seek, resolution, anti-abuse)')
  .option('-t, --timeout <ms>', 'Action timeout in milliseconds', '30000')
  .option('-H, --headless', 'Run browser in headless mode', true)
  .option('--headed', 'Run browser with visible UI')
  .option('--debug', 'Enable debug logging')
  .action(runTestCommand);

program
  .command('scan')
  .description('Scan a YouTube channel and test all videos')
  .argument('<channel-id>', 'YouTube channel ID or handle')
  .option('--api-key <key>', 'YouTube Data API v3 key')
  .option('--max-videos <n>', 'Maximum videos to test', '10')
  .option('--scenario <name>', 'Scenario to run on each video')
  .option('--concurrency <n>', 'Number of concurrent tests', '3')
  .option('--headless', 'Run headless', true)
  .action(scanCommand);

program
  .command('loadtest')
  .description('Run a load test with concurrent users')
  .argument('<video-url>', 'URL of the video to test')
  .option('-u, --users <n>', 'Number of concurrent users', '100')
  .option('-r, --ramp-up <s>', 'Ramp-up time in seconds', '30')
  .option('-d, --duration <s>', 'Test duration in seconds', '120')
  .option('--scenario <name>', 'Scenario for each user')
  .option('--headless', 'Run headless', true)
  .option('--quiet', 'Minimal output')
  .action(loadTestCommand);

program
  .command('anti-abuse')
  .description('Test anti-abuse and rate-limiting systems')
  .argument('<video-url>', 'URL of the video to test')
  .option('--accounts <emails>', 'Test accounts (comma-separated)')
  .option('--headless', 'Run headless', true)
  .action(antiAbuseCommand);

program
  .command('dashboard')
  .description('Export test metrics for Grafana/Prometheus')
  .option('--format <fmt>', 'Output format (prometheus, json)', 'prometheus')
  .option('--file <path>', 'Output file (default: stdout)')
  .action(dashboardCommand);

program
  .command('config')
  .description('Manage configuration')
  .argument('[action]', 'Action: get, set, list, reset')
  .argument('[key]', 'Config key')
  .argument('[value]', 'Config value')
  .action(configCommand);

program.parse(process.argv);
