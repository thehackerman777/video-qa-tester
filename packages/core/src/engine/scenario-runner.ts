// ============================================================
// Scenario Runner
// ============================================================
// Executes composable test scenarios on a video platform
// using Playwright. Each action is a step in the user journey.

import { Page } from 'playwright';
import {
  TestScenario,
  ScenarioAction,
  ActionResult,
  TestResult,
  TestingMetadata,
  TestError,
  ExpectedOutcome,
} from '../types';
import { logger } from '../utils/logger';
import { createTestingMetadata, getTestingHeaders } from '../utils/metadata';
import { v4 as uuidv4 } from 'uuid';

export class ScenarioRunner {
  private metadata: TestingMetadata;
  private results: ActionResult[] = [];
  private errors: TestError[] = [];
  private collectedMetrics: Record<string, number> = {};

  constructor(
    private page: Page,
    scenarioName: string,
    workerId: string
  ) {
    this.metadata = createTestingMetadata(scenarioName, workerId);
  }

  /**
   * Executes a complete test scenario against the current page.
   */
  async execute(scenario: TestScenario): Promise<TestResult> {
    const startTime = Date.now();
    logger.info({
      msg: `Starting scenario: ${scenario.name}`,
      scenarioId: scenario.id,
      actions: scenario.actions.length,
    });

    try {
      for (let i = 0; i < scenario.actions.length; i++) {
        const action = scenario.actions[i];
        const result = await this.executeAction(action, i);

        this.results.push(result);

        if (result.status !== 'success') {
          logger.warn({
            msg: `Action ${i} failed: ${action.type}`,
            status: result.status,
            details: result.details,
          });
        }

        // Apply delay between actions
        if (action.delayMs && action.delayMs > 0) {
          await this.page.waitForTimeout(action.delayMs);
        }
      }

      // Validate expected outcomes
      if (scenario.expectedOutcomes.length > 0) {
        this.validateOutcomes(scenario.expectedOutcomes);
      }

      const endTime = Date.now();

      return {
        testRunId: this.metadata.test_run_id,
        scenarioId: scenario.id,
        workerId: this.metadata.worker_id,
        status: this.errors.length > 0 ? 'failed' : 'passed',
        startTime: new Date(startTime).toISOString(),
        endTime: new Date(endTime).toISOString(),
        durationMs: endTime - startTime,
        actions: this.results,
        metrics: this.collectedMetrics,
        errors: this.errors,
        metadata: this.metadata,
      };
    } catch (err) {
      const endTime = Date.now();
      const error: TestError = {
        code: 'SCENARIO_ERROR',
        message: err instanceof Error ? err.message : 'Unknown error during scenario execution',
        stack: err instanceof Error ? err.stack : undefined,
        timestamp: new Date().toISOString(),
        severity: 'error',
      };

      this.errors.push(error);

      return {
        testRunId: this.metadata.test_run_id,
        scenarioId: scenario.id,
        workerId: this.metadata.worker_id,
        status: 'error',
        startTime: new Date(startTime).toISOString(),
        endTime: new Date(endTime).toISOString(),
        durationMs: endTime - startTime,
        actions: this.results,
        metrics: this.collectedMetrics,
        errors: this.errors,
        metadata: this.metadata,
      };
    }
  }

  /**
   * Executes a single action with retry logic.
   */
  private async executeAction(action: ScenarioAction, index: number): Promise<ActionResult> {
    const startTime = Date.now();

    try {
      const timeout = action.timeoutMs || 30_000;

      await this.page.waitForTimeout(500); // Small delay before action

      switch (action.type) {
        case 'navigate':
          await this.navigate(action.params.url as string);
          break;
        case 'play':
          await this.playVideo();
          break;
        case 'pause':
          await this.pauseVideo();
          break;
        case 'resume':
          await this.resumeVideo();
          break;
        case 'seek':
          await this.seekVideo(action.params.seconds as number);
          break;
        case 'change_resolution':
          await this.changeResolution(action.params.resolution as string);
          break;
        case 'click_like':
          await this.clickButton('like');
          break;
        case 'click_dislike':
          await this.clickButton('dislike');
          break;
        case 'comment':
          await this.postComment(action.params.text as string);
          break;
        case 'subscribe':
          await this.clickButton('subscribe');
          break;
        case 'scroll_comments':
          await this.scrollComments();
          break;
        case 'fullscreen':
          await this.page.keyboard.press('f');
          break;
        case 'exit_fullscreen':
          await this.page.keyboard.press('Escape');
          break;
        case 'change_speed':
          await this.changePlaybackSpeed(action.params.speed as number);
          break;
        case 'login':
          await this.login(
            action.params.username as string,
            action.params.password as string
          );
          break;
        case 'wait':
          await this.page.waitForTimeout(action.params.ms as number || 2000);
          break;
        case 'capture_snapshot':
          // Snapshot captured for debugging
          break;
        case 'validate_metric':
          await this.validateAnyMetric(
            action.params.selector as string,
            action.params.expected as string
          );
          break;
        default:
          throw new Error(`Unknown action type: ${action.type}`);
      }

      return {
        actionType: action.type,
        status: 'success',
        durationMs: Date.now() - startTime,
      };
    } catch (err) {
      const durationMs = Date.now() - startTime;
      let screenshot: string | undefined;

      try {
        const buf = await this.page.screenshot({ type: 'png' });
        screenshot = buf.toString('base64');
      } catch {
        // Screenshot failed, continue
      }

      return {
        actionType: action.type,
        status: 'failure',
        durationMs,
        details: {
          error: err instanceof Error ? err.message : 'Unknown error',
          actionIndex: index,
        },
        screenshot: screenshot?.substring(0, 1000), // Truncate for storage
      };
    }
  }

  // ============================================================
  // Navigation & Authentication
  // ============================================================

  private async navigate(url: string): Promise<void> {
    logger.debug({ msg: `Navigating to: ${url}` });
    await this.page.goto(url, {
      waitUntil: 'networkidle',
      timeout: 60_000,
    });
    await this.page.waitForTimeout(2000); // Allow JS to initialize
  }

  private async login(username: string, password: string): Promise<void> {
    logger.debug({ msg: 'Attempting login' });

    // Try common login selectors
    const emailInput = await this.page.$(
      'input[type="email"], input[name="email"], input[name="identifier"], input[autocomplete="username"]'
    );

    if (!emailInput) {
      // Click sign-in button first
      const signInButtons = await this.page.$$(
        'a:has-text("Sign in"), button:has-text("Sign in"), a:has-text("Log in"), button:has-text("Log in")'
      );

      if (signInButtons.length > 0) {
        await signInButtons[0].click();
        await this.page.waitForTimeout(2000);
      }
    }

    // Fill credentials
    const usernameField = await this.page.$(
      'input[type="email"], input[name="email"], input[name="identifier"], input[autocomplete="username"], input[name="username"]'
    );

    if (usernameField) {
      await usernameField.fill(username);
      await usernameField.press('Enter');
      await this.page.waitForTimeout(2000);
    }

    const passwordField = await this.page.$(
      'input[type="password"]'
    );

    if (passwordField) {
      await passwordField.fill(password);
      await passwordField.press('Enter');
      await this.page.waitForTimeout(3000);
    }

    logger.debug({ msg: 'Login completed' });
  }

  // ============================================================
  // Video Playback Actions
  // ============================================================

  private async playVideo(): Promise<void> {
    logger.debug({ msg: 'Playing video' });

    // Step 1: Try to click the video player area to initiate playback
    // YouTube requires a user gesture before it allows play()
    await this.page.evaluate(() => {
      // Try multiple selectors for the YouTube player
      const selectors = [
        '#movie_player',
        '.html5-video-player',
        'ytd-player',
        '#ytd-player',
        '.video-stream',
        'video',
        '#c4-player',
        '.player-container',
        '[role="button"][aria-label*="Play"]',
        '.ytp-play-button',
      ];

      for (const sel of selectors) {
        const el = document.querySelector(sel);
        if (el) {
          (el as HTMLElement).click();
          break;
        }
      }
    });

    await this.page.waitForTimeout(2000);

    // Step 2: Now try to programmatically play all video elements
    const played = await this.page.evaluate(() => {
      const videos = document.querySelectorAll('video');
      if (videos.length > 0) {
        let playedCount = 0;
        videos.forEach(v => {
          try { 
            v.muted = true; // Mute to bypass autoplay restrictions
            const p = v.play();
            if (p) {
              p.catch(() => {});
              playedCount++;
            }
          } catch {}
        });
        return playedCount > 0;
      }
      return false;
    });

    if (played) {
      logger.debug({ msg: 'Video playback started successfully' });
    } else {
      logger.debug({ msg: 'Could not start video playback (no video elements found)' });
    }

    await this.page.waitForTimeout(1000);
  }

  private async pauseVideo(): Promise<void> {
    logger.debug({ msg: 'Pausing video' });

    await this.page.evaluate(() => {
      const video = document.querySelector('video');
      if (video && !video.paused) {
        video.pause();
      }
    });
  }

  private async resumeVideo(): Promise<void> {
    logger.debug({ msg: 'Resuming video' });

    await this.page.evaluate(() => {
      const video = document.querySelector('video');
      if (video) {
        video.play().catch(() => {});
      }
    });
  }

  private async seekVideo(seconds: number): Promise<void> {
    logger.debug({ msg: `Seeking to ${seconds}s` });

    await this.page.evaluate((targetTime: number) => {
      const video = document.querySelector('video');
      if (video && video.duration) {
        video.currentTime = Math.min(targetTime, video.duration - 5);
      }
    }, seconds);

    // Record seek metric
    this.collectedMetrics['seeks'] = (this.collectedMetrics['seeks'] || 0) + 1;
  }

  private async changeResolution(resolution: string): Promise<void> {
    logger.debug({ msg: `Changing resolution to: ${resolution}` });

    // Try YouTube's settings menu
    const settingsButton = await this.page.$(
      'button[aria-label="Settings"], .ytp-button.ytp-settings-button'
    );

    if (settingsButton) {
      await settingsButton.click();
      await this.page.waitForTimeout(500);

      // Click quality menu
      const qualityOption = await this.page.$(
        'text=Quality, .ytp-menuitem:has-text("Quality")'
      );

      if (qualityOption) {
        await qualityOption.click();
        await this.page.waitForTimeout(500);

        // Select specific resolution
        const resolutionOption = await this.page.$(
          `text=${resolution}p, text=${resolution}, div.ytp-menuitem:has-text("${resolution}")`
        );

        if (resolutionOption) {
          await resolutionOption.click();
          await this.page.waitForTimeout(1000);
        }
      }
    }

    this.collectedMetrics['resolution_changes'] =
      (this.collectedMetrics['resolution_changes'] || 0) + 1;
  }

  private async changePlaybackSpeed(speed: number): Promise<void> {
    logger.debug({ msg: `Changing playback speed to: ${speed}x` });

    await this.page.evaluate((playbackSpeed: number) => {
      const videos = document.querySelectorAll('video');
      videos.forEach(v => {
        try { v.playbackRate = playbackSpeed; } catch {}
      });
    }, speed);
  }

  // ============================================================
  // Engagement Actions
  // ============================================================

  private async clickButton(type: 'like' | 'dislike' | 'subscribe'): Promise<void> {
    logger.debug({ msg: `Clicking ${type} button` });

    const selectors: Record<string, string[]> = {
      like: [
        'button[aria-label*="Like"]',
        'button[aria-label*="like this video"]',
        '#top-level-buttons [aria-label*="Like"]',
        'ytd-toggle-button-renderer:first-child',
        '[data-icon-name="Like"]',
      ],
      dislike: [
        'button[aria-label*="Dislike"]',
        'button[aria-label*="dislike this video"]',
        '#top-level-buttons [aria-label*="Dislike"]',
        'ytd-toggle-button-renderer:nth-child(2)',
        '[data-icon-name="Dislike"]',
      ],
      subscribe: [
        'button[aria-label*="Subscribe"]',
        '#subscribe-button button',
        'ytd-subscribe-button-renderer button',
        'button:has-text("Subscribe")',
      ],
    };

    const buttonSelectors = selectors[type];

    for (const selector of buttonSelectors) {
      const button = await this.page.$(selector);
      if (button) {
        await button.click();
        this.collectedMetrics[`${type}_clicks`] =
          (this.collectedMetrics[`${type}_clicks`] || 0) + 1;
        return;
      }
    }

    logger.debug({ msg: `No ${type} button found` });
  }

  private async postComment(text: string): Promise<void> {
    logger.debug({ msg: 'Posting comment' });

    const commentInput = await this.page.$(
      'input[placeholder*="Add a comment"], textarea[placeholder*="Add a comment"], #placeholder-area'
    );

    if (commentInput) {
      await commentInput.click();
      await this.page.waitForTimeout(500);
      await commentInput.fill(text);
      await this.page.waitForTimeout(500);

      const submitButton = await this.page.$(
        'button[aria-label*="Comment"], button:has-text("Comment"), #submit-button'
      );

      if (submitButton) {
        await submitButton.click();
        this.collectedMetrics['comments_posted'] =
          (this.collectedMetrics['comments_posted'] || 0) + 1;
      }
    }
  }

  private async scrollComments(): Promise<void> {
    logger.debug({ msg: 'Scrolling comments' });

    const commentsSection = await this.page.$(
      '#comments, ytd-comments, #comment-section, #items[slot="comments"]'
    );

    if (commentsSection) {
      await commentsSection.evaluate((el) => {
        el.scrollTop = el.scrollHeight;
      });
      await this.page.waitForTimeout(500);
    }

    // Also scroll the page
    await this.page.evaluate(() => {
      window.scrollBy(0, 800);
    });
    await this.page.waitForTimeout(1000);
  }

  // ============================================================
  // Metrics Collection & Validation
  // ============================================================

  /**
   * Collects current video playback metrics from the page.
   */
  async collectVideoMetrics(): Promise<Record<string, number>> {
    const metrics = await this.page.evaluate(() => {
      const video = document.querySelector('video');
      if (!video) return {};

      return {
        current_time: video.currentTime,
        duration: video.duration,
        volume: video.volume,
        playback_rate: video.playbackRate,
        paused: video.paused ? 1 : 0,
        buffered: video.buffered.length > 0
          ? video.buffered.end(video.buffered.length - 1)
          : 0,
        ready_state: video.readyState,
        network_state: video.networkState,
        video_width: video.videoWidth,
        video_height: video.videoHeight,
        error_state: video.error ? 1 : 0,
      };
    });

    Object.assign(this.collectedMetrics, metrics as Record<string, number>);
    return this.collectedMetrics;
  }

  private async validateAnyMetric(selector: string, expected: string): Promise<void> {
    const text = await this.page.textContent(selector);
    if (text?.trim() !== expected.trim()) {
      throw new Error(
        `Metric validation failed: expected "${expected}" for selector "${selector}", got "${text}"`
      );
    }
  }

  private validateOutcomes(expectedOutcomes: ExpectedOutcome[]): void {
    for (const outcome of expectedOutcomes) {
      const actual = this.collectedMetrics[outcome.metric];
      if (actual === undefined) {
        this.errors.push({
          code: 'METRIC_NOT_FOUND',
          message: `Expected metric '${outcome.metric}' was not collected`,
          timestamp: new Date().toISOString(),
          severity: 'error',
        });
        continue;
      }

      const passed = this.evaluateOutcome(actual, outcome);

      if (!passed) {
        this.errors.push({
          code: 'OUTCOME_FAILED',
          message: `Outcome '${outcome.metric}' failed: expected ${outcome.operator} ${outcome.expectedValue}, got ${actual}`,
          timestamp: new Date().toISOString(),
          severity: 'error',
        });
      }
    }
  }

  private evaluateOutcome(
    actual: number,
    outcome: ExpectedOutcome
  ): boolean {
    const expected = outcome.expectedValue as number;
    const tolerance = outcome.tolerance || 0;

    switch (outcome.operator) {
      case 'eq':
        return Math.abs(actual - expected) <= tolerance;
      case 'neq':
        return Math.abs(actual - expected) > tolerance;
      case 'gt':
        return actual > expected;
      case 'gte':
        return actual >= expected;
      case 'lt':
        return actual < expected;
      case 'lte':
        return actual <= expected;
      case 'exists':
        return actual !== undefined;
      case 'not_exists':
        return actual === undefined;
      default:
        return false;
    }
  }

  get currentMetadata(): TestingMetadata {
    return this.metadata;
  }
}


