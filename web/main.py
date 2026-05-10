#!/usr/bin/env python3
"""
Video QA Tester — Web Interface v2
FastAPI + HTMX + Ventriloc Design
"""

import asyncio
import json
import logging
import os
import sys
import traceback
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, Request, Form, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

sys.path.insert(0, str(Path(__file__).parent.parent))
from videoqa.core.session_manager import SessionManager, ChannelScanner, ViewDistributor

# ============================================================
# Logging
# ============================================================
logging.basicConfig(
    level=logging.DEBUG if os.environ.get("DEBUG") else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("videoqa-web")

app = FastAPI(title="Video QA Tester", version="2.0")
BASE_DIR = Path(__file__).parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

# Services
session_mgr = SessionManager()
scanner = ChannelScanner()

# Persistence: save results to disk
RESULTS_FILE = Path("data/test_results.json")
RESULTS_FILE.parent.mkdir(exist_ok=True)
running_tasks = {}

def load_results():
    if RESULTS_FILE.exists():
        try:
            return json.loads(RESULTS_FILE.read_text())
        except:
            return []
    return []

def save_results(results):
    RESULTS_FILE.write_text(json.dumps(results[-200:], indent=2))

test_results = load_results()


# ============================================================
# Routes
# ============================================================

def ctx(page: str, request: Request, **extra):
    return {
        "request": request,
        "page": page,
        "sessions": session_mgr.list_sessions(),
        "results": test_results[-20:],
        "running": len(running_tasks),
        **extra,
    }


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    logger.info(f"Dashboard page loaded (sessions={len(session_mgr.list_sessions())})")
    return templates.TemplateResponse(request, "index.html", ctx("dashboard", request))


@app.get("/sessions", response_class=HTMLResponse)
async def sessions_page(request: Request):
    return templates.TemplateResponse(request, "sessions.html", ctx("sessions", request))


@app.get("/channels", response_class=HTMLResponse)
async def channels_page(request: Request):
    return templates.TemplateResponse(request, "channels.html", ctx("channels", request))


@app.get("/test", response_class=HTMLResponse)
async def test_page(request: Request):
    return templates.TemplateResponse(request, "test.html", ctx("test", request))


@app.get("/logs", response_class=HTMLResponse)
async def logs_page(request: Request):
    """View recent server logs."""
    log_path = Path("/tmp/videoqa-web.log")
    logs_text = ""
    if log_path.exists():
        logs_text = log_path.read_text()[-5000:]
    return templates.TemplateResponse(request, "logs.html", ctx("logs", request, logs=logs_text))


# ============================================================
# API: Scanner
# ============================================================

@app.post("/api/scan")
async def scan_channel(
    channel: str = Form(...),
    max_videos: int = Form(50),
    search: str = Form(""),
    sort: str = Form("views"),
):
    logger.info(f"Scanning channel: {channel} (max={max_videos}, sort={sort})")
    try:
        if channel.startswith("@"):
            url = f"https://www.youtube.com/{channel}/videos"
        elif channel.startswith("UC"):
            url = f"https://www.youtube.com/channel/{channel}/videos"
        else:
            url = channel

        videos = await asyncio.to_thread(scanner.scan_videos, url, max_videos)
        logger.info(f"Scanned {len(videos)} videos from {channel}")

        for v in videos:
            v["views"] = scanner.extract_view_count(v.get("meta", ""))

        if sort == "views":
            videos.sort(key=lambda v: v["views"], reverse=True)

        if search:
            videos = [v for v in videos if search.lower() in v["title"].lower()]

        return JSONResponse({"status": "ok", "total": len(videos), "videos": videos[:max_videos]})

    except Exception as e:
        logger.error(f"Scan failed: {e}\n{traceback.format_exc()}")
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


# ============================================================
# API: Sessions
# ============================================================

@app.post("/api/sessions/upload")
async def upload_cookies(file: UploadFile = File(...)):
    logger.info(f"Uploading cookies: {file.filename}")
    try:
        content = await file.read()
        fname = f"/tmp/uploaded_cookies_{uuid.uuid4().hex[:8]}.txt"
        with open(fname, "wb") as f:
            f.write(content)
        sid = session_mgr.import_netscape_cookies(fname)
        logger.info(f"Created session: {sid}")
        return JSONResponse({"status": "ok", "session": sid})
    except Exception as e:
        logger.error(f"Upload failed: {e}")
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


@app.post("/api/sessions/paste")
async def paste_cookies(cookies: str = Form(...)):
    logger.info("Pasting cookies from textarea")
    try:
        fname = f"/tmp/pasted_cookies_{uuid.uuid4().hex[:8]}.txt"
        with open(fname, "w") as f:
            f.write(cookies)
        sid = session_mgr.import_netscape_cookies(fname)
        logger.info(f"Created session: {sid} from paste")
        return JSONResponse({"status": "ok", "session": sid})
    except Exception as e:
        logger.error(f"Paste failed: {e}")
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


@app.delete("/api/sessions/{sid}")
async def delete_session(sid: str):
    import shutil
    d = Path("profiles") / sid
    if d.exists():
        shutil.rmtree(d)
        logger.info(f"Deleted session: {sid}")
        return JSONResponse({"status": "ok"})
    return JSONResponse({"status": "error", "message": "Not found"}, status_code=404)


# ============================================================
# API: Tests
# ============================================================

@app.post("/api/test/run")
async def run_test(url: str = Form(...), watch_time: int = Form(45), count: int = Form(1), session: str = Form("")):
    task_id = uuid.uuid4().hex[:8]
    logger.info(f"Test run {task_id}: {url} x{count} ({watch_time}s)")

    async def run():
        try:
            from videoqa.core.browser import UndetectedYouTubeBrowser
            results = []
            for i in range(count):
                profile = session if session else None
                b = UndetectedYouTubeBrowser(headless=True, profile_dir=profile)
                try:
                    p = await b.start()
                    await p.goto(url, wait_until="domcontentloaded", timeout=20000)
                    await p.wait_for_timeout(3000)
                    s = await p.evaluate("""() => { try {
                        const sc = document.querySelectorAll("script");
                        for(const s of sc) if(s.textContent.includes("ytInitialPlayerResponse")) {
                            const m = s.textContent.match(/ytInitialPlayerResponse = ({.*?});/);
                            if(m) return JSON.parse(m[1]).playabilityStatus.status;
                        }
                    } catch(e) {} return "unknown"; }""")
                    if s == "OK":
                        await p.evaluate("document.querySelector('#movie_player,.html5-video-player')?.click()")
                        await p.wait_for_timeout(2000)
                        await p.evaluate("const v=document.querySelector('video');if(v){v.muted=true;v.play()}")
                        await p.wait_for_timeout(3000)
                        for _ in range(watch_time // 5):
                            await p.wait_for_timeout(5000)
                            await p.evaluate("const v=document.querySelector('video');if(v&&v.paused)v.play()")
                        final = await p.evaluate("()=>{const v=document.querySelector('video');return v?v.currentTime:0}")
                        results.append({"instance": i + 1, "status": "passed", "watch_time": round(final, 1)})
                    else:
                        results.append({"instance": i + 1, "status": "session_invalid", "error": f"Playability: {s}"})
                finally:
                    await b.close()
            test_results.append({"id": task_id, "url": url, "timestamp": datetime.now().isoformat(), "results": results,
                                 "passed": sum(1 for r in results if r["status"] == "passed"),
                                 "failed": sum(1 for r in results if r["status"] != "passed")})
            save_results(test_results)
            logger.info(f"Test {task_id}: {len(results)} instances, {test_results[-1]['passed']} passed")
        finally:
            running_tasks.pop(task_id, None)

    running_tasks[task_id] = asyncio.create_task(run())
    return JSONResponse({"status": "started", "task_id": task_id})


@app.post("/api/test/distribute")
async def distribute_views(channel: str = Form(...), total_views: int = Form(20), top_videos: int = Form(10)):
    task_id = uuid.uuid4().hex[:8]
    logger.info(f"Distribute {total_views} views across top {top_videos} of {channel}")

    async def run():
        try:
            distributor = ViewDistributor(session_mgr)
            url = f"https://www.youtube.com/{channel}/videos" if channel.startswith("@") else channel
            videos = await asyncio.to_thread(scanner.scan_videos, url, top_videos * 2)
            for v in videos:
                v["views"] = scanner.extract_view_count(v.get("meta", ""))
            videos.sort(key=lambda v: v["views"], reverse=True)
            videos = videos[:top_videos]
            results = await distributor.distribute_views(videos, total_views)
            test_results.append({"id": task_id, "channel": channel, "timestamp": datetime.now().isoformat(),
                                 "type": "distribute", "results": results,
                                 "passed": sum(1 for r in results if r.get("success")),
                                 "failed": sum(1 for r in results if not r.get("success"))})
            save_results(test_results)
            logger.info(f"Distribute {task_id}: {test_results[-1]['passed']}/{total_views} succeeded")
        finally:
            running_tasks.pop(task_id, None)

    running_tasks[task_id] = asyncio.create_task(run())
    return JSONResponse({"status": "started", "task_id": task_id})


# ============================================================
# Status / Results
# ============================================================

@app.get("/api/status")
async def get_status():
    return JSONResponse({
        "sessions": len(session_mgr.list_sessions()),
        "running_tasks": len(running_tasks),
        "recent_results": len(test_results),
    })


@app.get("/api/results")
async def get_results():
    return JSONResponse(test_results[-50:])


@app.get("/api/logs")
async def get_logs():
    log_path = Path("/tmp/videoqa-web.log")
    if log_path.exists():
        return JSONResponse({"logs": log_path.read_text()[-10000:]})
    return JSONResponse({"logs": "No logs available"})


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8081))
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="debug")
