// ============================================================
// Video QA Tester — Orchestrator Service
// ============================================================
// Central coordinator that accepts test plans, queues jobs,
// distributes work to workers, and aggregates results.

import express from 'express';
import cors from 'cors';
import { Queue, Worker, QueueEvents } from 'bullmq';
import IORedis from 'ioredis';
import { v4 as uuidv4 } from 'uuid';
import { createLogger } from '@videoqa/core';
import { register, Counter, Histogram, Gauge } from 'prom-client';

const logger = createLogger('orchestrator');

// ============================================================
// Configuration
// ============================================================

const PORT = process.env.PORT || 3000;
const REDIS_URL = process.env.REDIS_URL || 'redis://localhost:6379';
const API_KEY = process.env.ORCHESTRATOR_API_KEY || 'dev-key-change-me';

// ============================================================
// Redis & Queue Setup
// ============================================================

const connection = new IORedis(REDIS_URL, {
  maxRetriesPerRequest: null,
  enableReadyCheck: false,
});

const testQueue = new Queue('videoqa-tests', { connection });
const queueEvents = new QueueEvents('videoqa-tests', { connection });

// ============================================================
// Prometheus Metrics
// ============================================================

const testsTotal = new Counter({
  name: 'videoqa_tests_total',
  help: 'Total tests executed',
  labelNames: ['status', 'scenario'],
});

const testDuration = new Histogram({
  name: 'videoqa_test_duration_seconds',
  help: 'Test execution duration',
  labelNames: ['scenario'],
  buckets: [1, 5, 10, 30, 60, 120, 300, 600],
});

const concurrentUsers = new Gauge({
  name: 'videoqa_users_concurrent',
  help: 'Active concurrent users',
});

const workersActive = new Gauge({
  name: 'videoqa_workers_active',
  help: 'Active workers',
});

const queueDepth = new Gauge({
  name: 'videoqa_queue_depth',
  help: 'Pending jobs in queue',
});

const errorsTotal = new Counter({
  name: 'videoqa_errors_total',
  help: 'Total errors by type',
  labelNames: ['type'],
});

// ============================================================
// Express App
// ============================================================

const app = express();

app.use(cors());
app.use(express.json());

// Auth middleware
app.use((req, res, next) => {
  // Skip auth for health and metrics endpoints
  if (req.path === '/health' || req.path === '/metrics') {
    return next();
  }

  const apiKey = req.headers['x-api-key'] as string;
  if (apiKey !== API_KEY) {
    return res.status(401).json({ error: 'Unauthorized' });
  }
  next();
});

// ============================================================
// Routes
// ============================================================

/**
 * Health check
 */
app.get('/health', (_req, res) => {
  res.json({
    status: 'ok',
    version: '1.0.0',
    workers: workersActive.values().length || 0,
    queueSize: queueDepth.values().length || 0,
  });
});

/**
 * Prometheus metrics endpoint
 */
app.get('/metrics', async (_req, res) => {
  // Update queue depth gauge
  try {
    const jobCounts = await testQueue.getJobCounts();
    queueDepth.set(jobCounts.waiting || 0);
  } catch { /* ignore */ }

  res.set('Content-Type', register.contentType);
  res.send(await register.metrics());
});

/**
 * Submit a test plan for execution
 */
app.post('/api/test', async (req, res) => {
  const { videoUrl, scenario, name, concurrency, durationSeconds } = req.body;

  if (!videoUrl) {
    return res.status(400).json({ error: 'videoUrl is required' });
  }

  const jobId = uuidv4();

  const job = await testQueue.add(
    'test-execution',
    {
      jobId,
      videoUrl,
      scenario: scenario || 'basic',
      name: name || 'Unnamed Test',
      concurrency: concurrency || 1,
      durationSeconds: durationSeconds || 60,
      metadata: {
        traffic_type: 'internal_testing',
        test_run_id: jobId,
        timestamp: new Date().toISOString(),
      },
    },
    {
      jobId,
      attempts: 3,
      backoff: { type: 'exponential', delay: 2000 },
      removeOnComplete: 100,
      removeOnFail: 50,
    }
  );

  testsTotal.inc({ status: 'queued', scenario: scenario || 'basic' });

  logger.info({
    msg: 'Test job queued',
    jobId,
    videoUrl,
    scenario,
  });

  res.status(202).json({
    jobId,
    status: 'queued',
    queuePosition: await testQueue.getJobCounts(),
  });
});

/**
 * Submit a load test
 */
app.post('/api/loadtest', async (req, res) => {
  const { videoUrl, users, durationSeconds, scenario } = req.body;

  if (!videoUrl) {
    return res.status(400).json({ error: 'videoUrl is required' });
  }

  const jobId = uuidv4();

  await testQueue.add(
    'load-test',
    {
      jobId,
      videoUrl,
      users: users || 100,
      durationSeconds: durationSeconds || 120,
      scenario: scenario || 'basic',
      metadata: {
        traffic_type: 'internal_testing',
        test_run_id: jobId,
        load_test: true,
      },
    },
    { jobId, attempts: 2, backoff: 5000 }
  );

  res.status(202).json({
    jobId,
    status: 'queued',
    type: 'load_test',
    users: users || 100,
  });
});

/**
 * Channel scan
 */
app.post('/api/scan', async (req, res) => {
  const { channelId, maxVideos, scenario, apiKey } = req.body;

  if (!channelId) {
    return res.status(400).json({ error: 'channelId is required' });
  }

  const jobId = uuidv4();

  await testQueue.add(
    'channel-scan',
    {
      jobId,
      channelId,
      maxVideos: maxVideos || 10,
      scenario: scenario || 'basic',
      apiKey,
      metadata: {
        traffic_type: 'internal_testing',
        test_run_id: jobId,
      },
    },
    { jobId, attempts: 1 }
  );

  res.status(202).json({
    jobId,
    status: 'queued',
    channelId,
  });
});

/**
 * Get job status
 */
app.get('/api/jobs/:jobId', async (req, res) => {
  const { jobId } = req.params;
  const job = await testQueue.getJob(jobId);

  if (!job) {
    return res.status(404).json({ error: 'Job not found' });
  }

  const state = await job.getState();
  const progress = job.progress;

  res.json({
    jobId: job.id,
    name: job.name,
    status: state,
    progress,
    data: job.data,
    returnValue: job.returnvalue,
    failedReason: job.failedReason,
    timestamp: job.timestamp,
    processedOn: job.processedOn,
    finishedOn: job.finishedOn,
  });
});

// ============================================================
// Job Processing (Worker embedded for simplicity)
// In production, use separate worker processes
// ============================================================

const worker = new Worker(
  'videoqa-tests',
  async (job) => {
    concurrentUsers.inc();

    try {
      logger.info({
        msg: `Processing job: ${job.name}`,
        jobId: job.id,
        data: job.data,
      });

      // Simulate processing (actual execution handled by workers)
      await job.updateProgress(50);

      // In production, this would delegate to distributed workers
      await job.updateProgress(100);

      testsTotal.inc({ status: 'completed', scenario: job.data.scenario || 'unknown' });

      return { status: 'completed', jobId: job.id, processedAt: new Date().toISOString() };
    } catch (err) {
      errorsTotal.inc({ type: 'job_processing' });
      testsTotal.inc({ status: 'failed', scenario: job.data.scenario || 'unknown' });
      throw err;
    } finally {
      concurrentUsers.dec();
    }
  },
  { connection, concurrency: 10 }
);

worker.on('completed', (job) => {
  logger.info({ msg: `Job ${job.id} completed` });
});

worker.on('failed', (job, err) => {
  logger.error({ msg: `Job ${job?.id} failed`, error: err.message });
});

// ============================================================
// Start server
// ============================================================

app.listen(PORT, () => {
  logger.info({
    msg: `Orchestrator running on port ${PORT}`,
    redis: REDIS_URL,
    apiKey: API_KEY.substring(0, 4) + '...',
  });
});

// Graceful shutdown
process.on('SIGTERM', async () => {
  logger.info('Shutting down...');
  await worker.close();
  await testQueue.close();
  await connection.quit();
  process.exit(0);
});
