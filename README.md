# 🎬 Video QA Tester

**Legitimate QA automation for video streaming platforms.**

Automated testing system for YouTube-like platforms. Simulates real user behavior to validate **playback**, **analytics**, **anti-abuse**, and **load handling**. Designed for internal QA — all traffic is clearly marked as `internal_testing`.

> ⚠️ **Ethical Use Only**
> This system is for **legitimate QA testing of platforms you own or have explicit permission to test**.
> - ✅ Used on your own infrastructure
> - ✅ All traffic marked as internal testing
> - ❌ No bot evasion, no spoofing, no fraud
> - ❌ Not for inflating metrics or bypassing protections

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| 🧪 **User Simulation** | Play, pause, seek, resolution change, like, comment, subscribe |
| 📡 **Channel Scan** | Discover all videos from a YouTube channel via API or scraping |
| 📊 **Analytics Validation** | Verify view count, watch time, engagement metrics |
| 🛡️ **Anti-Abuse Testing** | Validate rate limits, throttling, suspicious session detection |
| 🚀 **Load Testing** | 100–10,000 concurrent users with ramp-up |
| 📱 **Multi-Platform** | CLI, KMP client (Android/Desktop), REST API |
| 📈 **Observability** | Prometheus metrics + Grafana dashboard |
| 🐳 **Containerized** | Docker Compose for complete stack |
| 🔄 **Distributed Workers** | BullMQ + Redis for job queue |

## 🚀 Quick Start

### Prerequisites

- Node.js 20+
- npm 9+
- Docker & Docker Compose (for full stack)
- YouTube Data API Key (optional, for channel scanning)

### 1. Install

```bash
git clone https://github.com/your-org/video-qa-tester.git
cd video-qa-tester

# Install dependencies
npm install

# Build packages
npm run build
```

### 2. Run a quick test

```bash
# Test a single video
npm run cli test "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

# With a specific scenario
npm run cli test "https://www.youtube.com/watch?v=dQw4w9WgXcQ" --scenario full

# Debug mode
npm run cli test "https://www.youtube.com/watch?v=dQw4w9WgXcQ" --debug
```

### 3. Scan a YouTube channel

```bash
# Via channel ID
npm run cli scan "UC_x5XG1OV2P6uZZ5FSM9Ttw" --api-key YOUR_API_KEY

# Via channel handle
npm run cli scan "@ChannelName" --api-key YOUR_API_KEY --max-videos 20
```

### 4. Run a load test

```bash
# 100 concurrent users
npm run cli loadtest "https://www.youtube.com/watch?v=dQw4w9WgXcQ" --users 100 --duration 60

# 1000 users with custom ramp-up
npm run cli loadtest "https://www.youtube.com/watch?v=dQw4w9WgXcQ" --users 1000 --ramp-up 60 --duration 300
```

### 5. Run anti-abuse tests

```bash
npm run cli anti-abuse "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
```

## 🏗️ Architecture

```
┌──────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│   CLI / KMP App  │────▶│  Orchestrator    │────▶│  Worker Pool     │
│  (test triggers) │     │  (job scheduler) │     │  (Playwright)    │
└──────────────────┘     └────────┬─────────┘     └────────┬─────────┘
                                  │                        │
                          ┌───────▼───────┐        ┌───────▼───────┐
                          │     Redis     │        │  Platform     │
                          │  (BullMQ)     │        │  Under Test   │
                          └───────┬───────┘        └───────┬───────┘
                                  │                        │
                          ┌───────▼───────┐                │
                          │  PostgreSQL   │◀───────────────┘
                          │  (results)    │
                          └───────────────┘
```

### Components

| Package | Description |
|---------|-------------|
| `packages/core` | Core testing engine: browser pool, scenario runner, analytics validator, anti-abuse tester |
| `packages/cli` | Command-line interface for all testing operations |
| `packages/kmp-client` | Kotlin Multiplatform client for Android, Desktop, iOS |
| `services/orchestrator` | Central coordinator with REST API, job queue, Prometheus metrics |
| `services/worker` | Distributed worker that runs Playwright tests |
| `monitoring/` | Grafana dashboards + Prometheus alert rules |

### Test Scenarios

| Scenario | Description | Category |
|----------|-------------|----------|
| `basic` | Navigate, play, pause, resume, seek | Playback |
| `full` | Login, play, change resolution, like, comment, subscribe | User Journey |
| `seek-heavy` | 5+ seeks in rapid succession | Playback |
| `resolution-hopper` | Switch through all available resolutions | Playback |
| `anti-abuse` | Rapid views and actions to trigger rate limits | Anti-Abuse |

## 🐳 Docker Deployment

Full stack with Docker Compose:

```bash
# Copy env and customize
cp .env.example .env
# Edit .env with your settings

# Start everything
docker compose up -d

# Check logs
docker compose logs -f orchestrator worker

# Access:
# - Orchestrator API: http://localhost:3000
# - Grafana: http://localhost:3001 (admin/admin)
# - Prometheus: http://localhost:9090
```

### Scale workers

```bash
docker compose up -d --scale worker=10
```

## ☸️ Kubernetes Deployment

See `k8s/manifests/` for Kubernetes manifests.

```bash
kubectl apply -k k8s/manifests/
kubectl scale deployment videoqa-worker --replicas=20
```

## 📊 Monitoring

### Prometheus Metrics

| Metric | Type | Description |
|--------|------|-------------|
| `videoqa_tests_total` | Counter | Tests by status (passed/failed/error) |
| `videoqa_test_duration_seconds` | Histogram | Test duration buckets |
| `videoqa_users_concurrent` | Gauge | Active concurrent test users |
| `videoqa_workers_active` | Gauge | Active workers |
| `videoqa_queue_depth` | Gauge | Pending jobs in queue |
| `videoqa_errors_total` | Counter | Errors by type |
| `videoqa_views_tracked` | Counter | Views tracked during tests |
| `videoqa_watch_time_seconds` | Counter | Total watch time accumulated |

### Grafana Dashboards

Access at `http://localhost:3001` (default: admin/admin).

The main dashboard shows:
- Test pass/fail rates
- Error rates and types
- Test duration distribution (P50, P95, P99)
- Active users and queue depth
- Worker status
- Watch time accumulated
- Scenario performance table
- Active alerts

### Alert Rules

| Alert | Condition | Severity |
|-------|-----------|----------|
| HighErrorRate | >5% errors in 5m | Warning |
| CriticalErrorRate | >20% errors in 1m | Critical |
| QueueBacklog | >100 jobs for >2m | Warning |
| WorkerDown | No active workers | Critical |
| WorkerCascadeFailure | Multiple workers offline | Critical |
| SlowTests | P99 > 120s | Warning |
| ThroughputDrop | Throughput drops 50% | Warning |

## 🔧 Configuration

### CLI Configuration

```bash
# Set a YouTube API key
videoqa config set youtubeApiKey YOUR_KEY

# Set default concurrency
videoqa config set defaultConcurrency 50

# List current config
videoqa config list
```

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ORCHESTRATOR_API_KEY` | `dev-key-change-me` | API key for orchestrator |
| `REDIS_URL` | `redis://localhost:6379` | Redis connection |
| `DATABASE_URL` | — | PostgreSQL (optional) |
| `YOUTUBE_API_KEY` | — | YouTube Data API v3 key |
| `LOG_LEVEL` | `info` | Log level |
| `DEFAULT_CONCURRENCY` | `10` | Default concurrent users |
| `MAX_BROWSERS` | `20` | Max browser pool size |

## 📱 KMP Client

The Kotlin Multiplatform client lets you trigger tests from Android, Desktop, or iOS apps.

```kotlin
// Android/Desktop/iOS
val client = VideoQAClient(
    QaClientConfig(
        orchestratorUrl = "http://your-server:3000",
        apiKey = "your-api-key"
    )
)

// Run a test
val result = client.runTest(
    TestPlan(
        name = "My Test",
        videoUrl = "https://youtube.com/watch?v=...",
        scenario = "full",
        runOnDevice = false
    )
)
```

See `packages/kmp-client/` for the full Gradle project.

## 📁 Project Structure

```
video-qa-tester/
├── README.md
├── .env.example
├── docker-compose.yml
├── package.json
├── packages/
│   ├── core/           # Testing engine (TypeScript)
│   │   └── src/
│   │       ├── engine/    # Browser pool, scenario runner
│   │       ├── scenarios/ # Test scenario definitions
│   │       ├── analytics/ # Analytics validator
│   │       ├── antiabuse/ # Anti-abuse tester
│   │       ├── metrics/   # Metrics collector
│   │       └── utils/     # Logger, metadata
│   ├── cli/            # CLI tool
│   │   └── src/commands/
│   └── kmp-client/     # Kotlin Multiplatform client
│       └── shared/src/
│           ├── commonMain/
│           ├── androidMain/
│           ├── iosMain/
│           └── jvmMain/
├── services/
│   ├── orchestrator/   # REST API + job queue
│   └── worker/         # Distributed test workers
├── docker/
│   ├── Dockerfile.orchestrator
│   └── Dockerfile.worker
├── k8s/
│   └── manifests/      # Kubernetes manifests
├── monitoring/
│   ├── prometheus/     # Prometheus config + alerts
│   └── grafana/        # Grafana dashboards + datasources
└── scripts/
    ├── setup.sh        # Quick setup script
    └── deploy.sh       # Deploy to VPS/K8s
```

## 🔒 Security & Ethics

- **ALL traffic** includes headers: `X-Traffic-Type: internal_testing` and `X-Test-Run-ID`
- No IP rotation, no residential proxies, no fingerprint spoofing
- Uses YouTube Data API v3 for channel discovery (when configured)
- All test accounts must be explicitly authorized
- Rate limits apply even to test traffic
- Complete audit trail in Redis/PostgreSQL

## 🧪 What This System Validates

### Playback Engine
- Video playback starts correctly
- Seek operations work (forward/backward)
- Resolution switching completes
- Pause/resume cycle functions
- Playback speed changes work

### Analytics Pipeline
- View count increments correctly
- Watch time is recorded accurately
- Minimum playback duration for valid views
- Engagement events (likes, comments) tracked
- Analytics events marked with test metadata

### Anti-Abuse Systems
- Rate limiting on rapid views
- Concurrent session limits per user
- Excessive seek throttling
- Short view filtering (< 2 seconds)
- API rate limiting

### Load Handling
- Scaling under concurrent load
- Queue management under pressure
- Resource usage under stress
- Recovery after load spike

### CDN & Caching
- Video segments load correctly
- Buffering events are minimal
- Resolution switching bandwidth management

## 🤝 Contributing

1. Fork the repo
2. Create your feature branch (`git checkout -b feature/amazing`)
3. Commit (`git commit -m 'Add amazing feature'`)
4. Push (`git push origin feature/amazing`)
5. Open a PR

## 📄 License

MIT — see [LICENSE](LICENSE)

## ⚠️ Disclaimer

This tool is for **legitimate QA testing only**. The authors are not responsible for misuse. Always:
- Test only platforms you own or have permission to test
- Do not use for view inflation, metric manipulation, or fraud
- Respect rate limits and terms of service
- Follow platform guidelines for automated testing
