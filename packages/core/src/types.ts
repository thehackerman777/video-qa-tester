// ============================================================
// Core Types for Video QA Tester
// ============================================================

import type { Browser, BrowserContext, Page } from 'playwright';

/** Every test carries this metadata to mark it as internal testing traffic */
export interface TestingMetadata {
  traffic_type: 'internal_testing';
  test_run_id: string;
  scenario_name: string;
  worker_id: string;
  timestamp: string;
  environment: 'dev' | 'staging' | 'qa';
}

/** Configuration for test targets */
export interface PlatformConfig {
  /** Base URL of the platform under test */
  baseUrl: string;
  /** Official API endpoint (e.g., YouTube Data API v3) */
  apiEndpoint?: string;
  /** API key for official data access */
  apiKey?: string;
  /** Channel ID to scan (YouTube or internal) */
  channelId?: string;
  /** Whether to use YouTube directly or internal platform */
  targetType: 'youtube' | 'internal';
  /** Authentication credentials for test accounts */
  auth?: {
    username: string;
    password: string;
  };
}

/** User behavior simulation configuration */
export interface BehaviorConfig {
  /** Chance of watching full video (0.0 - 1.0) */
  fullWatchProbability: number;
  /** Watch time range in seconds [min, max] */
  watchTimeRange: [number, number];
  /** Pause probability per minute of playback */
  pauseProbability: number;
  /** Seek probability per minute of playback */
  seekProbability: number;
  /** Resolution change probability */
  resolutionChangeProbability: number;
  /** Comment probability */
  commentProbability: number;
  /** Like/dislike probability */
  likeProbability: number;
  /** Subscribe probability */
  subscribeProbability: number;
  /** Average pause duration in seconds */
  avgPauseDuration: number;
  /** Seek distance range in seconds [min, max] */
  seekDistanceRange: [number, number];
  /** Available resolutions to test */
  resolutions: string[];
}

/** Test plan definition */
export interface TestPlan {
  /** Unique test run identifier */
  id: string;
  /** Test name */
  name: string;
  /** Test description */
  description?: string;
  /** Platform configuration */
  platform: PlatformConfig;
  /** Behavior configuration */
  behavior: BehaviorConfig;
  /** Number of virtual users */
  concurrency: number;
  /** Ramp-up time in seconds */
  rampUpSeconds: number;
  /** Total test duration in seconds (0 = run all scenarios once) */
  durationSeconds: number;
  /** Test scenarios to execute */
  scenarios: TestScenario[];
  /** Video IDs to test (fetched from channel if empty) */
  videoIds?: string[];
}

/** Individual test scenario */
export interface TestScenario {
  id: string;
  name: string;
  description: string;
  category: 'playback' | 'user_journey' | 'analytics' | 'anti_abuse' | 'load';
  actions: ScenarioAction[];
  expectedOutcomes: ExpectedOutcome[];
  weight?: number; // Probability weight for random selection
}

/** A single action in a scenario */
export interface ScenarioAction {
  type: ActionType;
  params: Record<string, unknown>;
  delayMs?: number; // Delay before executing
  timeoutMs?: number; // Timeout for this action
}

/** Available action types */
export type ActionType =
  | 'navigate'
  | 'play'
  | 'pause'
  | 'resume'
  | 'seek'
  | 'change_resolution'
  | 'click_like'
  | 'click_dislike'
  | 'comment'
  | 'subscribe'
  | 'scroll_comments'
  | 'fullscreen'
  | 'exit_fullscreen'
  | 'change_speed'
  | 'login'
  | 'wait'
  | 'capture_snapshot'
  | 'validate_metric';

/** Expected outcome validation */
export interface ExpectedOutcome {
  metric: string;
  operator: 'eq' | 'neq' | 'gt' | 'gte' | 'lt' | 'lte' | 'exists' | 'not_exists';
  expectedValue?: number | string | boolean;
  tolerance?: number; // Tolerance for floating point comparisons
}

/** Test execution result */
export interface TestResult {
  testRunId: string;
  scenarioId: string;
  workerId: string;
  status: 'passed' | 'failed' | 'error' | 'timeout';
  startTime: string;
  endTime: string;
  durationMs: number;
  actions: ActionResult[];
  metrics: Record<string, number>;
  errors: TestError[];
  metadata: TestingMetadata;
}

/** Result of a single action execution */
export interface ActionResult {
  actionType: ActionType;
  status: 'success' | 'failure' | 'timeout';
  durationMs: number;
  details?: Record<string, unknown>;
  screenshot?: string; // Base64 screenshot on failure
}

/** Error information */
export interface TestError {
  code: string;
  message: string;
  stack?: string;
  timestamp: string;
  severity: 'warning' | 'error' | 'critical';
}

/** Browser context for a test session */
export interface TestSession {
  id: string;
  browser: Browser;
  context: BrowserContext;
  page: Page;
  metadata: TestingMetadata;
  startTime: number;
  videoId?: string;
  currentTime: number;
  userActions: ActionResult[];
}

/** Analytics event captured during testing */
export interface AnalyticsEvent {
  type: 'view' | 'watch_time' | 'like' | 'comment' | 'subscribe' | 'buffering' | 'error';
  videoId: string;
  userId: string;
  sessionId: string;
  timestamp: string;
  metadata: TestingMetadata;
  data: Record<string, unknown>;
}

/** Anti-abuse rule configuration */
export interface AntiAbuseRule {
  name: string;
  description: string;
  limit: number;
  windowMs: number;
  action: 'block' | 'throttle' | 'verify' | 'log_only';
}

/** Worker status */
export interface WorkerStatus {
  id: string;
  status: 'idle' | 'busy' | 'error' | 'offline';
  currentJobId?: string;
  lastHeartbeat: string;
  metrics: {
    testsCompleted: number;
    errors: number;
    avgDurationMs: number;
    memoryUsageMb: number;
    cpuUsage: number;
  };
}

/** Queue job definition */
export interface TestJob {
  id: string;
  type: 'single_test' | 'load_test' | 'channel_scan' | 'anti_abuse_test';
  testPlan: TestPlan;
  status: 'queued' | 'running' | 'completed' | 'failed';
  progress: number; // 0-100
  createdAt: string;
  startedAt?: string;
  completedAt?: string;
  results?: TestResult[];
  error?: string;
}

/** Dashboard metric for Grafana queries */
export interface DashboardMetric {
  timestamp: string;
  metric: string;
  value: number;
  labels: Record<string, string>;
}
