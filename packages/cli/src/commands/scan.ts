// ============================================================
// CLI: Scan YouTube Channel
// ============================================================
// Scans all videos from a YouTube channel and runs QA tests
// on each one. Uses YouTube Data API v3 for video discovery
// and Playwright for page-level testing.

import {
  createTestEngine,
  DEFAULT_SCENARIOS,
  TestResult,
  TestScenario,
  MetricsCollector,
} from '@videoqa/core';
import chalk from 'chalk';
import ora from 'ora';
import axios from 'axios';
import { chromium } from 'playwright';

interface YouTubeVideo {
  id: string;
  title: string;
  url: string;
  duration: string;
  viewCount: number;
  publishedAt: string;
}

/**
 * Main scan command handler.
 * Discovers videos from a YouTube channel and runs tests.
 */
export async function scanCommand(
  channelId: string,
  options: {
    apiKey?: string;
    maxVideos?: string;
    scenario?: string;
    concurrency?: string;
    headless?: boolean;
  }
) {
  console.log(chalk.bold('\n📡 Video QA Tester — Channel Scan\n'));

  const maxVideos = parseInt(options.maxVideos || '10', 10);
  const concurrency = parseInt(options.concurrency || '3', 10);
  const apiKey = options.apiKey || process.env.YOUTUBE_API_KEY;

  console.log(chalk.dim(`  Channel: ${channelId}`));
  console.log(chalk.dim(`  Max Videos: ${maxVideos}`));
  console.log(chalk.dim(`  Concurrency: ${concurrency}`));

  // Step 1: Discover videos
  const discoverSpinner = ora('Discovering videos from channel...').start();
  let videos: YouTubeVideo[];

  if (apiKey) {
    videos = await discoverVideosViaAPI(channelId, apiKey, maxVideos, discoverSpinner);
  } else {
    videos = await discoverVideosViaScraping(channelId, maxVideos, discoverSpinner);
  }

  if (videos.length === 0) {
    discoverSpinner.fail('No videos found');
    console.log(chalk.yellow('\n  ⚠ No videos discovered. Try:'));
    console.log(chalk.dim('    1. Set YOUTUBE_API_KEY env var for reliable discovery'));
    console.log(chalk.dim('    2. Check the channel ID is correct'));
    console.log(chalk.dim('    3. Pass --api-key option'));
    return;
  }

  discoverSpinner.succeed(`Found ${videos.length} videos`);

  // Print video list
  console.log(chalk.bold('\n  Videos:'));
  videos.forEach((v, i) => {
    console.log(`    ${chalk.cyan(`${i + 1}.`)} ${chalk.white(v.title)}`);
    console.log(`       ${chalk.dim(v.url)}`);
    console.log(`       ${chalk.dim(`Views: ${v.viewCount.toLocaleString()}`)}`);
  });

  // Step 2: Select scenario
  const scenario = options.scenario
    ? DEFAULT_SCENARIOS.find(
        (s) =>
          s.id.includes(options.scenario!) ||
          s.name.toLowerCase().includes(options.scenario!.toLowerCase())
      )
    : DEFAULT_SCENARIOS[0];

  if (!scenario) {
    console.log(chalk.red('\n  ✗ Scenario not found'));
    return;
  }

  console.log(chalk.dim(`\n  Using scenario: ${scenario.name}`));

  // Step 3: Run tests
  console.log(chalk.bold('\n  Running tests...\n'));

  const engine = createTestEngine();
  await engine.browserPool.initialize();

  const results: TestResult[] = [];
  const errors: Array<{ video: string; error: string }> = [];
  let completed = 0;

  for (let i = 0; i < videos.length; i += concurrency) {
    const batch = videos.slice(i, i + concurrency);
    const batchSpinner = ora(
      `Testing batch ${Math.floor(i / concurrency) + 1}/${Math.ceil(videos.length / concurrency)}...`
    ).start();

    const batchPromises = batch.map((video) =>
      testSingleVideo(engine, video, scenario).then((result) => {
        completed++;
        if (result.status !== 'passed') {
          errors.push({ video: video.title, error: result.errors[0]?.message || 'Unknown' });
        }
        return result;
      }).catch((err) => {
        errors.push({ video: video.title, error: err.message });
        return null;
      })
    );

    const batchResults = await Promise.allSettled(batchPromises);
    batchResults.forEach((r) => {
      if (r.status === 'fulfilled' && r.value) {
        results.push(r.value);
        engine.metricsCollector.record(r.value);
      }
    });

    batchSpinner.succeed(
      `Batch ${Math.floor(i / concurrency) + 1} done — ${completed}/${videos.length}`
    );
  }

  await engine.shutdown();

  // Step 4: Print report
  printScanReport(videos.length, results, errors);
}

/**
 * Discovers videos using YouTube Data API v3.
 */
async function discoverVideosViaAPI(
  channelId: string,
  apiKey: string,
  maxVideos: number,
  spinner: ora.Ora
): Promise<YouTubeVideo[]> {
  try {
    spinner.text = 'Fetching channel details via API...';

    // Clean channel ID: handle handles (@handle) and full channel IDs
    let actualChannelId = channelId;
    if (channelId.startsWith('@') || channelId.startsWith('UC')) {
      // Look up channel by handle or ID
      const channelResponse = await axios.get(
        'https://www.googleapis.com/youtube/v3/channels',
        {
          params: {
            part: 'contentDetails',
            ...(channelId.startsWith('@')
              ? { forHandle: channelId }
              : { id: channelId }),
            key: apiKey,
          },
        }
      );

      if (!channelResponse.data.items?.length) {
        throw new Error(`Channel not found: ${channelId}`);
      }

      actualChannelId = channelResponse.data.items[0].id;
      const uploadsPlaylistId =
        channelResponse.data.items[0].contentDetails?.relatedPlaylists?.uploads;

      if (!uploadsPlaylistId) {
        throw new Error('No uploads playlist found');
      }

      // Get videos from uploads playlist
      spinner.text = 'Fetching videos from playlist...';
      const playlistResponse = await axios.get(
        'https://www.googleapis.com/youtube/v3/playlistItems',
        {
          params: {
            part: 'snippet,contentDetails',
            playlistId: uploadsPlaylistId,
            maxResults: Math.min(maxVideos, 50),
            key: apiKey,
          },
        }
      );

      if (!playlistResponse.data.items?.length) {
        return [];
      }

      // Get video details (view counts, durations)
      const videoIds = playlistResponse.data.items.map(
        (item: any) => item.contentDetails?.videoId || item.snippet?.resourceId?.videoId
      ).filter(Boolean);

      spinner.text = 'Fetching video details...';
      const videoResponse = await axios.get(
        'https://www.googleapis.com/youtube/v3/videos',
        {
          params: {
            part: 'statistics,contentDetails,snippet',
            id: videoIds.join(','),
            key: apiKey,
          },
        }
      );

      return videoResponse.data.items.map((item: any) => ({
        id: item.id,
        title: item.snippet?.title || 'Untitled',
        url: `https://www.youtube.com/watch?v=${item.id}`,
        duration: item.contentDetails?.duration || 'PT0S',
        viewCount: parseInt(item.statistics?.viewCount || '0', 10),
        publishedAt: item.snippet?.publishedAt || '',
      }));
    }

    return [];
  } catch (err) {
    spinner.warn(
      `API discovery failed: ${err instanceof Error ? err.message : 'Unknown error'}`
    );
    spinner.text = 'Falling back to scraping method...';
    return [];
  }
}

/**
 * Falls back to scraping the channel page for video discovery.
 */
async function discoverVideosViaScraping(
  channelId: string,
  maxVideos: number,
  spinner: ora.Ora
): Promise<YouTubeVideo[]> {
  try {
    spinner.text = 'Scraping channel page for videos...';

    const browser = await chromium.launch({
      headless: true,
      args: ['--no-sandbox'],
    });

    const context = await browser.newContext({
      userAgent:
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
      extraHTTPHeaders: {
        'X-Traffic-Type': 'internal_testing',
        'X-Scanner': 'videoqa-channel-scan',
      },
    });

    const page = await context.newPage();

    // Determine channel URL
    let channelUrl: string;
    if (channelId.startsWith('@')) {
      channelUrl = `https://www.youtube.com/${channelId}/videos`;
    } else if (channelId.startsWith('UC')) {
      channelUrl = `https://www.youtube.com/channel/${channelId}/videos`;
    } else {
      channelUrl = channelId; // Assume it's already a full URL
    }

    await page.goto(channelUrl, { waitUntil: 'networkidle', timeout: 30000 });
    await page.waitForTimeout(3000);

    // Scroll to load more videos
    for (let i = 0; i < 3; i++) {
      await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
      await page.waitForTimeout(2000);
    }

    // Extract video links
    const videoLinks = await page.$$eval(
      'a#video-title, a[href*="/watch?v="]',
      (links) =>
        links.map((link) => ({
          url: (link as HTMLAnchorElement).href,
          title: (link as HTMLAnchorElement).title || link.textContent?.trim() || 'Untitled',
        }))
    );

    // Deduplicate and limit
    const seen = new Set<string>();
    const videos: YouTubeVideo[] = [];

    for (const link of videoLinks) {
      if (seen.has(link.url)) continue;
      seen.add(link.url);

      const match = link.url.match(/[?&]v=([^&]+)/);
      if (!match) continue;

      videos.push({
        id: match[1],
        title: link.title,
        url: link.url,
        duration: '',
        viewCount: 0,
        publishedAt: '',
      });

      if (videos.length >= maxVideos) break;
    }

    await browser.close();
    return videos;
  } catch (err) {
    spinner.fail(`Scraping failed: ${err instanceof Error ? err.message : 'Unknown error'}`);
    return [];
  }
}

/**
 * Runs a single test on a video.
 */
async function testSingleVideo(
  engine: any,
  video: YouTubeVideo,
  scenario: TestScenario
): Promise<TestResult> {
  const { browser, context } = await engine.browserPool.acquireContext(
    {
      traffic_type: 'internal_testing',
      test_run_id: `scan-${video.id}`,
      scenario_name: scenario.name,
      worker_id: 'scan-worker',
      timestamp: new Date().toISOString(),
      environment: 'qa',
    }
  );

  const page = await context.newPage();
  const runner = new engine.runner(page, scenario.name, 'scan-worker');

  // Inject video URL into scenario action params
  const adaptedScenario: TestScenario = {
    ...scenario,
    actions: scenario.actions.map((action) => {
      if (action.type === 'navigate' && (action.params.url as string)?.includes('{{VIDEO_URL}}')) {
        return { ...action, params: { url: video.url } };
      }
      return action;
    }),
  };

  const result = await runner.execute(adaptedScenario);
  await engine.browserPool.releaseContext(context);

  return result;
}

/**
 * Prints the scan report.
 */
function printScanReport(
  totalVideos: number,
  results: TestResult[],
  errors: Array<{ video: string; error: string }>
) {
  console.log(chalk.bold('\n📊 Scan Report\n'));

  const passed = results.filter((r) => r.status === 'passed').length;
  const failed = results.filter((r) => r.status === 'failed').length;
  const errored = results.filter((r) => r.status === 'error').length;

  const barWidth = 30;
  const passRatio = totalVideos > 0 ? passed / totalVideos : 0;
  const barFilled = Math.round(barWidth * passRatio);

  console.log(`  ${chalk.bold('Results:')}`);
  console.log(`  ${chalk.green('█'.repeat(barFilled))}${chalk.red('█'.repeat(barWidth - barFilled))}`);
  console.log(`  ${chalk.green(`✓ ${passed} passed`)}  ${chalk.red(`✗ ${failed} failed`)}  ${chalk.yellow(`! ${errored} errors`)}`);

  const avgDuration = results.length > 0
    ? Math.round(results.reduce((s, r) => s + r.durationMs, 0) / results.length)
    : 0;
  console.log(`  ⏱  Avg duration: ${chalk.cyan(`${avgDuration}ms`)}`);

  if (errors.length > 0) {
    console.log(chalk.bold('\n  ❌ Errors:'));
    errors.slice(0, 5).forEach((e, i) => {
      console.log(`    ${i + 1}. ${chalk.yellow(e.video)}`);
      console.log(`       ${chalk.red(e.error)}`);
    });
    if (errors.length > 5) {
      console.log(`    ${chalk.dim(`...and ${errors.length - 5} more`)}`);
    }
  }

  console.log('');
}
