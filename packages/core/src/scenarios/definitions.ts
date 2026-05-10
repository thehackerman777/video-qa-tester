// ============================================================
// Pre-defined Test Scenarios
// ============================================================
// These are composable scenario templates you can use directly
// or extend for your specific platform.

import { TestScenario } from '../types';

/**
 * Scenario 1: Basic Playback
 * Simulates a user watching a video from start to near-completion.
 */
export const basicPlaybackScenario: TestScenario = {
  id: 'playback-basic',
  name: 'Basic Playback Test',
  description: 'Navigates to a video and watches most of it with natural behavior',
  category: 'playback',
  weight: 50,
  actions: [
    { type: 'navigate', params: { url: '{{VIDEO_URL}}' }, delayMs: 1000 },
    { type: 'wait', params: { ms: 5000 } },
    { type: 'play', params: {}, delayMs: 1000 },
    { type: 'wait', params: { ms: 15000 } },
    { type: 'pause', params: {}, delayMs: 3000 },
    { type: 'wait', params: { ms: 5000 } },
    { type: 'resume', params: {}, delayMs: 1000 },
    { type: 'wait', params: { ms: 30000 } },
    { type: 'seek', params: { seconds: 120 }, delayMs: 1000 },
    { type: 'wait', params: { ms: 20000 } },
  ],
  expectedOutcomes: [
    { metric: 'duration', operator: 'gt', expectedValue: 0 },
    { metric: 'current_time', operator: 'gt', expectedValue: 10 },
  ],
};

/**
 * Scenario 2: Full Interaction
 * Simulates a highly engaged user who interacts with all features.
 */
export const fullInteractionScenario: TestScenario = {
  id: 'playback-full-interaction',
  name: 'Full User Interaction',
  description: 'Complete user journey: login, browse, watch, and engage',
  category: 'user_journey',
  weight: 30,
  actions: [
    { type: 'navigate', params: { url: '{{PLATFORM_URL}}' }, delayMs: 2000 },
    { type: 'login', params: { username: '{{TEST_USER}}', password: '{{TEST_PASS}}' }, delayMs: 3000 },
    { type: 'navigate', params: { url: '{{VIDEO_URL}}' }, delayMs: 2000 },
    { type: 'wait', params: { ms: 3000 } },
    { type: 'play', params: {}, delayMs: 1000 },
    { type: 'wait', params: { ms: 20000 } },
    { type: 'change_resolution', params: { resolution: '720' }, delayMs: 2000 },
    { type: 'wait', params: { ms: 15000 } },
    { type: 'seek', params: { seconds: 60 }, delayMs: 1000 },
    { type: 'wait', params: { ms: 10000 } },
    { type: 'click_like', params: {}, delayMs: 2000 },
    { type: 'scroll_comments', params: {}, delayMs: 2000 },
    { type: 'comment', params: { text: 'Great video! Testing from our QA system.' }, delayMs: 2000 },
    { type: 'wait', params: { ms: 10000 } },
    { type: 'change_resolution', params: { resolution: '1080' }, delayMs: 2000 },
    { type: 'wait', params: { ms: 20000 } },
  ],
  expectedOutcomes: [
    { metric: 'current_time', operator: 'gt', expectedValue: 30 },
    { metric: 'resolution_changes', operator: 'gte', expectedValue: 2 },
    { metric: 'like_clicks', operator: 'gte', expectedValue: 1 },
  ],
};

/**
 * Scenario 3: Seek-heavy User
 * Simulates a user who skips around the video frequently.
 */
export const seekHeavyScenario: TestScenario = {
  id: 'playback-seek-heavy',
  name: 'Seek-Heavy User',
  description: 'User frequently seeks through the video',
  category: 'playback',
  weight: 20,
  actions: [
    { type: 'navigate', params: { url: '{{VIDEO_URL}}' }, delayMs: 1000 },
    { type: 'play', params: {}, delayMs: 1000 },
    { type: 'wait', params: { ms: 5000 } },
    { type: 'seek', params: { seconds: 30 }, delayMs: 2000 },
    { type: 'wait', params: { ms: 3000 } },
    { type: 'seek', params: { seconds: 90 }, delayMs: 2000 },
    { type: 'wait', params: { ms: 3000 } },
    { type: 'seek', params: { seconds: 150 }, delayMs: 2000 },
    { type: 'wait', params: { ms: 3000 } },
    { type: 'seek', params: { seconds: 210 }, delayMs: 2000 },
    { type: 'wait', params: { ms: 3000 } },
    { type: 'seek', params: { seconds: 300 }, delayMs: 2000 },
    { type: 'wait', params: { ms: 5000 } },
  ],
  expectedOutcomes: [
    { metric: 'seeks', operator: 'gte', expectedValue: 5 },
  ],
};

/**
 * Scenario 4: Resolution Hopper
 * Tests resolution switching behavior.
 */
export const resolutionHopperScenario: TestScenario = {
  id: 'playback-resolution-hopper',
  name: 'Resolution Hopper',
  description: 'Tests all resolution options during playback',
  category: 'playback',
  weight: 15,
  actions: [
    { type: 'navigate', params: { url: '{{VIDEO_URL}}' }, delayMs: 1000 },
    { type: 'play', params: {}, delayMs: 2000 },
    { type: 'change_resolution', params: { resolution: '144' }, delayMs: 3000 },
    { type: 'change_resolution', params: { resolution: '240' }, delayMs: 3000 },
    { type: 'change_resolution', params: { resolution: '360' }, delayMs: 3000 },
    { type: 'change_resolution', params: { resolution: '480' }, delayMs: 3000 },
    { type: 'change_resolution', params: { resolution: '720' }, delayMs: 3000 },
    { type: 'change_resolution', params: { resolution: '1080' }, delayMs: 3000 },
    { type: 'wait', params: { ms: 10000 } },
  ],
  expectedOutcomes: [
    { metric: 'resolution_changes', operator: 'gte', expectedValue: 5 },
  ],
};

/**
 * Scenario 5: Anti-Abuse Trigger Test
 * Validates that the platform correctly handles abuse-like behavior.
 */
export const antiAbuseTriggerScenario: TestScenario = {
  id: 'anti-abuse-rapid-views',
  name: 'Rapid View Trigger Test',
  description: 'Validates that rapid view events trigger rate limiting correctly',
  category: 'anti_abuse',
  weight: 10,
  actions: [
    { type: 'navigate', params: { url: '{{VIDEO_URL}}' }, delayMs: 500 },
    { type: 'play', params: {}, delayMs: 500 },
    { type: 'seek', params: { seconds: 5 }, delayMs: 100 },
    { type: 'wait', params: { ms: 2000 } },
    { type: 'navigate', params: { url: '{{VIDEO_URL}}' }, delayMs: 500 },
    { type: 'play', params: {}, delayMs: 500 },
    { type: 'seek', params: { seconds: 5 }, delayMs: 100 },
    { type: 'wait', params: { ms: 2000 } },
    { type: 'navigate', params: { url: '{{VIDEO_URL}}' }, delayMs: 500 },
    { type: 'play', params: {}, delayMs: 500 },
    { type: 'seek', params: { seconds: 5 }, delayMs: 100 },
    { type: 'wait', params: { ms: 2000 } },
    // Intentionally rapid actions to trigger rate limits
    { type: 'navigate', params: { url: '{{VIDEO_URL}}' }, delayMs: 100 },
    { type: 'play', params: {}, delayMs: 100 },
    { type: 'navigate', params: { url: '{{VIDEO_URL}}' }, delayMs: 100 },
    { type: 'play', params: {}, delayMs: 100 },
    { type: 'navigate', params: { url: '{{VIDEO_URL}}' }, delayMs: 100 },
    { type: 'play', params: {}, delayMs: 100 },
  ],
  expectedOutcomes: [
    { metric: 'rate_limit_triggered', operator: 'exists' },
  ],
};

/**
 * Scenario 6: Login + Subscribe User Journey
 */
export const subscribeJourneyScenario: TestScenario = {
  id: 'user-journey-subscribe',
  name: 'Subscribe Journey',
  description: 'User logs in, subscribes, and watches content',
  category: 'user_journey',
  weight: 25,
  actions: [
    { type: 'navigate', params: { url: '{{PLATFORM_URL}}' }, delayMs: 1000 },
    { type: 'login', params: { username: '{{TEST_USER}}', password: '{{TEST_PASS}}' }, delayMs: 3000 },
    { type: 'navigate', params: { url: '{{VIDEO_URL}}' }, delayMs: 2000 },
    { type: 'play', params: {}, delayMs: 1000 },
    { type: 'wait', params: { ms: 10000 } },
    { type: 'subscribe', params: {}, delayMs: 2000 },
    { type: 'wait', params: { ms: 15000 } },
    { type: 'click_like', params: {}, delayMs: 1000 },
    { type: 'wait', params: { ms: 10000 } },
  ],
  expectedOutcomes: [
    { metric: 'current_time', operator: 'gt', expectedValue: 20 },
  ],
};

/**
 * Scenario 7: Quick Load Test
 * Minimal scenario for load testing — fast execution.
 */
export const quickLoadScenario: TestScenario = {
  id: 'load-quick',
  name: 'Quick Load Test',
  description: 'Fast scenario designed for load testing with minimal delays',
  category: 'load',
  weight: 100,
  actions: [
    { type: 'navigate', params: { url: '{{VIDEO_URL}}' }, delayMs: 500, timeoutMs: 15000 },
    { type: 'wait', params: { ms: 3000 } },
    { type: 'play', params: {}, delayMs: 500, timeoutMs: 5000 },
    { type: 'wait', params: { ms: 5000 } },
    { type: 'pause', params: {}, delayMs: 500 },
    { type: 'wait', params: { ms: 2000 } },
    { type: 'resume', params: {}, delayMs: 500 },
    { type: 'wait', params: { ms: 5000 } },
  ],
  expectedOutcomes: [
    { metric: 'duration', operator: 'gt', expectedValue: 0 },
  ],
};

/**
 * Collection of all default scenarios
 */
export const DEFAULT_SCENARIOS: TestScenario[] = [
  basicPlaybackScenario,
  fullInteractionScenario,
  seekHeavyScenario,
  resolutionHopperScenario,
  antiAbuseTriggerScenario,
  subscribeJourneyScenario,
  quickLoadScenario,
];
