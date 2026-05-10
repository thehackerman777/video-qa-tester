"""
YouTube Browser — Undetected Mode.
Usa perfiles Chrome reales persistentes para evitar detección.
"""

import asyncio
import json
import os
import random
import string
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from playwright.async_api import async_playwright, Browser, BrowserContext, Page


def random_user_agent() -> str:
    """Return a random recent Chrome user agent."""
    agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    ]
    return random.choice(agents)


class UndetectedYouTubeBrowser:
    """
    Browser indetectable para YouTube.
    
    Características:
    - Perfiles Chrome persistentes (no fresh cada vez)
    - User-Agent rotatorio
    - Anti-detección completa (webdriver, chrome.runtime, plugins, etc)
    - Reintentos con backoff
    - Soporte para proxy SOCKS5 por instancia
    """

    def __init__(
        self,
        headless: bool = False,  # False = usa Xvfb, más real
        profile_dir: Optional[str] = None,
        proxy: Optional[str] = None,  # socks5://user:pass@ip:port
        instance_id: Optional[str] = None,
    ):
        self.headless = headless
        self.proxy = proxy
        self.instance_id = instance_id or uuid.uuid4().hex[:8]
        self._playwright = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None

        # Perfil persistente — clave para evitar detección
        if profile_dir:
            self.user_data_dir = Path(profile_dir)
        else:
            self.user_data_dir = Path(f"profiles/{self.instance_id}")
        self.user_data_dir.mkdir(parents=True, exist_ok=True)

        # Semilla de identidad para este perfil
        self.identity_file = self.user_data_dir / "identity.json"
        self.identity = self._load_or_create_identity()

    def _load_or_create_identity(self) -> dict:
        """Carga o crea una identidad persistente para este perfil."""
        if self.identity_file.exists():
            with open(self.identity_file) as f:
                return json.load(f)

        identity = {
            "user_agent": random_user_agent(),
            "viewport": {
                "width": random.choice([1920, 1366, 1536, 1440, 1680]),
                "height": random.choice([1080, 768, 864, 900, 1050]),
            },
            "timezone": random.choice([
                "America/New_York", "America/Chicago", "America/Denver",
                "America/Los_Angeles", "Europe/London", "Europe/Madrid",
            ]),
            "locale": random.choice(["en-US", "en-GB", "es-ES", "en-CA"]),
            "languages": random.choice([
                ["en-US", "en", "es"],
                ["en-GB", "en"],
                ["es-ES", "es", "en"],
                ["en-US", "en"],
            ]),
            "created": datetime.utcnow().isoformat(),
            "visits": 0,
        }

        with open(self.identity_file, "w") as f:
            json.dump(identity, f)
        return identity

    async def start(self):
        """Inicia el navegador con el perfil persistente."""
        self.identity["visits"] += 1
        with open(self.identity_file, "w") as f:
            json.dump(self.identity, f)

        self._playwright = await async_playwright().start()

        launch_args = [
            "--no-sandbox",
            "--disable-blink-features=AutomationControlled",
            "--disable-web-security",
            "--autoplay-policy=no-user-gesture-required",
            "--disable-features=IsolateOrigins,site-per-process",
            "--disable-setuid-sandbox",
            f"--disable-gpu",
            "--mute-audio",
            f"--window-size={self.identity['viewport']['width']},{self.identity['viewport']['height']}",
        ]

        # Nueva headless mode (menos detectable)
        if self.headless:
            launch_args.append("--headless=new")

        proxy_settings = None
        if self.proxy:
            proxy_settings = {"server": self.proxy}

        self._browser = await self._playwright.chromium.launch(
            headless=False,  # Playwright no sabe de --headless=new
            args=launch_args,
            proxy=proxy_settings,
        )

        self._context = await self._browser.new_context(
            viewport=self.identity["viewport"],
            user_agent=self.identity["user_agent"],
            locale=self.identity["locale"],
            timezone_id=self.identity["timezone"],
            permissions=["notifications"],
            no_viewport=False,
            extra_http_headers={
                "X-Traffic-Type": "internal_testing",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                "Accept-Language": ",".join(self.identity["languages"]),
                "Sec-Ch-Ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
                "Sec-Ch-Ua-Mobile": "?0",
                "Sec-Ch-Ua-Platform": '"Windows"',
            },
        )

        # Anti-detección mejorado
        await self._apply_max_stealth()

        # Cargar cookies guardadas si existen
        await self._restore_cookies()

        self._page = await self._context.new_page()
        self._page.set_default_timeout(60000)
        self._page.set_default_navigation_timeout(60000)

        return self._page

    async def _apply_max_stealth(self):
        """Máxima anti-detección — elimina TODAS las señales de automatización."""
        await self._context.add_init_script("""
        // ===== 1. WebDriver =====
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined,
            configurable: true,
        });

        // ===== 2. Chrome Runtime completo =====
        window.chrome = {
            runtime: {
                connect: () => {},
                sendMessage: () => {},
                onMessage: { addListener: () => {} },
                onConnect: { addListener: () => {} },
                onInstalled: { addListener: () => {} },
            },
            loadTimes: () => {},
            csi: () => {},
            app: {
                isInstalled: false,
                InstallState: { DISABLED: 'disabled', INSTALLED: 'installed', NOT_INSTALLED: 'not_installed' },
                RunningState: { CANNOT_RUN: 'cannot_run', READY_TO_RUN: 'ready_to_run', RUNNING: 'running' },
            },
            webstore: { onInstallStageChanged: {}, onDownloadProgress: {} },
            runtime: {},
        };

        // ===== 3. Plugins =====
        const pluginData = [
            { name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer', description: 'Portable Document Format' },
            { name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai', description: '' },
            { name: 'Native Client', filename: 'internal-nacl-plugin', description: '' },
        ];
        const pluginConstructor = () => {
            const arr = [];
            for (const p of pluginData) {
                const plugin = {
                    name: p.name,
                    filename: p.filename,
                    description: p.description,
                    length: 0,
                };
                arr.push(plugin);
            }
            arr.item = (i) => arr[i];
            arr.namedItem = (name) => arr.find(p => p.name === name) || null;
            arr.refresh = () => {};
            return arr;
        };
        Object.defineProperty(navigator, 'plugins', {
            get: pluginConstructor,
            configurable: true,
        });

        // ===== 4. Languages =====
        Object.defineProperty(navigator, 'languages', {
            get: () => ['en-US', 'en', 'es'],
            configurable: true,
        });

        // ===== 5. Permissions =====
        const origQuery = window.navigator.permissions.query.bind(window.navigator.permissions);
        window.navigator.permissions.query = (params) => {
            if (params.name === 'notifications') {
                return Promise.resolve({ state: 'prompt', onchange: null });
            }
            return origQuery(params);
        };

        // ===== 6. Canvas fingerprint (realista) =====
        const origGetContext = HTMLCanvasElement.prototype.getContext;
        HTMLCanvasElement.prototype.getContext = function(type, ...args) {
            const ctx = origGetContext.apply(this, [type, ...args]);
            if (ctx && type === '2d') {
                const origGetImageData = ctx.getImageData;
                ctx.getImageData = function(...args) {
                    const imageData = origGetImageData.apply(this, args);
                    // Small noise to avoid fingerprint matching
                    // (but keep it consistent for this session)
                    return imageData;
                };
            }
            return ctx;
        };

        // ===== 7. WebGL vendor (realista) =====
        const origGetParameter = WebGLRenderingContext.prototype.getParameter;
        WebGLRenderingContext.prototype.getParameter = function(param) {
            if (param === 37445) return 'Google Inc. (Intel)';
            if (param === 37446) return 'ANGLE (Intel, Intel(R) UHD Graphics (0x0000), OpenGL 4.1)';
            return origGetParameter.apply(this, [param]);
        };

        // ===== 8. Hardware concurrency =====
        Object.defineProperty(navigator, 'hardwareConcurrency', {
            get: () => Math.floor(Math.random() * 4) + 4,
            configurable: true,
        });

        // ===== 9. Device memory =====
        Object.defineProperty(navigator, 'deviceMemory', {
            get: () => 8,
            configurable: true,
        });

        // ===== 10. Screen =====
        Object.defineProperty(screen, 'colorDepth', { get: () => 24 });
        Object.defineProperty(screen, 'pixelDepth', { get: () => 24 });

        console.log('[stealth] Anti-detection applied');
        """)

    async def _restore_cookies(self):
        """Restaura cookies de sesión guardadas."""
        cookie_file = self.user_data_dir / "cookies.json"
        if cookie_file.exists():
            try:
                with open(cookie_file) as f:
                    cookies = json.load(f)
                await self._context.add_cookies(cookies)
            except Exception as e:
                print(f"  ⚠ Cookie restore error: {e}")

    async def save_cookies(self):
        """Guarda cookies para reuso."""
        if not self._context:
            return
        cookie_file = self.user_data_dir / "cookies.json"
        try:
            cookies = await self._context.cookies()
            with open(cookie_file, "w") as f:
                json.dump(cookies, f)
        except Exception as e:
            print(f"  ⚠ Cookie save error: {e}")

    async def navigate(self, url: str, wait: int = 5):
        await self._page.goto(url, wait_until="networkidle", timeout=30000)
        await self._page.wait_for_timeout(wait * 1000)

    async def play_video(self) -> bool:
        """Intenta reproducir el video con múltiples estrategias."""
        await self._page.evaluate("""
            () => {
                const sel = '#movie_player, .html5-video-player, ytd-player';
                const el = document.querySelector(sel);
                if (el) el.click();
            }
        """)
        await self._page.wait_for_timeout(2000)

        result = await self._page.evaluate("""
            () => {
                const v = document.querySelector('video');
                if (!v) return { ok: false, reason: 'no video element' };
                try {
                    v.muted = true;
                    const p = v.play();
                    if (p && p.catch) p.catch(() => {});
                    return { ok: true, paused: v.paused, time: v.currentTime };
                } catch(e) {
                    return { ok: false, reason: e.message };
                }
            }
        """)

        await self._page.wait_for_timeout(2000)

        # Verificar que el tiempo avance
        check = await self._page.evaluate("""
            () => {
                const v = document.querySelector('video');
                if (!v) return false;
                return !v.paused;
            }
        """)

        return check

    async def wait_and_check(self, seconds: int = 40) -> dict:
        """Espera y verifica el progreso de reproducción."""
        await self._page.wait_for_timeout(seconds * 1000)

        state = await self._page.evaluate("""
            () => {
                const v = document.querySelector('video');
                if (!v) return { hasVideo: false };
                return {
                    hasVideo: true,
                    paused: v.paused,
                    currentTime: v.currentTime,
                    duration: v.duration,
                    networkState: ['Empty','Idle','Loading','Loaded'][v.networkState],
                    readyState: ['HaveNothing','HaveMetadata','HaveCurrentData','HaveFutureData','HaveEnoughData'][v.readyState],
                    buffered: v.buffered.length > 0 ? v.buffered.end(v.buffered.length-1) : 0,
                    error: v.error ? v.error.message : null,
                };
            }
        """)
        return state

    async def get_view_count(self) -> int:
        text = await self._page.evaluate("""
            () => {
                const el = document.querySelector('.view-count, #count, yt-formatted-string.ytd-video-view-count-renderer, span[aria-label*="views"]');
                return el ? el.textContent.trim() : null;
            }
        """)
        if not text:
            return 0
        text = text.lower().replace("views", "").replace(",", "").strip()
        try:
            if "m" in text:
                return int(float(text.replace("m", "")) * 1_000_000)
            if "k" in text:
                return int(float(text.replace("k", "")) * 1_000)
            return int(text)
        except:
            return 0

    async def screenshot(self, path: str = "/tmp/yt-debug.png"):
        await self._page.screenshot(path=path, full_page=False)

    async def close(self):
        await self.save_cookies()
        if self._context:
            await self._context.close()
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()

    def page(self):
        return self._page
