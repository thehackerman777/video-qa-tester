#!/usr/bin/env python3
"""
Auto-login — YouTube test account login with session persistence.
Maneja múltiples pasos de Google: email → password → verificación
"""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from videoqa.core.browser import UndetectedYouTubeBrowser


async def main():
    creds_file = Path(".yt-credentials.json")
    if not creds_file.exists():
        template = {
            "accounts": [
                {"email": "your-test-account@gmail.com", "password": "your-password", "used": False}
            ]
        }
        creds_file.write_text(json.dumps(template, indent=2))
        print(f"✏ Created {creds_file} — edit it with your credentials, then run again")
        return

    creds = json.loads(creds_file.read_text())
    accounts = [a for a in creds["accounts"] if not a.get("used")]
    if not accounts:
        print("✅ All accounts already logged in")
        return

    account = accounts[0]
    print(f"\n🔑 Logging in as: {account['email']}")

    browser = UndetectedYouTubeBrowser(headless=True)

    try:
        page = await browser.start()
        print("1. Browser started")

        # Step 1: Go to YouTube click Sign in
        await page.goto("https://www.youtube.com", wait_until="networkidle", timeout=30000)
        await page.wait_for_timeout(3000)

        # Click "Sign in" button
        signin = await page.query_selector('a[aria-label*="Sign in"], paper-button:has-text("Sign in"), #buttons ytd-button-renderer a')
        if signin:
            await signin.click()
            await page.wait_for_timeout(3000)
            print("2. Clicked Sign in on YouTube")
        else:
            print("2. No Sign in button found, navigating directly")
            await page.goto("https://accounts.google.com/Login", wait_until="networkidle", timeout=30000)
            await page.wait_for_timeout(2000)

        # Step 2: Enter email
        print("3. Entering email...")
        try:
            email_input = await page.wait_for_selector(
                "input[type='email'], input[name='identifier']",
                timeout=15000
            )
            await email_input.click()
            await page.wait_for_timeout(300)
            await email_input.fill(account["email"])
            await page.wait_for_timeout(500)

            # Press Next button or Enter
            next_btn = await page.query_selector("#identifierNext button, button:has-text('Next')")
            if next_btn:
                await next_btn.click()
            else:
                await page.keyboard.press("Enter")
            print("   Email submitted")
        except Exception as e:
            print(f"   ⚠ Email error: {e}")
            await page.screenshot(path="/tmp/login-email-error.png")
            raise

        await page.wait_for_timeout(5000)

        # Check current state
        current_url = page.url
        print(f"   URL after email: {current_url[:80]}")

        # Step 3: Handle verification if needed
        loop_count = 0
        while loop_count < 10:
            await page.wait_for_timeout(2000)
            page_html = await page.content()

            # Check for password field
            password_visible = await page.evaluate("""
                () => {
                    const inputs = document.querySelectorAll("input[type='password']");
                    for (const inp of inputs) {
                        if (inp.offsetParent !== null && inp.getAttribute("aria-hidden") !== "true") {
                            return true;
                        }
                    }
                    return false;
                }
            """)

            if password_visible:
                print(f"4. Password field found (after ~{loop_count * 2}s)")
                break

            # Check for other challenges
            challenges = await page.evaluate("""
                () => {
                    const checks = {};
                    checks.phone = !!document.querySelector('input[type="tel"]');
                    checks.verify = !!document.querySelector('[data-challengeid]');
                    checks.captcha = !!document.querySelector('#captcha-form');
                    checks.tos = !!document.querySelector('[aria-label*="Terms"]');
                    checks.skip = !!document.querySelector('button:has-text("Skip"), button:has-text("Not now")');
                    return checks;
                }
            """)

            if challenges.get("phone"):
                print("   ⚠ Phone verification required!")
                print("   This account needs phone verification from AWS IP.")
                print("   Take a screenshot to see...")
                await page.screenshot(path="/tmp/login-phone-verify.png")
                print("   Screenshot: /tmp/login-phone-verify.png")

            if challenges.get("skip"):
                print("   Clicking 'Skip' button...")
                skip = await page.query_selector('button:has-text("Skip"), button:has-text("Not now")')
                if skip:
                    await skip.click()

            if challenges.get("captcha"):
                print("   ⚠ CAPTCHA detected! Manual intervention needed.")
                await page.screenshot(path="/tmp/login-captcha.png")
                break

            loop_count += 1
        else:
            print("   ⚠ Timed out waiting for password field")
            await page.screenshot(path="/tmp/login-timeout.png")
            # Try to save whatever session we have
            await browser.save_cookies()
            print("   Session saved anyway (partial)")
            return

        # Step 4: Enter password
        print("5. Entering password...")
        pass_input = await page.query_selector(
            "input[type='password']:not([aria-hidden='true'])"
        )
        if not pass_input:
            pass_input = await page.query_selector(
                "#password input[type='password']"
            )
        if not pass_input:
            pass_input = await page.query_selector("input[type='password']")

        if pass_input:
            await pass_input.click()
            await page.wait_for_timeout(300)
            await pass_input.fill(account["password"])
            await page.wait_for_timeout(500)

            next_btn = await page.query_selector("#passwordNext button, button:has-text('Next')")
            if next_btn:
                await next_btn.click()
            else:
                await page.keyboard.press("Enter")
            await page.wait_for_timeout(5000)
            print("   Password submitted")
        else:
            print("   ⚠ Could not find password field")
            await page.screenshot(path="/tmp/login-no-password.png")
            await browser.save_cookies()
            return

        # Step 5: Check result
        await page.wait_for_timeout(3000)
        current_url = page.url

        if "myaccount" in current_url or "youtube.com" in current_url:
            print(f"\n✅ LOGIN SUCCESSFUL!")
            await browser.save_cookies()
            print("   ✅ Session saved!")
            account["used"] = True
            creds_file.write_text(json.dumps(creds, indent=2))
        else:
            print(f"\n⚠ Login may need more steps. URL: {current_url[:80]}")
            print("   Trying to save cookies anyway...")
            await browser.save_cookies()

    except Exception as e:
        print(f"\n❌ Error: {e}")
        await page.screenshot(path="/tmp/login-error.png")
        print("  Screenshot: /tmp/login-error.png")

    finally:
        await browser.close()

    print("\n✅ Done! Run tests with saved session:")
    print("  python3 -m videoqa.cli.main test <url> --watch-time 45")


if __name__ == "__main__":
    asyncio.run(main())
