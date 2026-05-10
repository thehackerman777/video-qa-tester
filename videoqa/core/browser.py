"""
Browser manager for YouTube QA testing.
Handles stealth configuration, session persistence, and reliable playback.
"""

import asyncio
import json
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from playwright.async_api import (
    async_playwright,
    Browser,
    BrowserContext,
    Page,
)

from .types import Metadata, TestConfig


class YouTubeBrowser:
    """Manages a Playwright browser with stealth config and session persistence."""

    def __init__(self, config: Optional[TestConfig] = None):
        self.config = config or TestConfig()
        self._playwright = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None
        self._session_path: Optional[Path] = None
        self._authenticated = False

    # ---------------------------------------------------------------
    # Lifecycle
    # ---------------------------------------------------------------

    async def start(self, metadata: Optional[Metadata] = None):
        """Launch browser with stealth configuration."""
        self._playwright = await async_playwright().start()

        self._browser = await self._playwright.chromium.launch(
            headless=self.config.headless,
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-web-security",
                "--autoplay-policy=no-user-gesture-required",
                "--disable-features=IsolateOrigins,site-per-process",
                "--disable-setuid-sandbox",
                "--disable-gpu",
            ],
        )

        self._context = await self._browser.new_context(
            viewport={"width": self.config.viewport[0], "height": self.config.viewport[1]},
            user_agent=self.config.user_agent,
            locale=self.config.locale,
            timezone_id="America/New_York",
            permissions=["notifications"],
            extra_http_headers={
                "X-Traffic-Type": "internal_testing",
                "X-Test-Run-ID": metadata.test_run_id if metadata else "unknown",
                "Accept-Language": "en-US,en;q=0.9",
            },
        )

        # Apply stealth init scripts
        await self._apply_stealth()

        # Try to restore session
        if self.config.persist_session:
            await self._restore_session()

        self._page = await self._context.new_page()
        self._page.set_default_timeout(self.config.timeout)
        self._page.set_default_navigation_timeout(self.config.timeout * 2)

        return self._page

    async def stop(self):
        """Clean shutdown."""
        if self.config.persist_session and self._context:
            await self._save_session()

        if self._context:
            await self._context.close()
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()

    # ---------------------------------------------------------------
    # Session management
    # ---------------------------------------------------------------

    def _session_file(self) -> Path:
        session_dir = Path(self.config.session_dir)
        session_dir.mkdir(parents=True, exist_ok=True)
        return session_dir / "youtube_session.json"

    async def _save_session(self):
        """Save browser state (cookies, localStorage) for reuse."""
        if not self._context:
            return
        path = self._session_file()
        try:
            state = await self._context.storage_state()
            with open(path, "w") as f:
                json.dump(state, f)
        except Exception as e:
            print(f"  ⚠ Could not save session: {e}")

    async def _restore_session(self):
        """Restore previously saved browser session."""
        path = self._session_file()
        if not path.exists():
            return
        try:
            with open(path) as f:
                state = json.load(f)
            await self._context.add_cookies(state.get("cookies", []))
            self._authenticated = True
        except Exception as e:
            print(f"  ⚠ Could not restore session: {e}")

    @property
    def is_authenticated(self) -> bool:
        return self._authenticated

    # ---------------------------------------------------------------
    # Stealth — remove automation detection vectors
    # ---------------------------------------------------------------

    async def _apply_stealth(self):
        """Remove Playwright's automation signals that YouTube detects."""
        await self._context.add_init_script("""
        // Remove webdriver flag — this is the #1 detection signal
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined
        });

        // Add realistic chrome runtime
        window.chrome = {
            runtime: {},
            loadTimes: function() {},
            csi: function() {},
            app: {}
        };

        // Override permissions query (YouTube checks this)
        const originalQuery = window.navigator.permissions.query;
        window.navigator.permissions.query = (params) => {
            if (params.name === 'notifications') {
                return Promise.resolve({
                    state: Notification.permission,
                    onchange: null
                });
            }
            return originalQuery(params);
        };

        // Fix plugins array (headless has empty plugins)
        Object.defineProperty(navigator, 'plugins', {
            get: () => [1, 2, 3, 4, 5]
        });

        // Fix languages (headless defaults to en-US only)
        Object.defineProperty(navigator, 'languages', {
            get: () => ['en-US', 'en', 'es']
        });

        // Override webdriver active detection
        if (navigator.webdriver === false) {
            delete navigator.webdriver;
        }
        """)

    # ---------------------------------------------------------------
    # YouTube Interaction
    # ---------------------------------------------------------------

    async def navigate_video(self, url: str, wait_seconds: int = 5):
        """Navigate to a YouTube video page."""
        await self._page.goto(url, wait_until="networkidle")
        await self._page.wait_for_timeout(wait_seconds * 1000)

    async def play_video(self) -> bool:
        """
        Reliable video playback on YouTube.
        Uses multiple strategies: click player, then programmatic play.
        Returns True if playback started.
        """
        log = []

        # Strategy 1: Click the movie player area
        clicked = await self._page.evaluate("""
            () => {
                const selectors = [
                    '#movie_player',
                    '.html5-video-player',
                    'ytd-player',
                    '.ytp-play-button',
                    'button[aria-label*="Play"]'
                ];
                for (const sel of selectors) {
                    const el = document.querySelector(sel);
                    if (el) {
                        el.click();
                        return sel;
                    }
                }
                return null;
            }
        """)
        if clicked:
            log.append(f"clicked {clicked}")
        await self._page.wait_for_timeout(1000)

        # Strategy 2: Mute + programmatic play
        played = await self._page.evaluate("""
            () => {
                const videos = document.querySelectorAll('video');
                let count = 0;
                videos.forEach(v => {
                    try {
                        v.muted = true;
                        const p = v.play();
                        if (p && typeof p.then === 'function') {
                            p.catch(() => {});
                        }
                        count++;
                    } catch(e) {
                        console.error('play error:', e);
                    }
                });
                return count;
            }
        """)

        await self._page.wait_for_timeout(1000)

        # Verify playback
        if played > 0:
            state = await self._check_playback()
            log.append(f"videos_found={played}, paused={state.get('paused')}, time={state.get('currentTime')}")
            return not state.get("paused", True)

        return False

    async def wait_for_watch_time(self, target_seconds: int = 35) -> float:
        """
        Wait for target seconds of watch time, checking periodically.
        Returns actual watch time achieved.
        """
        check_interval = 5
        elapsed = 0

        while elapsed < target_seconds:
            await self._page.wait_for_timeout(check_interval * 1000)
            elapsed += check_interval

            # Check if still playing
            state = await self._check_playback()
            if state.get("paused", True):
                # Try to resume
                await self._page.evaluate("""
                    () => {
                        const v = document.querySelector('video');
                        if (v && v.paused) v.play().catch(() => {});
                    }
                """)
                await self._page.wait_for_timeout(1000)

        # Final check
        final = await self._check_playback()
        return final.get("currentTime", 0)

    async def get_view_count(self) -> int:
        """Extract view count from the YouTube video page."""
        text = await self._page.evaluate("""
            () => {
                const el = document.querySelector(
                    '.view-count, #count, yt-formatted-string.ytd-video-view-count-renderer, '
                    'span[aria-label*="views"]'
                );
                return el ? el.textContent.trim() : null;
            }
        """)
        if not text:
            return 0
        # Parse: "1.2M views" → 1200000
        text = text.lower().replace("views", "").replace(",", "").strip()
        try:
            if "m" in text:
                return int(float(text.replace("m", "")) * 1_000_000)
            if "k" in text:
                return int(float(text.replace("k", "")) * 1_000)
            return int(text)
        except ValueError:
            return 0

    async def screenshot(self, path: str = "/tmp/yt-debug.png"):
        """Take a screenshot for debugging."""
        await self._page.screenshot(path=path, full_page=False)

    async def get_player_state(self) -> dict:
        """Get detailed player state for debugging."""
        return await self._check_playback()

    # ---------------------------------------------------------------
    # Google Login
    # ---------------------------------------------------------------

    async def login_google(self, email: str, password: str) -> bool:
        """Log into Google/YouTube with test account."""
        print(f"  🔑 Logging in as {email}...")

        await self._page.goto("https://accounts.google.com/Login", wait_until="networkidle")
        await self._page.wait_for_timeout(2000)

        # Step 1: Email
        try:
            email_field = await self._page.wait_for_selector(
                "input[type='email'], input[name='identifier']",
                timeout=10000
            )
            await email_field.click()
            await self._page.wait_for_timeout(300)
            await email_field.fill(email)
            await self._page.wait_for_timeout(500)
            await email_field.press("Enter")
            await self._page.wait_for_timeout(3000)
        except Exception as e:
            print(f"  ⚠ Email field error: {e}")
            return False

        # Step 2: Password
        try:
            pass_field = await self._page.wait_for_selector(
                "input[type='password'], input[name='Passwd']",
                timeout=15000
            )
            await pass_field.click()
            await self._page.wait_for_timeout(300)
            await pass_field.fill(password)
            await self._page.wait_for_timeout(500)
            await pass_field.press("Enter")
            await self._page.wait_for_timeout(5000)
        except Exception as e:
            print(f"  ⚠ Password field error: {e}")
            return False

        # Check for 2FA or other challenges
        page_url = self._page.url
        if "myaccount" in page_url or "signin" not in page_url:
            self._authenticated = True
            print("  ✅ Login successful!")

            # Save session
            if self.config.persist_session:
                await self._save_session()

            return True
        else:
            print(f"  ⚠ Login may need further steps (URL: {page_url[:80]}...)")
            return False

    # ---------------------------------------------------------------
    # Channel Scanning
    # ---------------------------------------------------------------

    async def scan_channel(self, channel_handle: str, max_videos: int = 10):
        """Discover videos from a YouTube channel."""
        from .types import ChannelVideo

        # Handle @handle or UC... formats
        if channel_handle.startswith("@"):
            url = f"https://www.youtube.com/{channel_handle}/videos"
        elif channel_handle.startswith("UC"):
            url = f"https://www.youtube.com/channel/{channel_handle}/videos"
        else:
            url = channel_handle

        await self._page.goto(url, wait_until="networkidle")
        await self._page.wait_for_timeout(3000)

        # Scroll to load videos
        for _ in range(3):
            await self._page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await self._page.wait_for_timeout(2000)

        # Extract video links
        videos = await self._page.evaluate(f"""
            () => {{
                const links = document.querySelectorAll('a#video-title, a[href*="/watch?v="]');
                const seen = new Set();
                const result = [];
                for (const link of links) {{
                    const url = link.href;
                    if (seen.has(url)) continue;
                    seen.add(url);
                    const match = url.match(/[?&]v=([^&]+)/);
                    if (!match) continue;
                    result.push({{
                        video_id: match[1],
                        title: link.title || link.textContent.trim() || 'Untitled',
                        url: url,
                        view_count: 0,
                    }});
                    if (result.length >= {max_videos}) break;
                }}
                return result;
            }}
        """)

        return [ChannelVideo(**v) for v in videos]

    # ---------------------------------------------------------------
    # Helpers
    # ---------------------------------------------------------------

    async def _check_playback(self) -> dict:
        """Check current video playback state."""
        return await self._page.evaluate("""
            () => {
                const v = document.querySelector('video');
                if (!v) return { hasVideo: false };
                return {
                    hasVideo: true,
                    paused: v.paused,
                    currentTime: v.currentTime,
                    duration: v.duration,
                    muted: v.muted,
                    volume: v.volume,
                    readyState: ['HaveNothing','HaveMetadata','HaveCurrentData','HaveFutureData','HaveEnoughData'][v.readyState] || v.readyState,
                    networkState: ['Empty','Idle','Loading','Loaded'][v.networkState] || v.networkState,
                    error: v.error ? v.error.message : null,
                    src: !!v.src,
                    buffered: v.buffered.length > 0 ? v.buffered.end(v.buffered.length-1) : 0,
                };
            }
        """)

    def page(self):
        return self._page
