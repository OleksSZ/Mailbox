import asyncio
import datetime
import os
import random
import sys
import traceback

# Django setup
import other.Mailbox.mailbox_project.modules.load_django as load_django
from other.Mailbox.mailbox_project.parser_app.models import FirstName, LastName

os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"

from playwright.async_api import async_playwright
from playwright_stealth import stealth_async

from other.Mailbox.mailbox_project.modules.name_generator import DatabaseNameGenerator
from other.Mailbox.mailbox_project.modules.generate_secure_password import generate_secure_password


# ===== CONFIG =====
COUNTRY = "CA"
BASE_PROXY_USERNAME = ""
PROXY_PASSWORD = ""
REGISTER_URL = "https://register.mailbox.org/en/private1?plan=light"
# ==================


def log(msg):
    ts = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
    print(f"[{ts}] {msg}", flush=True)


def get_proxy_config(country: str):
    sess = ''.join(random.choices('abcdefghijklmnopqrstuvwxyz0123456789', k=8))
    user = f"{BASE_PROXY_USERNAME}-cc-{country.lower()}-sessid-{sess}"
    log(f"Proxy user: {user}")
    return {
        "server": "http://pr.oxylabs.io:7777",
        "username": user,
        "password": PROXY_PASSWORD,
    }


async def dump_debug(page, prefix="debug"):
    """Сохраняет URL, HTML, скриншот при ошибке."""
    log(f"===== DUMP DEBUG ({prefix}) =====")
    try:
        log(f"URL at dump: {page.url}")
    except Exception as e:
        log(f"URL fail: {e}")

    try:
        html = await page.content()
        fname = f"{prefix}.html"
        with open(fname, "w", encoding="utf-8") as f:
            f.write(html)
        log(f"HTML saved: {fname} ({len(html)} bytes)")
    except Exception as e:
        log(f"HTML save fail: {e}")

    try:
        await page.screenshot(path=f"{prefix}.png", full_page=True)
        log(f"Screenshot saved: {prefix}.png")
    except Exception as e:
        log(f"Screenshot fail: {e}")


async def main():
    log("=== START DEBUG REGISTRATION ===")
    log(f"Country: {COUNTRY}")

    # Name / password
    name_gen = DatabaseNameGenerator(COUNTRY)
    account_data = name_gen.generate_next()
    account_password = generate_secure_password(14)
    log(f"First name: {account_data['first_name']}")
    log(f"Last name:  {account_data['last_name']}")
    log(f"Email:      {account_data['email']}")
    log(f"Password:   {account_password}")
    log(f"Country (from DB): {account_data['country']}")
    log(f"Gender: {account_data['gender']}")

    proxy_cfg = get_proxy_config(COUNTRY)

    async with async_playwright() as p:
        log("Launching Chromium...")
        browser = await p.chromium.launch(
            headless=True,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-infobars',
                '--disable-dev-shm-usage',
                '--no-sandbox',
            ]
        )
        log("Chromium OK")

        log("Creating context...")
        context = await browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            viewport={'width': 1920, 'height': 1080},
            proxy=proxy_cfg,
            locale='en-US',
            timezone_id='America/New_York',
        )
        log("Context OK")

        page = await context.new_page()

        # === Hooks для логов ===
        page.on("console", lambda msg: log(f"  [console.{msg.type}] {msg.text}"))
        page.on("pageerror", lambda err: log(f"  [pageerror] {err}"))
        page.on("requestfailed", lambda req: log(f"  [REQ_FAIL] {req.method} {req.url} — {req.failure}"))

        async def on_response(resp):
            try:
                t = resp.request.timing or {}
                dur = t.get("responseEnd", 0) - t.get("requestStart", 0)
                if dur and dur > 2000:
                    log(f"  [SLOW {int(dur)}ms] {resp.status} {resp.url}")
            except Exception:
                pass
        page.on("response", on_response)

        log("Applying stealth_async...")
        try:
            await stealth_async(page)
            log("stealth_async OK")
        except Exception as e:
            log(f"stealth_async FAILED: {e}")

        # === GOTO ===
        log(f"Navigating to {REGISTER_URL} ...")
        try:
            await page.goto(REGISTER_URL, timeout=60000, wait_until="domcontentloaded")
            log("GOTO OK")
            log(f"  URL:   {page.url}")
            log(f"  Title: {await page.title()}")
        except Exception as e:
            log(f"GOTO FAILED: {type(e).__name__}: {e}")
            await dump_debug(page, "debug_01_goto_failed")
            await browser.close()
            return

        # === Ждём форму ===
        log("Waiting for email input (15s)...")
        email_input = page.locator('input[name="mbo_registration_step_one[emailAddress]"]')
        try:
            await email_input.wait_for(state="visible", timeout=15000)
            log("Email input VISIBLE")
        except Exception as e:
            log(f"Email input NOT visible: {type(e).__name__}: {e}")
            await dump_debug(page, "debug_02_email_input_failed")
            await browser.close()
            return

        # === Заполняем step 1 ===
        log("Filling step 1 form...")
        try:
            await email_input.fill(account_data['email'])
            log(f"  email filled: {account_data['email']}")

            pw = page.locator('input[name="mbo_registration_step_one[plainPassword][first]"]')
            await pw.fill(account_password)

            pw2 = page.locator('input[name="mbo_registration_step_one[plainPassword][second]"]')
            await pw2.fill(account_password)
            log("  passwords filled")

            log("Clicking submit...")
            await page.locator('button[type="submit"]').click()
            log("  submit clicked")
        except Exception as e:
            log(f"Fill/click FAILED: {type(e).__name__}: {e}")
            log(traceback.format_exc())
            await dump_debug(page, "debug_03_fill_failed")
            await browser.close()
            return

        # === Ждём ответ ===
        log("Waiting for step 2 OR 'email taken' error (20s)...")
        error_loc = page.locator('text="The desired email address is already taken"')
        step2_loc = page.locator('select#mbo_registration_step_two_salutation')

        try:
            await error_loc.or_(step2_loc).wait_for(state="visible", timeout=20000)
            if await error_loc.is_visible():
                log("RESULT: EMAIL TAKEN ❌")
                await dump_debug(page, "debug_04_email_taken")
            else:
                log("RESULT: STEP 2 REACHED ✅ (email свободен)")
                log(f"  URL: {page.url}")
                try:
                    await page.screenshot(path="debug_05_step2_ok.png", full_page=True)
                    log("  screenshot saved: debug_05_step2_ok.png")
                except Exception:
                    pass
        except Exception as e:
            log(f"NEITHER error NOR step2 appeared: {type(e).__name__}: {e}")
            log(f"  Current URL: {page.url}")
            await dump_debug(page, "debug_06_step2_timeout")

        log("=== DONE ===")
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())