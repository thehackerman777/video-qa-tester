#!/usr/bin/env python3
"""
Video QA Tester — Web Interface
FastAPI + HTMX + Tailwind
"""

import asyncio
import json
import os
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

import httpx
from fastapi import FastAPI, Request, Form, Query, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from jinja2 import pass_context

sys.path.insert(0, str(Path(__file__).parent.parent))
from videoqa.core.session_manager import SessionManager, ChannelScanner, ViewDistributor

app = FastAPI(title="Video QA Tester", version="1.0")

BASE_DIR = Path(__file__).parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
static = BASE_DIR / "static"
static.mkdir(exist_ok=True)

# Helpers
session_mgr = SessionManager()
scanner = ChannelScanner()

# In-memory state
test_results = []
running_tasks = {}


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(request, "index.html", {
        "sessions": session_mgr.list_sessions(),
        "results": test_results[-20:],
        "running": len(running_tasks),
        "page": "dashboard",
    })


@app.get("/channels", response_class=HTMLResponse)
async def channels_page(request: Request):
    return templates.TemplateResponse(request, "channels.html", {
        "page": "channels",
    })


@app.get("/sessions", response_class=HTMLResponse)
async def sessions_page(request: Request):
    return templates.TemplateResponse(request, "sessions.html", {
        "sessions": session_mgr.list_sessions(),
        "page": "sessions",
    })


@app.get("/test", response_class=HTMLResponse)
async def test_page(request: Request):
    return templates.TemplateResponse(request, "test.html", {
        "sessions": session_mgr.list_sessions(),
        "page": "test",
    })


# ============================================================
# API: Channel Scanner
# ============================================================

@app.post("/api/scan")
async def scan_channel(
    channel: str = Form(...),
    max_videos: int = Form(50),
    search: str = Form(""),
    sort: str = Form("views"),
):
    """Scan channel and return videos with pagination."""
    try:
        if channel.startswith("@"):
            url = f"https://www.youtube.com/{channel}/videos"
        elif channel.startswith("UC"):
            url = f"https://www.youtube.com/channel/{channel}/videos"
        else:
            url = channel

        # Run scanner in thread pool
        videos = await asyncio.to_thread(scanner.scan_videos, url, max_videos)

        # Parse views
        for v in videos:
            v["views"] = scanner.extract_view_count(v.get("meta", ""))

        # Sort
        if sort == "views":
            videos.sort(key=lambda v: v["views"], reverse=True)
        elif sort == "newest":
            pass  # Already in page order

        # Filter
        if search:
            search_lower = search.lower()
            videos = [v for v in videos if search_lower in v["title"].lower()]

        return JSONResponse({
            "status": "ok",
            "total": len(videos),
            "videos": videos[:max_videos],
        })
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


# ============================================================
# API: Sessions
# ============================================================

@app.post("/api/sessions/upload")
async def upload_cookies(file: UploadFile = File(...)):
    """Upload cookies file and create session."""
    try:
        content = await file.read()
        filename = f"/tmp/uploaded_cookies_{uuid.uuid4().hex[:8]}.txt"
        with open(filename, "wb") as f:
            f.write(content)

        sid = session_mgr.import_netscape_cookies(filename)
        return JSONResponse({"status": "ok", "session": sid})
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


@app.post("/api/sessions/paste")
async def paste_cookies(cookies: str = Form(...)):
    """Paste cookies directly into text area."""
    try:
        filename = f"/tmp/pasted_cookies_{uuid.uuid4().hex[:8]}.txt"
        with open(filename, "w") as f:
            f.write(cookies)

        sid = session_mgr.import_netscape_cookies(filename)
        return JSONResponse({"status": "ok", "session": sid, "message": f"Created {sid}"})
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


@app.delete("/api/sessions/{sid}")
async def delete_session(sid: str):
    """Delete a session."""
    import shutil
    session_dir = Path("profiles") / sid
    if session_dir.exists():
        shutil.rmtree(session_dir)
        return JSONResponse({"status": "ok"})
    return JSONResponse({"status": "error", "message": "Session not found"}, status_code=404)


# ============================================================
# API: Tests
# ============================================================

@app.post("/api/test/run")
async def run_test(
    url: str = Form(...),
    watch_time: int = Form(45),
    count: int = Form(1),
    session: str = Form(""),
):
    """Run a test (single or multi-instance)."""
    task_id = uuid.uuid4().hex[:8]
    
    async def run():
        try:
            from videoqa.core.browser import UndetectedYouTubeBrowser
            
            results = []
            for i in range(count):
                profile = session if session else f"profiles/session-{i+1:03d}"
                b = UndetectedYouTubeBrowser(
                    headless=True,
                    profile_dir=profile if session else None,
                )
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
                        
                        chunks = watch_time // 5
                        for _ in range(chunks):
                            await p.wait_for_timeout(5000)
                            await p.evaluate("const v=document.querySelector('video');if(v&&v.paused)v.play()")
                        
                        final = await p.evaluate("()=>{const v=document.querySelector('video');return v?v.currentTime:0}")
                        results.append({"instance": i+1, "status": "passed", "watch_time": round(final, 1)})
                    else:
                        results.append({"instance": i+1, "status": "session_invalid", "error": f"Playability: {s}"})
                finally:
                    await b.close()
                
            test_results.append({
                "id": task_id,
                "url": url,
                "timestamp": datetime.now().isoformat(),
                "results": results,
                "passed": sum(1 for r in results if r["status"] == "passed"),
                "failed": sum(1 for r in results if r["status"] != "passed"),
            })
        finally:
            running_tasks.pop(task_id, None)
    
    running_tasks[task_id] = asyncio.create_task(run())
    return JSONResponse({"status": "started", "task_id": task_id})


@app.post("/api/test/distribute")
async def distribute_views(
    channel: str = Form(...),
    total_views: int = Form(20),
    top_videos: int = Form(10),
):
    """Distribute views across top videos."""
    task_id = uuid.uuid4().hex[:8]
    
    async def run():
        try:
            distributor = ViewDistributor(session_mgr)
            
            if channel.startswith("@"):
                url = f"https://www.youtube.com/{channel}/videos"
            else:
                url = channel
            
            videos = await asyncio.to_thread(scanner.scan_videos, url, top_videos * 2)
            for v in videos:
                v["views"] = scanner.extract_view_count(v.get("meta", ""))
            videos.sort(key=lambda v: v["views"], reverse=True)
            videos = videos[:top_videos]
            
            results = await distributor.distribute_views(videos, total_views)
            
            test_results.append({
                "id": task_id,
                "channel": channel,
                "timestamp": datetime.now().isoformat(),
                "type": "distribute",
                "results": results,
                "passed": sum(1 for r in results if r.get("success")),
                "failed": sum(1 for r in results if not r.get("success")),
            })
        finally:
            running_tasks.pop(task_id, None)
    
    running_tasks[task_id] = asyncio.create_task(run())
    return JSONResponse({"status": "started", "task_id": task_id})


@app.get("/api/status")
async def get_status():
    """Get system status."""
    return JSONResponse({
        "sessions": len(session_mgr.list_sessions()),
        "running_tasks": len(running_tasks),
        "recent_results": len(test_results),
    })


@app.get("/api/results")
async def get_results():
    """Get recent test results."""
    return JSONResponse(test_results[-50:])


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
