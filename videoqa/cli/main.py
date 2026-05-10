#!/usr/bin/env python3
"""
Video QA Tester — CLI v2
Zero-cuenta, anti-detección, multi-instancia.
"""

import asyncio
import json
import os
import random
import subprocess
import sys
import time
import uuid
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich import box

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from videoqa.core.browser import UndetectedYouTubeBrowser
from videoqa.core.interceptor import ForcedYouTubeBrowser

console = Console()


# ============================================================
# COMMANDS
# ============================================================

@click.group()
def cli():
    """Video QA Tester v2 — Zero-account YouTube testing."""
    pass


@cli.command()
@click.argument("url")
@click.option("--watch-time", default=40, help="Seconds to watch")
@click.option("--headed/--headless", default=True, help="Show browser window")
@click.option("--profile", default=None, help="Profile directory (persistent)")
@click.option("--proxy", default=None, help="SOCKS5 proxy: socks5://user:pass@ip:port")
@click.option("--debug", is_flag=True)
@click.option("--count", default=1, help="Number of concurrent instances")
def test(url, watch_time, headed, profile, proxy, debug, count):
    """Test a video — single or multi-instance."""
    if count > 1:
        return run_multi(url, count, watch_time, headed, proxy, debug)

    asyncio.run(run_single(url, watch_time, headed, profile, proxy, debug))


@cli.command()
@click.argument("channel")
@click.option("--max", default=10)
@click.option("--headed/--headless", default=False)
def scan(channel, max, headed):
    """Scan a YouTube channel for videos."""
    async def run():
        browser = UndetectedYouTubeBrowser(headless=not headed)
        console.print(Panel.fit(f"[bold]📡 Scanning: {channel}[/bold]", border_style="blue"))

        try:
            page = await browser.start()
            if channel.startswith("@"):
                url = f"https://www.youtube.com/{channel}/videos"
            else:
                url = f"https://www.youtube.com/channel/{channel}/videos"

            await page.goto(url, wait_until="networkidle")
            await page.wait_for_timeout(3000)

            for _ in range(3):
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await page.wait_for_timeout(2000)

            videos = await page.evaluate(f"""
                () => {{
                    const links = document.querySelectorAll('a#video-title, a[href*="/watch?v="]');
                    const seen = new Set();
                    const result = [];
                    for (const link of links) {{
                        const url = link.href;
                        if (seen.has(url)) continue;
                        seen.add(url);
                        const m = url.match(/[?&]v=([^&]+)/);
                        if (!m) continue;
                        result.push({{ id: m[1], title: (link.title || link.textContent.trim()).substring(0, 60), url }});
                        if (result.length >= {max}) break;
                    }}
                    return result;
                }}
            """)

            if not videos:
                console.print("[red]No videos found[/red]")
                return

            table = Table(box=box.SIMPLE)
            table.add_column("#")
            table.add_column("Title")
            table.add_column("URL")
            for i, v in enumerate(videos):
                table.add_row(str(i + 1), v["title"], v["url"][:55])
            console.print(table)

        finally:
            await browser.close()

    asyncio.run(run())


@cli.command()
@click.argument("url")
@click.option("--instances", default=3, help="Number of parallel instances")
@click.option("--watch-time", default=40)
@click.option("--proxy-file", default=None, help="File with proxies (one per line)")
@click.option("--docker", is_flag=True, help="Use Docker instead of local processes")
def mass(url, instances, watch_time, proxy_file, docker):
    """
    Mass test — multiple instances watching the same video.
    Run with Docker: --docker --instances 20
    Run locally:    --instances 10
    """
    if docker:
        run_docker_mass(url, instances, watch_time, proxy_file)
    else:
        asyncio.run(run_local_mass(url, instances, watch_time, proxy_file))


@cli.command()
@click.argument("url")
@click.option("--headed/--headless", default=True)
@click.option("--output", default="/tmp/yt-debug.png")
def debug(url, headed, output):
    """Debug: show full page state + screenshot."""
    async def run():
        browser = UndetectedYouTubeBrowser(headless=not headed)
        console.print("[bold]🔍 Debug Mode[/bold]\n")

        try:
            page = await browser.start()
            await page.goto(url, wait_until="networkidle")
            await page.wait_for_timeout(3000)

            state = await page.evaluate("""
                () => {
                    const v = document.querySelector('video');
                    return {
                        hasVideo: !!v,
                        paused: v?.paused,
                        currentTime: v?.currentTime,
                        duration: v?.duration,
                        networkState: v ? ['Empty','Idle','Loading','Loaded'][v.networkState] : null,
                        readyState: v ? ['HaveNothing','HaveMetadata','HaveCurrentData','HaveFutureData','HaveEnoughData'][v.readyState] : null,
                        src: v?.src ? 'yes' : 'no',
                        error: v?.error?.message || null,
                    };
                }
            """)
            console.print(f"  Initial state: [dim]{json.dumps(state, indent=2)}[/dim]")

            # Try to play
            await page.evaluate("""
                () => {
                    const el = document.querySelector('#movie_player, .html5-video-player, ytd-player');
                    if (el) el.click();
                }
            """)
            await page.wait_for_timeout(2000)

            played = await page.evaluate("""
                () => {
                    const v = document.querySelector('video');
                    if (!v) return false;
                    v.muted = true;
                    try { v.play(); return true; } catch(e) { return false; }
                }
            """)
            console.print(f"  Play attempt: {'[green]OK[/green]' if played else '[red]Failed[/red]'}")

            await page.wait_for_timeout(5000)
            state2 = await page.evaluate("""
                () => {
                    const v = document.querySelector('video');
                    return v ? { paused: v.paused, time: v.currentTime } : { error: 'no video' };
                }
            """)
            console.print(f"  After 5s: [dim]{json.dumps(state2, indent=2)}[/dim]")

            await browser.screenshot(output)
            console.print(f"  Screenshot: {output}")

        finally:
            await browser.close()

    asyncio.run(run())


# ============================================================
# MULTI-INSTANCE RUNNERS
# ============================================================

def run_multi(url, count, watch_time, headed, proxy, debug):
    """Run multiple instances in parallel (same process)."""
    async def run_all():
        tasks = []
        for i in range(count):
            browser = UndetectedYouTubeBrowser(
                headless=not headed,
                profile_dir=f"profiles/instance-{i}",
                proxy=proxy,
                instance_id=f"inst-{i}",
            )
            tasks.append(run_instance(browser, url, watch_time, debug, i))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        passed = sum(1 for r in results if r is True)
        failed = sum(1 for r in results if r is False)
        errors = sum(1 for r in results if isinstance(r, Exception))

        table = Table(title=f"Results: {count} instances", box=box.SIMPLE)
        table.add_column("Metric")
        table.add_column("Value")
        table.add_row("Total", str(count))
        table.add_row("Passed", f"[green]{passed}[/green]")
        table.add_row("Failed", f"[red]{failed}[/red]")
        table.add_row("Errors", f"[yellow]{errors}[/yellow]")
        console.print("\n")
        console.print(table)

    asyncio.run(run_all())


@cli.command()
@click.argument("url")
@click.option("--headed/--headless", default=False)
def inject(url, headed):
    """API interceptor — bypass LOGIN_REQUIRED by modifying YouTube API response."""
    async def run():
        browser = ForcedYouTubeBrowser(headless=not headed)
        console.print(Panel.fit(
            f"[bold]💉 API Interceptor Mode[/bold]\n\n"
            f"  URL: {url}",
            border_style="green"
        ))

        try:
            page = await browser.start_with_api_intercept()
            console.print("1. Interceptor active, navigating...")
            await browser.navigate(url, 3)

            state = await page.evaluate('''() => {
                const v = document.querySelector("video");
                return {
                    hasVideo: !!v,
                    networkState: v ? ["Empty","Idle","Loading","Loaded"][v.networkState] : null,
                    readyState: v ? ["HaveNothing","HaveMetadata","HaveCurrentData","HaveFutureData","HaveEnoughData"][v.readyState] : null,
                    src: v?.src ? "yes" : "no",
                };
            }''')
            console.print(f"2. State: {json.dumps(state, indent=2)}")

            console.print("3. Attempting playback...")
            played = await browser.play_video()
            console.print(f"   {'[green]✓[/green]' if played else '[red]✗[/red]'} Playing: {played}")

            await browser.screenshot()
            console.print("4. Waiting 10s...")

            before = await page.evaluate('() => { const v = document.querySelector("video"); return v ? v.currentTime : 0; }')
            await page.wait_for_timeout(10000)
            after = await page.evaluate('() => { const v = document.querySelector("video"); return v ? v.currentTime : 0; }')

            diff = after - before
            console.print(f"5. Time: {before:.1f}s → {after:.1f}s (progress: {diff:.1f}s) {'[green]✓[/green]' if diff > 3 else '[red]✗[/red]'}")
            console.print(f"   Screenshot: /tmp/yt-debug.png")

        finally:
            await browser.close()

    asyncio.run(run())


async def run_instance(browser, url, watch_time, debug, idx) -> bool:
    """Run a single browser instance."""
    try:
        page = await browser.start()

        if debug:
            console.print(f"  [{idx}] Navigating...")

        await page.goto(url, wait_until="networkidle", timeout=30000)
        await page.wait_for_timeout(3000)

        # Click player
        await page.evaluate("""
            () => {
                const el = document.querySelector('#movie_player, .html5-video-player, ytd-player, .ytp-play-button');
                if (el) el.click();
            }
        """)
        await page.wait_for_timeout(2000)

        # Play
        played = await page.evaluate("""
            () => {
                const v = document.querySelector('video');
                if (!v) return false;
                v.muted = true;
                try { v.play(); return true; } catch(e) { return false; }
            }
        """)

        if not played:
            if debug:
                console.print(f"  [{idx}] [red]Could not start playback[/red]")
            await browser.close()
            return False

        if debug:
            console.print(f"  [{idx}] Playing... ({watch_time}s)")

        # Wait with periodic checks
        chunk = 10
        for _ in range(watch_time // chunk):
            await page.wait_for_timeout(chunk * 1000)
            # Check if still alive
            alive = await page.evaluate("""
                () => {
                    try {
                        const v = document.querySelector('video');
                        if (!v || v.ended) return false;
                        if (v.paused) v.play().catch(() => {});
                        return true;
                    } catch { return false; }
                }
            """)
            if not alive:
                if debug:
                    console.print(f"  [{idx}] [yellow]Playback stopped early[/yellow]")
                break

        await browser.close()
        return True

    except Exception as e:
        if debug:
            console.print(f"  [{idx}] [red]Error: {e}[/red]")
        try:
            await browser.close()
        except:
            pass
        return False


def run_docker_mass(url, instances, watch_time, proxy_file):
    """Run instances via Docker Compose."""
    console.print(f"[bold]🐳 Docker Mass Test[/bold]")
    console.print(f"  Instances: {instances}")
    console.print(f"  URL: {url}")

    os.environ["VIDEO_URL"] = url
    os.environ["WATCH_TIME"] = str(watch_time)
    os.environ["BROWSER_COUNT"] = str(instances)

    cmd = ["docker-compose", "up", "--build", "--scale", f"browser={instances}", "-d"]
    console.print(f"  Running: {' '.join(cmd)}")

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        console.print("[green]  ✅ Containers started[/green]")
        console.print("  Run 'docker-compose logs -f' to watch")
        console.print("  Run 'docker-compose down' to stop")
    else:
        console.print(f"[red]  Error: {result.stderr}[/red]")


async def run_local_mass(url, instances, watch_time, proxy_file):
    """Run multiple instances locally (for testing)."""
    proxies = []
    if proxy_file:
        with open(proxy_file) as f:
            proxies = [line.strip() for line in f if line.strip()]

    console.print(f"[bold]🧪 Local Mass Test[/bold]")
    console.print(f"  Instances: {instances}")
    console.print(f"  Proxies: {len(proxies) if proxies else 'none'}")

    tasks = []
    for i in range(instances):
        proxy = random.choice(proxies) if proxies else None
        browser = UndetectedYouTubeBrowser(
            headless=True,
            profile_dir=f"profiles/instance-{i}",
            proxy=proxy,
            instance_id=f"mass-{i}",
        )
        tasks.append(run_instance(browser, url, watch_time, debug=True, idx=i))

    with Progress(SpinnerColumn(), TextColumn("{task.description}"), transient=True) as p:
        p.add_task(f"Running {instances} instances...", total=None)
        results = await asyncio.gather(*tasks, return_exceptions=True)

    passed = sum(1 for r in results if r is True)
    console.print(f"\n[green]  ✅ {passed}/{instances} completed[/green]")
    if passed < instances:
        console.print(f"[yellow]  ⚠ {instances - passed} failed[/yellow]")


if __name__ == "__main__":
    cli()
