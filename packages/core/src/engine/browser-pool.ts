// ============================================================
// Browser Pool Manager
// ============================================================
// Manages a pool of Playwright browser instances for
// concurrent test execution. Handles lifecycle, cleanup,
// and resource limits.

import { chromium, firefox, Browser, BrowserContext, BrowserType } from 'playwright';
import { logger } from '../utils/logger';
import { TestingMetadata } from '../types';

interface PoolConfig {
  maxBrowsers: number;
  browserType: 'chromium' | 'firefox';
  headless: boolean;
  viewport: { width: number; height: number };
  userAgent?: string;
  proxy?: { server: string; username?: string; password?: string };
}

const DEFAULT_CONFIG: PoolConfig = {
  maxBrowsers: 10,
  browserType: 'chromium',
  headless: true,
  viewport: { width: 1920, height: 1080 },
};

export class BrowserPool {
  private browsers: Browser[] = [];
  private contexts: BrowserContext[] = [];
  private config: PoolConfig;
  private inUse = 0;
  private maxConcurrency: number;

  constructor(config: Partial<PoolConfig> = {}, maxConcurrency = 10) {
    this.config = { ...DEFAULT_CONFIG, ...config };
    this.maxConcurrency = maxConcurrency;
  }

  async initialize(): Promise<void> {
    logger.info({
      msg: 'Initializing browser pool',
      config: {
        browserType: this.config.browserType,
        headless: this.config.headless,
        maxBrowsers: this.config.maxBrowsers,
      },
    });
  }

  /**
   * Acquires a browser context for a test session.
   * Creates new browser instance if needed (up to maxBrowsers).
   */
  async acquireContext(
    metadata: TestingMetadata,
    extraHeaders?: Record<string, string>
  ): Promise<{ browser: Browser; context: BrowserContext }> {
    if (this.inUse >= this.maxConcurrency) {
      throw new Error(
        `Max concurrency (${this.maxConcurrency}) reached. Cannot acquire more contexts.`
      );
    }

    let browser = this.browsers.find((b) => b.contexts().length < 1);

    if (!browser) {
      if (this.browsers.length >= this.config.maxBrowsers) {
        // Wait for a browser to free up
        await this.waitForAvailableBrowser();
        return this.acquireContext(metadata, extraHeaders);
      }

      browser = await this.launchBrowser();
      this.browsers.push(browser);
    }

    const context = await browser.newContext({
      viewport: this.config.viewport,
      userAgent: this.config.userAgent,
      locale: 'en-US',
      timezoneId: 'America/New_York',
      permissions: ['notifications'],
      extraHTTPHeaders: {
        'X-Traffic-Type': metadata.traffic_type,
        'X-Test-Run-ID': metadata.test_run_id,
        'X-Test-Scenario': metadata.scenario_name,
        'X-Worker-ID': metadata.worker_id,
        ...extraHeaders,
      },
    });

    // Set longer timeout for video playback tests
    context.setDefaultTimeout(30_000);
    context.setDefaultNavigationTimeout(60_000);

    this.contexts.push(context);
    this.inUse++;

    logger.debug({
      msg: 'Browser context acquired',
      inUse: this.inUse,
      totalBrowsers: this.browsers.length,
      testRunId: metadata.test_run_id,
    });

    return { browser, context };
  }

  /**
   * Releases a context back to the pool.
   */
  async releaseContext(context: BrowserContext): Promise<void> {
    try {
      await context.close();
    } catch (err) {
      logger.warn({ msg: 'Error closing context', err });
    }

    this.contexts = this.contexts.filter((c) => c !== context);
    this.inUse--;

    logger.debug({
      msg: 'Browser context released',
      inUse: this.inUse,
    });
  }

  /**
   * Shuts down all browsers and clears the pool.
   */
  async shutdown(): Promise<void> {
    logger.info({
      msg: 'Shutting down browser pool',
      browsers: this.browsers.length,
      contexts: this.contexts.length,
    });

    // Close all contexts first
    for (const context of this.contexts) {
      try {
        await context.close();
      } catch {
        // Ignore errors during shutdown
      }
    }

    // Close all browsers
    for (const browser of this.browsers) {
      try {
        await browser.close();
      } catch {
        // Ignore errors during shutdown
      }
    }

    this.browsers = [];
    this.contexts = [];
    this.inUse = 0;

    logger.info('Browser pool shut down successfully');
  }

  get inUseCount(): number {
    return this.inUse;
  }

  get totalBrowsers(): number {
    return this.browsers.length;
  }

  private async launchBrowser(): Promise<Browser> {
    const launchOptions: Parameters<BrowserType['launch']>[0] = {
      headless: this.config.headless,
      args: [
        '--disable-gpu',
        '--no-sandbox',
        '--disable-setuid-sandbox',
        '--disable-dev-shm-usage',
        '--disable-web-security',
        '--autoplay-policy=no-user-gesture-required',
        '--mute-audio',
        '--disable-background-timer-throttling',
        '--disable-renderer-backgrounding',
      ],
    };

    if (this.config.proxy) {
      launchOptions.proxy = this.config.proxy;
    }

    if (this.config.browserType === 'firefox') {
      return await firefox.launch(launchOptions);
    }

    return await chromium.launch(launchOptions);
  }

  private async waitForAvailableBrowser(timeoutMs = 30_000): Promise<void> {
    const start = Date.now();

    while (Date.now() - start < timeoutMs) {
      const hasAvailable = this.browsers.some((b) => b.contexts().length === 0);

      if (hasAvailable) {
        return;
      }

      await this.sleep(500);
    }

    throw new Error('Timed out waiting for available browser');
  }

  private sleep(ms: number): Promise<void> {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }
}
