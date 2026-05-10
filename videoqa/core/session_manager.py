"""
Multi-Session Manager — gestiona múltiples perfiles de YouTube.
Cada perfil representa un "usuario" diferente con sus propias cookies.
"""

import asyncio
import csv
import json
import os
import random
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from videoqa.core.browser import UndetectedYouTubeBrowser


class SessionManager:
    """
    Gestiona múltiples sesiones de YouTube (cada una = un usuario diferente).
    
    Las sesiones se guardan en profiles/session-N/cookies.json
    Cada sesión tiene:
    - cookies.json → cookies de YouTube autenticadas
    - identity.json → metadatos de identidad (user-agent, viewport, etc)
    """

    def __init__(self, base_dir: str = "profiles"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def list_sessions(self) -> list[dict]:
        """Lista todas las sesiones disponibles."""
        sessions = []
        for d in sorted(self.base_dir.glob("session-*")):
            if d.is_dir():
                cookie_file = d / "cookies.json"
                identity_file = d / "identity.json"
                sessions.append({
                    "id": d.name,
                    "path": str(d),
                    "has_cookies": cookie_file.exists(),
                    "has_identity": identity_file.exists(),
                    "last_used": datetime.fromtimestamp(
                        d.stat().st_mtime
                    ).isoformat() if d.stat().st_mtime else "never",
                })
        return sessions

    def count(self) -> int:
        """Número de sesiones disponibles."""
        return len(list(self.base_dir.glob("session-*/cookies.json")))

    def import_netscape_cookies(self, netscape_file: str, session_id: Optional[str] = None):
        """
        Importa cookies en formato Netscape a una sesión.
        
        Formato Netscape (exportado por extensiones como cookies.txt):
        .youtube.com	TRUE	/	TRUE	expires	name	value
        """
        if not session_id:
            existing = len(list(self.base_dir.glob("session-*")))
            session_id = f"session-{existing + 1:03d}"

        session_dir = self.base_dir / session_id
        session_dir.mkdir(parents=True, exist_ok=True)

        cookies_playwright = []
        with open(netscape_file) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split("\t")
                if len(parts) >= 7:
                    domain = parts[0]
                    secure = parts[3]
                    expires = parts[4]
                    name = parts[5]
                    value = " ".join(parts[6:])

                    cookie = {
                        "name": name,
                        "value": value,
                        "domain": domain,
                        "path": "/",
                        "expires": int(expires) if expires != "0" else -1,
                        "httpOnly": False,
                        "secure": secure == "TRUE",
                        "sameSite": "None" if secure == "TRUE" else "Lax",
                    }
                    cookies_playwright.append(cookie)

        cookie_file = session_dir / "cookies.json"
        with open(cookie_file, "w") as f:
            json.dump(cookies_playwright, f, indent=2)

        # Create random identity
        self._create_identity(session_dir)

        print(f"✅ Imported session {session_id} ({len(cookies_playwright)} cookies)")
        return session_id

    def create_batch_from_netscape_files(self, pattern: str = "cookies_*.txt"):
        """
        Importa múltiples archivos de cookies a la vez.
        Ej: python3 -c "from videoqa.core.session_manager import SessionManager; SessionManager().create_batch_from_netscape_files('cookies_*.txt')"
        """
        from glob import glob
        files = sorted(glob(pattern))
        if not files:
            print(f"No files matching {pattern}")
            return []

        sessions = []
        for i, f in enumerate(files):
            sid = f"session-{i+1:03d}"
            try:
                self.import_netscape_cookies(f, sid)
                sessions.append(sid)
            except Exception as e:
                print(f"❌ Error importing {f}: {e}")

        print(f"\n✅ Imported {len(sessions)} sessions")
        return sessions

    def get_random_session(self) -> Optional[dict]:
        """Obtiene una sesión aleatoria."""
        sessions = self.list_sessions()
        valid = [s for s in sessions if s["has_cookies"]]
        if not valid:
            return None
        return random.choice(valid)

    def _create_identity(self, session_dir: Path):
        """Crea una identidad aleatoria para la sesión (evita fingerprinting)."""
        identity = {
            "created": datetime.utcnow().isoformat(),
            "user_agent": random.choice([
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/123.0.0.0 Safari/537.36",
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
            ]),
            "viewport": random.choice([
                {"width": 1920, "height": 1080},
                {"width": 1366, "height": 768},
                {"width": 1536, "height": 864},
                {"width": 1440, "height": 900},
            ]),
            "locale": random.choice(["en-US", "en-GB", "es-ES", "en-CA"]),
            "timezone": random.choice([
                "America/New_York", "America/Chicago", 
                "America/Bogota", "America/Los_Angeles",
            ]),
        }
        with open(session_dir / "identity.json", "w") as f:
            json.dump(identity, f, indent=2)


class ChannelScanner:
    """Escanea un canal de YouTube para obtener videos y su popularidad."""

    def scan_videos(self, channel_url: str, max_videos: int = 50) -> list[dict]:
        """
        Escanea el canal y devuelve videos ordenados por popularidad.
        """
        import asyncio as aio
        
        async def _scan():
            browser = UndetectedYouTubeBrowser(headless=True)
            try:
                page = await browser.start()
                await page.goto(channel_url, wait_until="domcontentloaded", timeout=30000)
                await page.wait_for_timeout(3000)

                # Scroll to load all videos
                for _ in range(5):
                    await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    await page.wait_for_timeout(2000)

                # Get all video links with metadata
                videos = await page.evaluate(f"""
                    () => {{
                        const links = document.querySelectorAll("a#video-title, a[href*='/watch?v=']");
                        const seen = new Set();
                        const result = [];
                        for (const link of links) {{
                            const url = link.href;
                            if (seen.has(url)) continue;
                            seen.add(url);
                            const m = url.match(/[?&]v=([^&]+)/);
                            if (!m) continue;
                            
                            // Try to get view count from parent element
                            const item = link.closest("ytd-video-renderer, ytd-grid-video-renderer, ytd-video-meta-block");
                            let views = 0;
                            let metaText = "";
                            if (item) {{
                                const meta = item.querySelector("#metadata-line span, .metadata-item");
                                if (meta) metaText = meta.textContent.trim();
                            }}
                            
                            result.push({{
                                id: m[1],
                                title: (link.title || link.textContent.trim()).substring(0, 100),
                                url: url.split("&")[0],
                                meta: metaText,
                            }});
                            if (result.length >= {max_videos}) break;
                        }}
                        return result;
                    }}
                """)
                return videos

            finally:
                await browser.close()

        return aio.run(_scan())

    def extract_view_count(self, meta_text: str) -> int:
        """Extrae el número de vistas del texto de metadata."""
        import re
        text = meta_text.lower().replace(",", "")
        match = re.search(r"([\d.]+)\s*([mk]?)\s*views?", text)
        if match:
            num = float(match.group(1))
            unit = match.group(2)
            if unit == "m":
                return int(num * 1_000_000)
            elif unit == "k":
                return int(num * 1_000)
            return int(num)
        return 0


class JobManager:
    """Mantiene el estado de las tareas de distribución para la UI."""
    _jobs = {}

    @classmethod
    def create_job(cls, job_id, total_views):
        cls._jobs[job_id] = {
            "id": job_id,
            "status": "RUNNING",
            "total_views": total_views,
            "completed_views": 0,
            "failed_views": 0,
            "pending_views": total_views,
            "active_workers": 0,
            "start_time": time.time(),
            "results": [],
            "errors": []
        }
        return cls._jobs[job_id]

    @classmethod
    def get_job(cls, job_id):
        return cls._jobs.get(job_id)

    @classmethod
    def update_progress(cls, job_id, result):
        job = cls._jobs.get(job_id)
        if not job: return
        job["results"].append(result)
        job["pending_views"] -= 1
        if result.get("success"):
            job["completed_views"] += 1
        else:
            job["failed_views"] += 1
            if result.get("error"):
                job["errors"].append(result["error"])
        
        if job["pending_views"] == 0:
            job["status"] = "COMPLETED"

    @classmethod
    def update_active_workers(cls, job_id, delta):
        job = cls._jobs.get(job_id)
        if job:
            job["active_workers"] += delta


class ViewDistributor:
    """
    Distribuye vistas equitativamente entre los videos.
    
    Estrategia:
    - Toma los N videos más populares
    - Asigna cada sesión (cookie) a un video
    - Cada sesión ve el video por 45-60s
    """

    def __init__(self, session_manager: SessionManager):
        self.sessions = session_manager

    async def distribute_views(self, videos: list[dict], total_views: int, job_id: str = None, time_limit_minutes: float = None, concurrency: int = None):
        """
        Distribuye 'total_views' vistas entre los videos.
        
        Args:
            videos: Lista de videos con id, title, url y opcionalmente 'weight'
            total_views: Número total de vistas a generar
            job_id: ID para reportar a JobManager
            time_limit_minutes: Límite de tiempo en minutos
            concurrency: Número de workers paralelos
        """
        available_sessions = self.sessions.list_sessions()
        valid_sessions = [s for s in available_sessions if s["has_cookies"]]

        if not valid_sessions:
            print("❌ No sessions available. Import cookies first.")
            if job_id:
                job = JobManager.get_job(job_id)
                if job: job["status"] = "FAILED"
            return []

        if not job_id:
            job_id = uuid.uuid4().hex[:8]
            JobManager.create_job(job_id, total_views)

        print(f"\n{'='*50}")
        print(f"📊 DISTRIBUCIÓN DE VISTAS (Job: {job_id})")
        print(f"   Sessions: {len(valid_sessions)}")
        print(f"   {total_views} visits to distribute")
        print(f"   {len(videos)} videos available")
        print(f"{'='*50}\n")

        # Estrategia proporcional (si hay weights) o equitativa
        assigned = []
        has_weights = all("weight" in v for v in videos)
        
        if has_weights:
            total_weight = sum(v.get("weight", 1) for v in videos)
            counts = [int(total_views * (v.get("weight", 1) / total_weight)) for v in videos]
            # Ajustar redondeos
            while sum(counts) < total_views:
                counts[0] += 1
            
            video_list = []
            for v, c in zip(videos, counts):
                video_list.extend([v] * c)
            random.shuffle(video_list)
        else:
            video_list = [videos[i % len(videos)] for i in range(total_views)]

        # Asignar sesiones
        session_idx = 0
        for i, video in enumerate(video_list):
            session = valid_sessions[session_idx % len(valid_sessions)]
            assigned.append({
                "view_id": i + 1,
                "session": session["id"],
                "session_dir": session["path"],
                "video_id": video["id"],
                "video_title": video["title"][:50],
                "video_url": video["url"],
                "job_id": job_id
            })
            session_idx += 1

        # Configurar Concurrencia
        if not concurrency:
            if time_limit_minutes:
                # Cada vista toma aprox 60s
                concurrency = max(1, int((total_views * 1.0) / time_limit_minutes) + 1)
            else:
                concurrency = 3 # default 3 workers

        concurrency = min(concurrency, total_views)
        
        print(f"🚀 Iniciando {concurrency} workers concurrentes...")
        
        queue = asyncio.Queue()
        for a in assigned:
            queue.put_nowait(a)

        async def worker():
            while True:
                try:
                    assignment = queue.get_nowait()
                except asyncio.QueueEmpty:
                    break
                
                JobManager.update_active_workers(job_id, 1)
                try:
                    print(f"\n  [{assignment['view_id']}/{total_views}] {assignment['session']} → {assignment['video_title']}")
                    result = await self._execute_view(assignment)
                    JobManager.update_progress(job_id, result)
                except Exception as e:
                    JobManager.update_progress(job_id, {"success": False, "error": str(e), "view_id": assignment["view_id"], "watch_time": 0})
                finally:
                    JobManager.update_active_workers(job_id, -1)
                    queue.task_done()

        workers = []
        for i in range(concurrency):
            # REQUERIMIENTO QA: "cada worker debe iniciar un segundo despues del anterior"
            if i > 0:
                await asyncio.sleep(1.0)
            task = asyncio.create_task(worker())
            workers.append(task)
            
        await asyncio.gather(*workers)
        
        job = JobManager.get_job(job_id)
        if job:
            passed = job["completed_views"]
            failed = job["failed_views"]
            results = job["results"]
        else:
            passed = failed = 0
            results = []

        print(f"\n{'='*50}")
        print(f"📊 RESULTADOS (Job: {job_id})")
        print(f"   Exitosas: {passed}")
        print(f"   Fallidas: {failed}")
        print(f"{'='*50}")

        return results

    async def _execute_view(self, assignment: dict) -> dict:
        """Ejecuta una vista individual."""
        session_dir = assignment["session_dir"]
        url = assignment["video_url"]
        watch_time = random.randint(40, 60)

        browser = UndetectedYouTubeBrowser(
            headless=True,
            profile_dir=session_dir,
            instance_id=assignment["session"],
        )

        result = {
            "view_id": assignment["view_id"],
            "session": assignment["session"],
            "video": assignment["video_title"],
            "success": False,
            "watch_time": 0,
            "error": None,
        }

        try:
            page = await browser.start()
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(random.randint(3000, 5000))

            # Play
            await page.evaluate(
                'document.querySelector("#movie_player, .html5-video-player, ytd-player")?.click()'
            )
            await page.wait_for_timeout(2000)
            await page.evaluate(
                'const v = document.querySelector("video"); if(v){v.muted=true;v.play()}'
            )
            await page.wait_for_timeout(3000)

            # Verify
            t = await page.evaluate(
                '() => { const v = document.querySelector("video"); return v ? v.currentTime : 0 }'
            )
            if t == 0:
                result["error"] = "Time not progressing"
                return result

            # Watch
            chunks = watch_time // 5
            for _ in range(chunks):
                await page.wait_for_timeout(5000)
                await page.evaluate(
                    'const v = document.querySelector("video"); if(v && v.paused) v.play()'
                )

            final = await page.evaluate(
                '() => { const v = document.querySelector("video"); return v ? v.currentTime : 0 }'
            )
            result["success"] = True
            result["watch_time"] = final

            # Random delay between views (human-like)
            delay = random.uniform(2, 5)
            await page.wait_for_timeout(int(delay * 1000))

        except Exception as e:
            result["error"] = str(e)[:100]
        finally:
            await browser.close()

        return result
