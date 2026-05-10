// ============================================================
// CLI: Config Command
// ============================================================

import chalk from 'chalk';
import { readFileSync, writeFileSync, existsSync } from 'fs';
import { join } from 'path';
import { homedir } from 'os';

const CONFIG_PATH = join(homedir(), '.videoqa', 'config.json');

interface VideoQAConfig {
  youtubeApiKey?: string;
  defaultConcurrency?: number;
  defaultHeadless?: boolean;
  defaultScenario?: string;
  testAccounts?: string[];
  environment?: 'dev' | 'staging' | 'qa';
}

function loadConfig(): VideoQAConfig {
  try {
    if (existsSync(CONFIG_PATH)) {
      return JSON.parse(readFileSync(CONFIG_PATH, 'utf-8'));
    }
  } catch {
    // Ignore
  }
  return {};
}

function saveConfig(config: VideoQAConfig): void {
  const dir = join(homedir(), '.videoqa');
  if (!existsSync(dir)) {
    const { mkdirSync } = require('fs');
    mkdirSync(dir, { recursive: true });
  }
  writeFileSync(CONFIG_PATH, JSON.stringify(config, null, 2));
}

const CONFIG_META: Record<string, { desc: string; type: string }> = {
  youtubeApiKey: { desc: 'YouTube Data API v3 key', type: 'string' },
  defaultConcurrency: { desc: 'Default concurrent users', type: 'number' },
  defaultHeadless: { desc: 'Run browser headless', type: 'boolean' },
  defaultScenario: { desc: 'Default test scenario', type: 'string' },
  testAccounts: { desc: 'Test account emails', type: 'string[]' },
  environment: { desc: 'Target environment', type: 'string' },
};

export async function configCommand(
  action?: string,
  key?: string,
  value?: string
): Promise<void> {
  const config = loadConfig();

  switch (action) {
    case 'list':
    case undefined:
      console.log(chalk.bold('\n⚙️  Video QA Config\n'));
      if (Object.keys(config).length === 0) {
        console.log('  No configuration set.\n');
        return;
      }
      for (const [k, v] of Object.entries(config)) {
        const meta = CONFIG_META[k];
        const desc = meta ? chalk.dim(`(${meta.desc})`) : '';
        const formatted = typeof v === 'object' ? JSON.stringify(v) : String(v);
        console.log(`  ${chalk.cyan(k)} = ${chalk.white(formatted)} ${desc}`);
      }
      console.log('');
      break;

    case 'get':
      if (!key) {
        console.log(chalk.red('  Specify a key: videoqa config get <key>\n'));
        return;
      }
      const val = config[key as keyof VideoQAConfig];
      console.log(`${key} = ${val !== undefined ? chalk.white(val) : chalk.dim('(not set)')}\n`);
      break;

    case 'set':
      if (!key || value === undefined) {
        console.log(chalk.red('  Usage: videoqa config set <key> <value>\n'));
        return;
      }
      const meta = CONFIG_META[key];
      if (!meta) {
        console.log(chalk.yellow(`  Unknown key: ${key}\n`));
        return;
      }
      if (meta.type === 'number') {
        (config as any)[key] = parseFloat(value);
      } else if (meta.type === 'boolean') {
        (config as any)[key] = value === 'true' || value === '1';
      } else {
        (config as any)[key] = value;
      }
      saveConfig(config);
      console.log(chalk.green(`  ✓ ${key} set to: ${value}\n`));
      break;

    case 'reset':
      saveConfig({});
      console.log(chalk.green('  ✓ Configuration reset\n'));
      break;

    default:
      console.log(chalk.red(`  Unknown action: ${action}\n`));
      console.log('  Available: list, get, set, reset\n');
  }
}
