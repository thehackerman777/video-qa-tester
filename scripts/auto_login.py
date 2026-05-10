#!/usr/bin/env python3
"""
Auto-login script — YouTube test account login with session persistence.

Usage:
    1. Edit .yt-credentials.json with your test account
    2. python3 scripts/auto_login.py
    3. Session saved. Future tests will use it.
"""

import asyncio
import json
import sys
from pathlib import Path

# Add project root
sys.path.insert(0, str(Path(__file__).parent.parent))

from videoqa.core.browser import UndetectedYouTubeBrowser


async def main():
    creds_file = Path(".yt-credentials.json")
    if not creds_file.exists():
        # Create template
        template = {
            "accounts": [
                {
                    "email": "your-test-account@gmail.com",
                    "password": "your-password",
                    "used": False,
                }
            ]
        }
        creds_file.write_text(json.dumps(template, indent=2))
        print(f"✏ Created {creds_file}")
        print(f"  Edit it with your credentials, then run again")
        return

    creds = json.loads(creds_file.read_text())
    accounts = [a for a in creds["accounts"] if not a.get("used")]

    if not accounts:
        print("✅ All accounts already logged in")
        return

    account = accounts[0]
    print(f"\n🔑 Logging in as: {account['email']}")

    browser = UndetectedYouTubeBrowser(headless=False)

    try:
        page = await browser.start()
        print("1. Browser started. Navigated to Google Login...")
        await page.goto("https://accounts.google.com/Login",
                        wait_until="networkidle", timeout=30000)

        # Step 1: Email
        email_input = await page.wait_for_selector(
            "input[type='email']", timeout=15000)
        await email_input.click()
        await page.wait_for_timeout(300)
        await email_input.fill(account["email"])
        await page.wait_for_timeout(300)
        await page.keyboard.press("Enter")
        await page.wait_for_timeout(4000)
        print("2. Email entered")

        # Step 2: Password
        pass_input = await page.wait_for_selector(
            "input[type='password']", timeout=15000)
        await pass_input.click()
        await page.wait_for_timeout(300)
        await pass_input.fill(account["password"])
        await page.wait_for_timeout(300)
        await page.keyboard.press("Enter")
        await page.wait_for_timeout(5000)
        print("3. Password entered")

        # Check result
        current_url = page.url
        if "myaccount" in current_url or "youtube" in current_url:
            print(f"\n✅ LOGIN SUCCESSFUL!")
            print(f"   URL: {current_url[:80]}")

            # Save session
            await browser.save_cookies()
            print("   ✅ Session cookies saved!")

            # Mark account as used
            account["used"] = True
            creds_file.write_text(json.dumps(creds, indent=2))
            print("   ✅ Account marked as used")
        else:
            print(f"\n⚠ Login needs attention")
            print(f"   URL: {current_url[:80]}")
            print("   Possible: 2FA, phone verification, or captcha")
            print("   Check the browser window that opened (--headed)")
            input("\n   Press Enter after completing login manually...")

            # Save session anyway
            await browser.save_cookies()
            print("   ✅ Session saved anyway")

    finally:
        await browser.close()

    print("\n✅ Done! Now run your tests:")
    print("  python3 -m videoqa.cli.main test <url> --watch-time 45")


if __name__ == "__main__":
    asyncio.run(main())
