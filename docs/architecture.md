# Video QA Tester — Architecture Document

## 📋 Overview

**Video QA Tester** is a legitimate, ethical QA/testing automation system designed for internal testing of video streaming platforms (YouTube-like). It simulates real user behavior to validate:

- Playback metrics (views, watch time, engagement)
- Backend analytics pipelines
- Anti-abuse and rate-limiting systems
- CDN and caching behavior
- Concurrent user handling (load testing)
- Race conditions and edge cases

## 🏗️ High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                         CLI / API Layer                      │
│  (TypeScript CLI, REST API, KMP Client — Android/Desktop)   │
└────────────────────────┬────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────┐
│                   Orchestrator Service                       │
│  - Test plan scheduler                                      │
│  - Queue management (Redis BullMQ)                          │
│  - Job distribution to workers                              │
│  - Result aggregation                                       │
│  - Metrics export (Prometheus)                              │
└────────────────────────┬────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────┐
│                    Worker Pool (Distributed)                  │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐     ┌──────────┐  │
│  │ Worker 1 │ │ Worker 2 │ │ Worker 3 │ ... │ Worker N │  │
│  │(Browser) │ │(Browser) │ │(Browser) │     │(Browser) │  │
│  └──────────┘ └──────────┘ └──────────┘     └──────────┘  │
└────────────────────────┬────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────┐
│                   Platform Under Test                        │
│  (YouTube / Your own video platform)                        │
│  - API endpoints                                            │
│  - WebSocket events                                         │
│  - HLS/DASH streams                                         │
│  - Analytics pipeline                                       │
└─────────────────────────────────────────────────────────────┘
```

## 📦 Component Breakdown

### 1. Core Engine (`packages/core`)
The heart of the system. Contains:
- **Browser Automation**: Playwright-based user simulation
- **Scenario Runner**: Executes composable test scenarios
- **Metrics Collector**: Captures performance metrics, network logs, console errors
- **Analytics Validator**: Compares observed metrics vs expected
- **Anti-Abuse Tester**: Validates rate limits, throttling, fingerprint detection

### 2. CLI (`packages/cli`)
Command-line interface for:
- Running ad-hoc test scenarios
- Starting load tests
- Viewing results
- Managing configurations

### 3. KMP Client (`packages/kmp-client`)
Kotlin Multiplatform client for:
- **Android**: Native test runner on Android devices
- **Desktop (JVM)**: Run tests from desktop
- **iOS**: Test from iOS devices
- Shared logic for test configuration and result reporting

### 4. Load Tester (`packages/load-tester`)
Uses k6 + Playwright for:
- Ramp-up tests (10 → 10000 users)
- Steady-state endurance
- Spike testing
- Stress testing
- Soak testing

### 5. Orchestrator (`services/orchestrator`)
Central coordinator:
- Accepts test plan definitions (JSON/YAML)
- Queues jobs to Redis
- Manages worker pool scaling
- Aggregates results
- Exposes Prometheus metrics
- REST API for external integration

### 6. Worker (`services/worker`)
Distributed execution unit:
- Consumes jobs from BullMQ queue
- Spawns Playwright browser contexts
- Applies test metadata headers (`traffic_type: internal_testing`)
- Reports progress and results back to orchestrator
- Auto-scales based on queue depth

### 7. API (`services/api`)
Entry point for:
- REST endpoints to trigger tests
- WebSocket for real-time test progress
- Authentication (API keys)
- Integration with CI/CD pipelines

## 🔄 Data Flow

```
1. User submits test plan (via CLI, API, or KMP client)
2. Orchestrator validates plan and creates job
3. Job enqueued in Redis (BullMQ queue)
4. Available worker picks up job
5. Worker executes scenario sequence:
   a. Launch browser (headless or headed)
   b. Navigate to video
   c. Execute user actions (play, pause, seek, resolution change)
   d. Capture metrics (watch time, buffer events, errors)
   e. Send analytics events with metadata headers
   f. Validate expected outcomes
6. Results stream back to orchestrator
7. Metrics exported to Prometheus
8. Results stored in PostgreSQL
9. Grafana dashboards updated in real-time
```

## 📊 Metrics & Observability

### Prometheus Metrics
| Metric | Type | Description |
|--------|------|-------------|
| `videoqa_tests_total` | Counter | Total tests executed |
| `videoqa_tests_duration_seconds` | Histogram | Test duration distribution |
| `videoqa_users_concurrent` | Gauge | Active concurrent users |
| `videoqa_workers_active` | Gauge | Active workers |
| `videoqa_queue_depth` | Gauge | Pending jobs in queue |
| `videoqa_errors_total` | Counter | Error count by type |
| `videoqa_views_tracked` | Counter | Views tracked during tests |
| `videoqa_watch_time_seconds` | Histogram | Watch time distribution |
| `videoqa_buffer_events` | Counter | Buffering events during tests |

### Key Alerts
- `HighErrorRate` — >5% error rate in last 5 minutes
- `QueueBacklog` — queue depth > 100 for > 2 minutes
- `WorkerCascadeFailure` — >3 workers down simultaneously
- `TestFailureThreshold` — >10% test failure rate

## 🔐 Security & Ethics

- **ALL traffic** includes header: `X-Traffic-Type: internal_testing`
- No spoofing, no evasions, no residential proxies
- Uses official APIs where possible (YouTube Data API v3)
- Rate limits enforced on test traffic too (configurable)
- All test accounts are explicitly authorized
- No interaction with content we don't own
- Complete audit trail in PostgreSQL

## 🧪 Test Type Matrix

| Test Type | What It Validates | Concurrency | Duration |
|-----------|-------------------|-------------|----------|
| Single Playback | Basic playback, metrics | 1 | 30s-5m |
| User Journey | Login → Browse → Play → Engage | 1-10 | 5-15m |
| Load (Ramp) | Scaling behavior | 10→10000 | 10-30m |
| Stress | Breaking point | 100→5000 | 5-15m |
| Soak | Endurance over time | 500 | 2-24h |
| Spike | Sudden burst handling | 0→2000 | 2-5m |
| Anti-Abuse | Rate limits, throttling | 1-100 | 10-30m |
| Race Condition | Concurrent edge cases | 2-50 | 1-5m |

## 📁 Tech Stack

| Component | Technology |
|-----------|------------|
| Runtime | Node.js 20+, TypeScript 5+ |
| Browser Automation | Playwright 1.40+ |
| Load Testing | k6 + custom Playwright |
| Queue | BullMQ + Redis 7 |
| Database | PostgreSQL 15+ |
| Container | Docker + Docker Compose |
| Orchestration | Kubernetes (optional) |
| Monitoring | Prometheus + Grafana |
| Client SDK | Kotlin Multiplatform (Android, iOS, Desktop) |
| CI/CD | GitHub Actions |
