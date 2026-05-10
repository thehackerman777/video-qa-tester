"""
YouTube Browser v3 — API Interceptor.
Intercepta la respuesta de la API de YouTube para bypassear
el playabilityStatus LOGIN_REQUIRED.
"""

import asyncio
import json
import random
import uuid
from pathlib import Path
from typing import Optional

from playwright.async_api import async_playwright, Browser, BrowserContext, Page, Route


class ForcedYouTubeBrowser:
    """
    Browser que intercepta la API de YouTube para forzar la reproducción.
    
    Estrategia:
    1. Intercepta la request a youtubei/v1/player que contiene playabilityStatus
    2. Modifica la respuesta para cambiar LOGIN_REQUIRED → OK
    3. El video se reproduce aunque no haya sesión
    """

    def __init__(self, headless: bool = True):
        self.headless = headless
        self.instance_id = uuid.uuid4().hex[:8]
        self._playwright = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None

    async def start(self):
        self._playwright = await async_playwright().start()

        self._browser = await self._playwright.chromium.launch(
            headless=self.headless,
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--autoplay-policy=no-user-gesture-required",
                "--disable-web-security",
            ],
        )

        self._context = await self._browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            locale="en-US",
            extra_http_headers={
                "X-Traffic-Type": "internal_testing",
            },
        )

        # Anti-detección
        await self._context.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        window.chrome = { runtime: {} };
        """)

        self._page = await self._context.new_page()
        self._page.set_default_timeout(60000)

        return self._page

    async def start_with_api_intercept(self):
        """
        Inicia el navegador con interceptación de la API de YouTube.
        Esto modifica el playabilityStatus en las respuestas.
        """
        page = await self.start()
        await self._setup_interceptor()
        return page

    async def _setup_interceptor(self):
        """Configura el interceptor de la API de YouTube."""
        
        async def intercept_youtube_api(route: Route):
            url = route.request.url

            # Interceptar la request de player (contiene playabilityStatus)
            if "youtubei/v1/player" in url:
                original_response = await route.fetch()
                body = await original_response.json()
                
                # Modificar playabilityStatus
                if "playabilityStatus" in body:
                    body["playabilityStatus"]["status"] = "OK"
                    body["playabilityStatus"]["reason"] = ""
                    
                    # Asegurar que haya un stream disponible
                    if "streamingData" not in body:
                        body["streamingData"] = {
                            "expiresInSeconds": "3600",
                            "formats": [],
                            "adaptiveFormats": [],
                        }

                # Continuar con la respuesta modificada
                await route.fulfill(
                    status=original_response.status,
                    headers=original_response.headers,
                    body=json.dumps(body),
                    content_type="application/json",
                )
                return

            # También interceptar el ytInitialPlayerResponse en el HTML
            if "watch?v=" in url and route.request.resource_type == "document":
                response = await route.fetch()
                html = await response.text()

                # Modificar ytInitialPlayerResponse en el HTML
                import re
                def fix_player_response(match):
                    try:
                        data = json.loads(match.group(1))
                        if "playabilityStatus" in data:
                            data["playabilityStatus"]["status"] = "OK"
                            data["playabilityStatus"]["reason"] = ""
                        return f"var ytInitialPlayerResponse = {json.dumps(data)}"
                    except:
                        return match.group(0)

                html = re.sub(
                    r'var ytInitialPlayerResponse = ({.*?});',
                    fix_player_response,
                    html,
                    flags=re.DOTALL,
                )

                await route.fulfill(
                    status=response.status,
                    headers=response.headers,
                    body=html,
                    content_type="text/html",
                )
                return

            # Otras requests: pasar sin modificar
            await route.continue_()

        await self._page.route("**/*", intercept_youtube_api)

    async def navigate(self, url: str, wait: int = 5):
        await self._page.goto(url, wait_until="domcontentloaded", timeout=30000)
        await self._page.wait_for_timeout(wait * 1000)

    async def play_video(self) -> bool:
        """Intenta reproducir con fuerza usando los datos interceptados."""
        
        # Click player
        await self._page.evaluate("""
            () => {
                const el = document.querySelector('#movie_player, .html5-video-player, ytd-player');
                if (el) el.click();
            }
        """)
        await self._page.wait_for_timeout(2000)

        # Forzar play con video.muted
        played = await self._page.evaluate("""
            () => {
                const v = document.querySelector('video');
                if (!v) return false;
                v.muted = true;
                try {
                    const p = v.play();
                    if (p && p.catch) p.catch(() => {});
                    return true;
                } catch(e) {
                    return false;
                }
            }
        """)

        if not played:
            return False

        # Esperar y verificar progreso
        await self._page.wait_for_timeout(5000)

        state = await self._page.evaluate("""
            () => {
                const v = document.querySelector('video');
                if (!v) return { hasVideo: false };
                return {
                    hasVideo: true,
                    paused: v.paused,
                    currentTime: v.currentTime,
                    readyState: ['HaveNothing','HaveMetadata','HaveCurrentData','HaveFutureData','HaveEnoughData'][v.readyState],
                    networkState: ['Empty','Idle','Loading','Loaded'][v.networkState],
                    duration: v.duration,
                    buffered: v.buffered.length > 0 ? v.buffered.end(v.buffered.length-1) : 0,
                };
            }
        """)

        return state.get("currentTime", 0) > 0

    async def wait_and_verify(self, seconds: int = 40) -> dict:
        """Espera y verifica el progreso."""
        await self._page.wait_for_timeout(seconds * 1000)
        return await self._page.evaluate("""
            () => {
                const v = document.querySelector('video');
                if (!v) return { hasVideo: false };
                return {
                    hasVideo: true,
                    paused: v.paused,
                    currentTime: v.currentTime,
                    duration: v.duration,
                    networkState: ['Empty','Idle','Loading','Loaded'][v.networkState],
                    buffered: v.buffered.length > 0 ? v.buffered.end(v.buffered.length-1) : 0,
                };
            }
        """)

    async def screenshot(self, path: str = "/tmp/yt-debug.png"):
        await self._page.screenshot(path=path, full_page=False)

    async def close(self):
        if self._context:
            await self._context.close()
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()

    def page(self):
        return self._page
