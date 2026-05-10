#!/usr/bin/env python3
"""
Video QA Tester — CLI v2
YouTube QA testing con sesión persistente.
"""

import asyncio
import json
import os
import random
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

console = Console()


@click.group()
def cli():
    """Video QA Tester — Automated YouTube QA testing."""
    pass


@cli.command()
@click.argument("url")
@click.option("--watch-time", default=45, help="Seconds to watch")
@click.option("--headed/--headless", default=False)
@click.option("--count", default=1, help="Number of parallel instances")
@click.option("--session-dir", default="profiles", help="Session profiles directory")
def test(url, watch_time, headed, count, session_dir):
    """Test a video — reproduce con sesión guardada."""
    if count > 1:
        return run_multi(url, count, watch_time, headed, session_dir)

    asyncio.run(run_single(url, watch_time, headed, session_dir))


async def run_single(url, watch_time, headed, session_dir):
    browser = UndetectedYouTubeBrowser(
        headless=not headed,
        profile_dir=str(Path(session_dir) / "default"),
    )

    console.print(Panel.fit(f"[bold]🎬 Testing: {url}[/bold]\n  Watch time: {watch_time}s", border_style="blue"))

    try:
        page = await browser.start()
        print("1. Navigating to video...")
        await page.goto(url, wait_until="networkidle", timeout=30000)
        await page.wait_for_timeout(3000)

        # Check if session is working
        playability = await page.evaluate("""
            () => {
                try {
                    const scripts = document.querySelectorAll("script");
                    for (const s of scripts) {
                        if (s.textContent.includes("ytInitialPlayerResponse")) {
                            const match = s.textContent.match(/ytInitialPlayerResponse = ({.*?});/);
                            if (match) {
                                const data = JSON.parse(match[1]);
                                return data.playabilityStatus?.status || "unknown";
                            }
                        }
                    }
                } catch(e) {}
                return "unknown";
            }
        """)
        print(f"   Playability status: {playability}")

        if playability == "LOGIN_REQUIRED":
            print("   [yellow]⚠ Session not valid — need to login first[/yellow]")
            print("   Run: python3 scripts/auto_login.py (from your local PC)")
            await browser.close()
            return

        # Click player
        await page.evaluate("""
            () => {
                const el = document.querySelector("#movie_player, .html5-video-player, ytd-player, .ytp-play-button");
                if (el) el.click();
            }
        """)
        await page.wait_for_timeout(2000)

        # Play
        await page.evaluate("""
            () => {
                const v = document.querySelector("video");
                if (v) { v.muted = true; v.play().catch(() => {}); }
            }
        """)
        await page.wait_for_timeout(3000)

        # Check time progression
        t0 = await page.evaluate("() => { const v = document.querySelector('video'); return v ? v.currentTime : 0; }")
        if t0 == 0:
            print("   [yellow]⏳ Time not progressing yet, waiting...[/yellow]")
            await page.wait_for_timeout(5000)

        t1 = await page.evaluate("() => { const v = document.querySelector('video'); return v ? v.currentTime : 0; }")
        if t1 > 0:
            print(f"   [green]✓ Video playing! Time: {t1:.1f}s[/green]")
        else:
            print(f"   [red]✗ Time stuck at 0. YouTube blocked playback[/red]")
            print("   Need: valid session or different IP")
            await browser.close()
            return

        # Watch for specified time
        chunks = watch_time // 5
        for i in range(chunks):
            await page.wait_for_timeout(5000)
            t = await page.evaluate("() => { const v = document.querySelector('video'); return v ? v.currentTime : 0; }")
            print(f"   Watching... {t:.0f}s / {watch_time}s")

            # Keep alive
            await page.evaluate("""
                () => {
                    const v = document.querySelector("video");
                    if (v && v.paused) v.play().catch(() => {});
                }
            """)

        final_time = await page.evaluate("() => { const v = document.querySelector('video'); return v ? v.currentTime : 0; }")
        print(f"\n[green]✅ Done! Watch time: {final_time:.1f}s[/green]")

    except Exception as e:
        print(f"\n[red]❌ Error: {e}[/red]")
    finally:
        await browser.close()


def run_multi(url, count, watch_time, headed, session_dir):
    """Multiple parallel instances."""
    async def run_all():
        tasks = []
        for i in range(count):
            browser = UndetectedYouTubeBrowser(
                headless=not headed,
                profile_dir=str(Path(session_dir) / f"instance-{i}"),
                instance_id=f"inst-{i}",
            )
            tasks.append(run_one(browser, url, watch_time, i))

        results = await asyncio.gather(*tasks, return_exceptions=True)
        passed = sum(1 for r in results if r is True)
        console.print(f"\n[green]✅ {passed}/{count} completed[/green]")

    asyncio.run(run_all())


@cli.command()
@click.option("--headed/--headless", default=False)
def login(headed):
    """Login manually and save session."""
    from scripts.auto_login import main as login_main
    asyncio.run(login_main())


@cli.command()
@click.argument("url")
@click.option("--headed/--headless", default=False)
def debug(url, headed):
    """Debug: show page state and take screenshot."""
    async def run():
        browser = UndetectedYouTubeBrowser(headless=not headed)
        try:
            page = await browser.start()
            await page.goto(url, wait_until="networkidle", timeout=30000)
            await page.wait_for_timeout(3000)

            state = await page.evaluate("""
                () => {
                    const v = document.querySelector("video");
                    return {
                        hasVideo: !!v,
                        paused: v?.paused,
                        currentTime: v?.currentTime,
                        networkState: v ? ["Empty","Idle","Loading","Loaded"][v.networkState] : null,
                        readyState: v ? ["HaveNothing","HaveMetadata","HaveCurrentData","HaveFutureData","HaveEnoughData"][v.readyState] : null,
                        src: v?.src ? "yes" : "no",
                    };
                }
            """)
            console.print(json.dumps(state, indent=2))
            await browser.screenshot("/tmp/yt-debug.png")
            print("Screenshot: /tmp/yt-debug.png")
        finally:
            await browser.close()

    asyncio.run(run())


@cli.command()
def export_session():
    """Export session cookies for transfer between machines."""
    session_file = Path("profiles/default/cookies.json")
    if session_file.exists():
        print(f"Session file: {session_file}")
        print(f"Size: {session_file.stat().st_size / 1024:.1f} KB")
        print("\nTo transfer to server:")
        print(f"  scp {session_file} user@server:/path/to/video-qa-tester/profiles/default/")
    else:
        print("No session found. Login first.")


@cli.command()
def clear_session():
    """Clear saved session."""
    import shutil
    session_dir = Path("profiles")
    if session_dir.exists():
        shutil.rmtree(session_dir)
        print("✅ All sessions cleared")
    else:
        print("No sessions to clear")


async def run_one(browser, url, watch_time, idx) -> bool:
    """Single instance runner for multi-mode."""
    try:
        page = await browser.start()
        await page.goto(url, wait_until="networkidle", timeout=30000)
        await page.wait_for_timeout(3000)

        await page.evaluate("""
            () => {
                const el = document.querySelector("#movie_player, .html5-video-player, ytd-player");
                if (el) el.click();
            }
        """)
        await page.wait_for_timeout(2000)

        await page.evaluate("""
            () => {
                const v = document.querySelector("video");
                if (v) { v.muted = true; v.play().catch(() => {}); }
            }
        """)
        await page.wait_for_timeout(3000)

        t0 = await page.evaluate("() => { const v = document.querySelector('video'); return v ? v.currentTime : 0; }")
        if t0 == 0:
            await page.wait_for_timeout(5000)

        t1 = await page.evaluate("() => { const v = document.querySelector('video'); return v ? v.currentTime : 0; }")
        if t1 == 0:
            await browser.close()
            return False

        chunks = watch_time // 5
        for _ in range(chunks):
            await page.wait_for_timeout(5000)
            await page.evaluate("""
                () => {
                    const v = document.querySelector("video");
                    if (v && v.paused) v.play().catch(() => {});
                }
            """)

        await browser.close()
        return True

    except:
        try:
            await browser.close()
        except:
            pass
        return False


if __name__ == "__main__":
    cli()
