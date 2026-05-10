#!/usr/bin/env python3
"""
Video QA Tester — CLI
Automated QA testing for video platforms.

Usage:
    videoqa test <url> [options]
    videoqa scan <channel> [options]
    videoqa loadtest <url> [options]
    videoqa login [options]
    videoqa debug <url>
"""

import asyncio
import sys
import time
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.panel import Panel
from rich import box

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from videoqa.core.browser import YouTubeBrowser
from videoqa.core.types import (
    TestConfig, Metadata, TestResult, TestStatus,
    ActionResult, ActionType, LoadTestConfig,
)


console = Console()


# ============================================================
# SHARED HELPERS
# ============================================================

def make_metadata(scenario: str) -> Metadata:
    return Metadata(scenario=scenario)


def make_config(headless: bool = True) -> TestConfig:
    return TestConfig(headless=headless)


def print_result(result: TestResult):
    """Pretty-print a test result."""
    status_color = "green" if result.status == TestStatus.PASSED else "red"
    console.print(f"\n  ● Status: [{status_color}]{result.status.value.upper()}[/{status_color}]")
    console.print(f"    Duration: {result.duration_ms:.0f}ms")
    console.print(f"    Actions: {len(result.actions)}")
    console.print(f"    Errors: {len(result.errors)}")
    console.print(f"    Watch time: {result.watch_time_seconds:.1f}s")

    # Actions table
    if result.actions:
        table = Table(box=box.SIMPLE)
        table.add_column("#")
        table.add_column("Action")
        table.add_column("Status")
        table.add_column("Duration")
        for i, a in enumerate(result.actions):
            status = "✓" if a.status == "success" else "✗"
            table.add_row(str(i + 1), a.action_type.value, status, f"{a.duration_ms:.0f}ms")
        console.print("\n  Actions:")
        console.print(table)

    # View count difference
    if result.view_count_after > 0:
        diff = result.view_count_after - result.view_count_before
        console.print(f"\n  📊 View count: {result.view_count_before} → {result.view_count_after}")
        if diff > 0:
            console.print(f"     [green]✓ View counted! (+{diff})[/green]")
        else:
            console.print(f"     [yellow]No view counted yet[/yellow]")

    console.print("")


# ============================================================
# COMMANDS
# ============================================================

@click.group()
def cli():
    """Video QA Tester — Automated testing for video platforms."""
    pass


@cli.command()
@click.argument("url")
@click.option("--headless/--headed", default=True, help="Run browser headless")
@click.option("--wait", default=35, help="Seconds to watch the video")
@click.option("--debug", is_flag=True, help="Show detailed debug info")
def test(url, headless, wait, debug):
    """Run a single test against a video URL."""
    async def run():
        metadata = make_metadata("single-test")
        config = TestConfig(headless=headless, video_wait_seconds=wait)
        browser = YouTubeBrowser(config)

        console.print(Panel.fit(
            f"[bold]🎬 Video QA Tester — Test[/bold]\n\n"
            f"  URL: {url}\n"
            f"  Watch time: {wait}s\n"
            f"  Headless: {headless}",
            border_style="blue"
        ))

        result = TestResult(video_url=url, status=TestStatus.ERROR, metadata=metadata)
        start = time.time()

        try:
            await browser.start(metadata)
            page = browser.page()

            # Collect console errors
            console_errors = []
            page.on("pageerror", lambda e: console_errors.append(str(e)))

            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                transient=True,
            ) as progress:
                progress.add_task("Navigating to video...", total=None)
                await browser.navigate_video(url, 3)

                # Get view count before
                result.view_count_before = await browser.get_view_count()
                if debug:
                    state = await browser.get_player_state()
                    console.print(f"  [dim]Player state: {state.get('readyState')}[/dim]")

                progress.add_task("Playing video...", total=None)
                played = await browser.play_video()
                result.actions.append(ActionResult(ActionType.PLAY, "success" if played else "failure"))

                if debug:
                    state = await browser.get_player_state()
                    console.print(f"  [dim]After play: paused={state.get('paused')}, time={state.get('currentTime'):.1f}s[/dim]")

                progress.add_task(f"Watching for {wait}s...", total=None)
                actual_watch = await browser.wait_for_watch_time(wait)
                result.watch_time_seconds = actual_watch

                # Check final state
                result.view_count_after = await browser.get_view_count()
                result.status = TestStatus.PASSED if played else TestStatus.FAILED

            result.duration_ms = (time.time() - start) * 1000

            if debug and console_errors:
                console.print("\n  [yellow]Console errors:[/yellow]")
                for e in console_errors[:5]:
                    console.print(f"    {e}")

        except Exception as e:
            result.status = TestStatus.ERROR
            result.errors.append(str(e))
            if debug:
                console.print(f"\n  [red]Error: {e}[/red]")
                await browser.screenshot()
                console.print("  Screenshot saved to /tmp/yt-debug.png")

        finally:
            await browser.stop()

        print_result(result)

    asyncio.run(run())


@cli.command()
@click.argument("channel")
@click.option("--max-videos", default=5, help="Maximum videos to scan")
@click.option("--headless/--headed", default=True)
@click.option("--test", is_flag=True, help="Also run a test on each video")
def scan(channel, max_videos, headless, test):
    """Scan a YouTube channel and list videos."""
    async def run():
        config = TestConfig(headless=headless)
        browser = YouTubeBrowser(config)

        console.print(Panel.fit(
            f"[bold]📡 Video QA Tester — Channel Scan[/bold]\n\n"
            f"  Channel: {channel}\n"
            f"  Max videos: {max_videos}",
            border_style="blue"
        ))

        try:
            await browser.start()
            videos = await browser.scan_channel(channel, max_videos)

            if not videos:
                console.print("[red]  ✗ No videos found[/red]")
                return

            table = Table(title=f"Found {len(videos)} videos", box=box.SIMPLE)
            table.add_column("#")
            table.add_column("Title")
            table.add_column("URL")
            for i, v in enumerate(videos):
                table.add_row(str(i + 1), v.title[:60], v.url[:50])
            console.print(table)

        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
        finally:
            await browser.stop()

    asyncio.run(run())


@cli.command()
@click.argument("url")
@click.option("--users", default=10, help="Number of concurrent users")
@click.option("--ramp-up", default=20, help="Ramp-up time in seconds")
@click.option("--duration", default=60, help="Test duration in seconds")
@click.option("--headless/--headed", default=True)
@click.option("--browsers", default=5, help="Max concurrent browser processes")
def loadtest(url, users, ramp_up, duration, headless, browsers):
    """Run concurrent user load test against a video."""
    async def run_user(user_id: int, results: list):
        """Run a single user session."""
        config = TestConfig(headless=headless, video_wait_seconds=40)
        browser = YouTubeBrowser(config)
        result = TestResult(video_url=url, status=TestStatus.ERROR)

        try:
            await browser.start(Metadata(scenario="load-test", worker=f"user-{user_id}"))
            await browser.navigate_video(url, 3)
            played = await browser.play_video()
            if played:
                watch = await browser.wait_for_watch_time(35)
                result.watch_time_seconds = watch
                result.view_count_after = await browser.get_view_count()
                result.status = TestStatus.PASSED
            else:
                result.status = TestStatus.FAILED
            result.duration_ms = 0
        except Exception as e:
            result.errors.append(str(e))
        finally:
            await browser.stop()
            results.append(result)

    async def run():
        console.print(Panel.fit(
            f"[bold]🚀 Video QA Tester — Load Test[/bold]\n\n"
            f"  URL: {url}\n"
            f"  Users: {users}\n"
            f"  Ramp-up: {ramp_up}s\n"
            f"  Duration: {duration}s\n"
            f"  Max browsers: {browsers}",
            border_style="blue"
        ))

        results = []
        semaphore = asyncio.Semaphore(browsers)

        async def limited_user(i: int):
            async with semaphore:
                await run_user(i, results)

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
        ) as progress:
            task = progress.add_task("Ramping up users...", total=users)
            ramp_up_batch = max(1, users // ramp_up)

            for i in range(0, users, ramp_up_batch):
                batch = list(range(i, min(i + ramp_up_batch, users)))
                tasks = [limited_user(u) for u in batch]
                await asyncio.gather(*tasks)
                progress.update(task, advance=len(batch))
                await asyncio.sleep(1)

        # Print report
        passed = sum(1 for r in results if r.status == TestStatus.PASSED)
        failed = sum(1 for r in results if r.status == TestStatus.FAILED)
        errors = sum(1 for r in results if r.status == TestStatus.ERROR)

        table = Table(box=box.SIMPLE)
        table.add_column("Metric")
        table.add_column("Value")
        table.add_row("Total users", str(len(results)))
        table.add_row("Passed", f"[green]{passed}[/green]")
        table.add_row("Failed", f"[red]{failed}[/red]")
        table.add_row("Errors", f"[yellow]{errors}[/yellow]")
        table.add_row("Success rate", f"{(passed / max(len(results), 1)) * 100:.1f}%")
        avg_watch = sum(r.watch_time_seconds for r in results) / max(len(results), 1)
        table.add_row("Avg watch time", f"{avg_watch:.1f}s")
        views_total = sum(r.view_count_after for r in results)
        table.add_row("Total views tracked", str(views_total))

        console.print("\n  📊 Load Test Results")
        console.print(table)
        console.print("")

    asyncio.run(run())


@cli.command()
@click.option("--email", prompt=True, help="Google account email")
@click.option("--password", prompt=True, hide_input=True, help="Google account password")
@click.option("--headless/--headed", default=False)
def login(email, password, headless):
    """Login to Google and save session for future use."""
    async def run():
        config = TestConfig(headless=headless, persist_session=True)
        browser = YouTubeBrowser(config)

        console.print(Panel.fit(
            f"[bold]🔑 YouTube Login[/bold]\n\n"
            f"  Account: {email}\n"
            f"  Session will be saved for reuse",
            border_style="blue"
        ))

        try:
            await browser.start()
            success = await browser.login_google(email, password)
            if success:
                console.print("[green]  ✅ Session saved! Future tests will use this session.[/green]")
            else:
                console.print("[yellow]  ⚠ Login may need additional steps[/yellow]")
        finally:
            await browser.stop()

    asyncio.run(run())


@cli.command()
@click.argument("url")
@click.option("--headless/--headed", default=False)
def debug(url, headless):
    """Debug: show detailed video page state."""
    async def run():
        config = TestConfig(headless=headless)
        browser = YouTubeBrowser(config)

        console.print("[bold]🔍 Debug Mode[/bold]\n")

        try:
            await browser.start()

            # Navigate
            console.print("1. Navigating...")
            await browser.navigate_video(url, 3)

            # Player state
            state = await browser.get_player_state()
            console.print(f"2. Player state: [dim]{json.dumps(state, indent=2)}[/dim]")

            # View count
            views = await browser.get_view_count()
            console.print(f"3. View count: {views}")

            # Play
            console.print("4. Playing...")
            played = await browser.play_video()
            console.print(f"   Played: {played}")

            await browser._page.wait_for_timeout(5000)

            state2 = await browser.get_player_state()
            console.print(f"5. After 5s: [dim]{json.dumps(state2, indent=2)}[/dim]")

            # Screenshot
            await browser.screenshot()
            console.print("6. Screenshot: /tmp/yt-debug.png")

            # Page URL
            console.print(f"7. URL: {browser._page.url}")

        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
        finally:
            await browser.stop()

    import json
    asyncio.run(run())


@cli.command()
def status():
    """Show session status and saved sessions."""
    session_file = Path("sessions/youtube_session.json")
    if session_file.exists():
        size = session_file.stat().st_size
        console.print(f"[green]  ✅ Session saved ({size / 1024:.1f} KB)[/green]")
        console.print(f"  File: {session_file}")
    else:
        console.print("[yellow]  ⚠ No saved session. Run 'videoqa login' first.[/yellow]")


@cli.command()
def clear_session():
    """Clear saved session."""
    session_file = Path("sessions/youtube_session.json")
    if session_file.exists():
        session_file.unlink()
        console.print("[green]  ✅ Session cleared[/green]")
    else:
        console.print("[yellow]  ⚠ No session to clear[/yellow]")


if __name__ == "__main__":
    cli()
