// ============================================================
// Video QA Tester — Worker Service
// ============================================================
// Distributed worker that consumes jobs from BullMQ queue
// and executes Playwright tests.

import { Worker as BullWorker } from 'bullmq';
import IORedis from 'ioredis';
import { createLogger, createTestEngine, DEFAULT_SCENARIOS, TestScenario, TestResult } from '@videoqa/core';

const logger = createLogger('worker');

const REDIS_URL = process.env.REDIS_URL || 'redis://localhost:6379';

const connection = new IORedis(REDIS_URL, {
  maxRetriesPerRequest: null,
  enableReadyCheck: false,
});

async function start() {
  const engine = createTestEngine();
  await engine.browserPool.initialize();

  logger.info({
    msg: 'Worker starting',
    redis: REDIS_URL,
    browserPoolSize: 10,
  });

  const worker = new BullWorker(
    'videoqa-tests',
    async (job) => {
      const { videoUrl, scenario: scenarioName, concurrency } = job.data;

      logger.info({
        msg: `Processing job: ${job.name}`,
        jobId: job.id,
        scenario: scenarioName,
      });

      const scenario = DEFAULT_SCENARIOS.find(
        (s) => s.id.includes(scenarioName) || s.name.toLowerCase().includes(scenarioName.toLowerCase())
      ) || DEFAULT_SCENARIOS[0];

      const results: TestResult[] = [];
      const workers = concurrency || 1;

      // Run tests
      for (let i = 0; i < workers; i++) {
        try {
          const { browser, context } = await engine.browserPool.acquireContext(
            {
              traffic_type: 'internal_testing',
              test_run_id: `worker-${job.id}-${i}`,
              scenario_name: scenario.name,
              worker_id: `worker-${process.pid}`,
              timestamp: new Date().toISOString(),
              environment: 'qa',
            }
          );

          const page = await context.newPage();
          const runner = new engine.runner(page, scenario.name, `worker-${process.pid}`);

          const adaptedScenario: TestScenario = {
            ...scenario,
            actions: scenario.actions.map((a) => {
              if (a.type === 'navigate' && (a.params.url as string)?.includes('{{VIDEO_URL}}')) {
                return { ...a, params: { url: videoUrl } };
              }
              return a;
            }),
          };

          const result = await runner.execute(adaptedScenario);
          results.push(result);
          engine.metricsCollector.record(result);

          await engine.browserPool.releaseContext(context);

          await job.updateProgress(Math.round(((i + 1) / workers) * 100));
        } catch (err) {
          logger.error({
            msg: `Test ${i} failed`,
            error: err instanceof Error ? err.message : 'Unknown',
          });
        }
      }

      return {
        jobId: job.id,
        totalTests: results.length,
        passed: results.filter((r) => r.status === 'passed').length,
        failed: results.filter((r) => r.status === 'failed').length,
        completed: true,
      };
    },
    {
      connection,
      concurrency: parseInt(process.env.WORKER_CONCURRENCY || '5', 10),
      lockDuration: 120_000,
      maxStalledCount: 3,
    }
  );

  worker.on('completed', (job) => {
    logger.info({ msg: `Job ${job.id} completed`, returnvalue: job.returnvalue });
  });

  worker.on('failed', (job, err) => {
    logger.error({ msg: `Job ${job?.id} failed`, error: err.message });
  });

  worker.on('error', (err) => {
    logger.error({ msg: 'Worker error', error: err.message });
  });

  logger.info('Worker is ready and listening for jobs');
}

start().catch((err) => {
  logger.error({ msg: 'Failed to start worker', error: err.message });
  process.exit(1);
});

// Graceful shutdown
process.on('SIGTERM', async () => {
  logger.info('Shutting down worker...');
  process.exit(0);
});
