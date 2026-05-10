# 🎬 Video QA Tester (Python)

**Automated QA testing for YouTube and video platforms.**

Simulates real user behavior for legitimate testing of your own content.
All traffic is marked as `internal_testing`.

> ⚠️ **For testing your own content only.**

## ✨ Features

- **Authenticated testing** — Login to YouTube to avoid bot detection
- **Session persistence** — Login once, reuse sessions
- **View counting validation** — Watch 35s+ to trigger YouTube view counting
- **Channel scanning** — Discover all videos from a channel
- **Load testing** — 100+ concurrent users
- **Stealth browser** — Removes automation detection signals
- **Debug mode** — See full player state, screenshots

## 🚀 Quick Start

```bash
# Install
pip install -r requirements.txt
playwright install chromium

# 1. Login (needed to bypass YouTube's bot detection)
python -m videoqa.cli.main login --email your-account@gmail.com

# 2. Test a single video
python -m videoqa.cli.main test "https://www.youtube.com/watch?v=YOUR_VIDEO"

# 3. Scan a channel
python -m videoqa.cli.main scan "@YourChannel"

# 4. Run 10 users
python -m videoqa.cli.main loadtest "https://www.youtube.com/watch?v=YOUR_VIDEO" --users 10
```

## 📋 Commands

| Command | Description |
|---------|-------------|
| `test <url>` | Test a single video — plays for 35s |
| `scan <channel>` | Discover videos from a channel |
| `loadtest <url>` | Run concurrent users against a video |
| `login` | Login to Google and save session |
| `debug <url>` | Show detailed player state |
| `status` | Check saved session |
| `clear-session` | Remove saved session |

## 🛡️ How It Works

1. **Login first** — YouTube blocks unauthenticated headless browsers with "Sign in to confirm you're not a bot". Login once, session is saved.
2. **Stealth mode** — Removes `navigator.webdriver`, adds realistic browser fingerprints.
3. **Play + wait** — Clicks the player, calls `video.play()` programmatically, waits 35s+ for YouTube's view threshold.
4. **Session reuse** — Saved cookies/storage mean subsequent tests don't need login.

## 🏗️ Structure

```
videoqa/
├── core/
│   ├── types.py      # Data types & configs
│   └── browser.py    # YouTubeBrowser — stealth, sessions, playback
├── cli/
│   └── main.py       # All CLI commands
```

## 🔧 Configuration

| Env var | Default | Description |
|---------|---------|-------------|
| `YT_EMAIL` | — | YouTube test account email |
| `YT_PASS` | — | YouTube test account password |
| `VIDEOQA_HEADLESS` | `true` | Run headless |
| `VIDEOQA_BROWSERS` | `10` | Max concurrent browsers |

## 📊 Debugging

```bash
# Show detailed player state
python -m videoqa.cli.main debug "https://www.youtube.com/watch?v=YOUR_VIDEO" --headed

# Check if session is valid
python -m videoqa.cli.main status
```
