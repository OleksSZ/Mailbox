import os
import sys
import random
import datetime
import asyncio
from typing import Optional, Dict, Any, List

import other.Mailbox.mailbox_project.modules.load_django as load_django
from other.Mailbox.mailbox_project.parser_app.models import FirstName, LastName, MailboxAccount, NameCombination

os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"

from playwright.async_api import async_playwright, Browser, BrowserContext, Page

from other.Mailbox.mailbox_project.modules.name_generator import DatabaseNameGenerator
from other.Mailbox.mailbox_project.modules.generate_secure_password import generate_secure_password
from dotenv import load_dotenv
load_dotenv()


def log(msg: str) -> None:
    ts = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
    print(f"[{ts}] {msg}", flush=True)


async def attach_page_listeners(page: Page, tag: str = "") -> None:
    page.on("console", lambda msg: log(f"  [{tag} console.{msg.type}] {msg.text}"))
    page.on("pageerror", lambda err: log(f"  [{tag} pageerror] {err}"))
    page.on("requestfailed", lambda req: log(
        f"  [{tag} REQ_FAIL] {req.method} {req.url} — {req.failure}"
    ))

    async def on_response(resp):
        try:
            t = resp.request.timing or {}
            dur = t.get("responseEnd", 0) - t.get("requestStart", 0)
            if dur and dur > 2000:
                log(f"  [{tag} SLOW {int(dur)}ms] {resp.status} {resp.url}")
        except Exception:
            pass
    page.on("response", on_response)
# ============================================


# Конфигурация
BASE_PROXY_USERNAME = os.getenv("BASE_PROXY_USERNAME")
PROXY_PASSWORD = os.getenv("PROXY_PASSWORD")
REGISTER_URL = "https://register.mailbox.org/en/private1?plan=light"
MAX_RETRIES_PER_ACCOUNT = int(os.getenv("MAX_RETRIES_PER_ACCOUNT", 5))
MAX_EMAIL_ATTEMPTS = int(os.getenv("MAX_EMAIL_ATTEMPTS", 3))
CONCURRENT_WORKERS = int(os.getenv("CONCURRENT_WORKERS", 3))
# ЛИМИТ НА КАЖДУЮ СТРАНУ отдельно, а не суммарно
LIMIT_PER_COUNTRY = int(os.getenv("LIMIT", 100))


def get_proxy_username(country: str) -> str:
    random_sess_id = ''.join(random.choices('abcdefghijklmnopqrstuvwxyz0123456789', k=8))
    return f"{BASE_PROXY_USERNAME}-cc-{country.lower()}-sessid-{random_sess_id}"


def get_proxy_config(country: str) -> Dict[str, Any]:
    return {
        "server": "http://pr.oxylabs.io:7777",
        "username": get_proxy_username(country),
        "password": PROXY_PASSWORD,
    }


async def create_context(browser: Browser, country: str) -> BrowserContext:
    context = await browser.new_context(
        user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        viewport={'width': 1920, 'height': 1080},
        proxy=get_proxy_config(country),
        locale='en-US',
        timezone_id='America/New_York',
    )
    return context


async def apply_stealth(page: Page) -> None:
    await page.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined
        });
        Object.defineProperty(navigator, 'plugins', {
            get: () => [1, 2, 3, 4, 5]
        });
        Object.defineProperty(navigator, 'languages', {
            get: () => ['en-US', 'en']
        });
        window.chrome = {
            runtime: {}
        };
        const originalQuery = window.navigator.permissions.query;
        window.navigator.permissions.query = (parameters) => (
            parameters.name === 'notifications' ?
                Promise.resolve({ state: Notification.permission }) :
                originalQuery(parameters)
        );
    """)


async def solve_captcha(page: Page) -> None:
    captcha_container = page.locator('.frc-captcha')
    await captcha_container.wait_for(state="attached", timeout=30000)
    await captcha_container.scroll_into_view_if_needed()
    await page.wait_for_timeout(2000)
    await captcha_container.evaluate("el => el.click()")
    await page.wait_for_function(
        'document.querySelector("input[name=\\"frc-captcha-solution\\"]").value !== ""',
        timeout=120000,
    )
    log("Капча успешно пройдена!")


async def register_one_account(
    country: str,
    browser: Browser,
    name_gen: DatabaseNameGenerator,
    slot_number: int,
) -> Optional[MailboxAccount]:
    log(f"\n{'=' * 15} КРАЇНА: {country} | Слот №{slot_number}/{LIMIT_PER_COUNTRY} {'=' * 15}")

    for attempt in range(1, MAX_RETRIES_PER_ACCOUNT + 1):
        context = None
        page = None
        account_data = None

        try:
            log(f"Спроба {attempt}/{MAX_RETRIES_PER_ACCOUNT} для {country}")

            context = await create_context(browser, country)
            page = await context.new_page()

            await attach_page_listeners(page, tag=f"{country}/att{attempt}")
            await apply_stealth(page)

            log(f"Открываем страницу регистрации: {REGISTER_URL}")
            goto_start = datetime.datetime.now()
            try:
                await page.goto(REGISTER_URL, timeout=60000, wait_until="domcontentloaded")
                goto_ms = (datetime.datetime.now() - goto_start).total_seconds() * 1000
                log(f"GOTO OK за {int(goto_ms)}ms — Title: {await page.title()}")
            except Exception as e_goto:
                goto_ms = (datetime.datetime.now() - goto_start).total_seconds() * 1000
                log(f"GOTO FAILED за {int(goto_ms)}ms: {type(e_goto).__name__}: {e_goto}")
                raise

            account_password = generate_secure_password(14)

            email_found = False

            for email_attempt in range(1, MAX_EMAIL_ATTEMPTS + 1):
                account_data = name_gen.generate_next()
                log(f"--> Проверка почты {email_attempt}: {account_data['first_name']} {account_data['last_name']} (R{account_data['round_number']}, combo_id={account_data['combo_id']})")
                log(f"--> Email: {account_data['email']}")
                log(f"--> Пароль: {account_password}")

                email_input = page.locator('input[name="mbo_registration_step_one[emailAddress]"]')

                try:
                    await email_input.wait_for(state="visible", timeout=15000)
                except Exception as e_wait:
                    log(f"Email input NOT visible за 15s: {type(e_wait).__name__}: {e_wait}")
                    raise

                await email_input.clear()
                await email_input.fill(account_data['email'])

                password_input = page.locator('input[name="mbo_registration_step_one[plainPassword][first]"]')
                await password_input.clear()
                await password_input.fill(account_password)

                confirm_input = page.locator('input[name="mbo_registration_step_one[plainPassword][second]"]')
                await confirm_input.clear()
                await confirm_input.fill(account_password)

                next_btn = page.locator('button[type="submit"]')
                await next_btn.wait_for(state="visible", timeout=10000)
                await next_btn.click()
                log("Форма step 1 отправлена, ждём ответа...")

                error_locator = page.locator('text="The desired email address is already taken"')
                step_two_locator = page.locator('select#mbo_registration_step_two_salutation')

                try:
                    await error_locator.or_(step_two_locator).wait_for(state="visible", timeout=15000)
                    if await error_locator.is_visible():
                        log(f"Email {account_data['email']} занят. Возвращаем комбо и берём другое...")
                        name_gen.release(account_data['combo_id'])
                        account_data = None
                        continue
                    else:
                        log("Успех! Email свободен, форма перешла на второй шаг.")
                        email_found = True
                        break
                except Exception as e_step:
                    log(f"Форма не дала ответа за 15 секунд: {type(e_step).__name__}: {e_step}")
                    log(f"  Текущий URL: {page.url}")
                    raise Exception("Прокси тормозит или форма зависла.")

            if not email_found:
                raise Exception("Не удалось найти свободный email за отведённое число попыток.")

            await page.wait_for_timeout(3000)

            gender_map = {'M': 'mr', 'F': 'ms'}
            salutation_value = gender_map.get(account_data['gender'], 'no_title')

            salutation_select = page.locator('select#mbo_registration_step_two_salutation')
            await salutation_select.wait_for(state="visible", timeout=10000)
            await salutation_select.select_option(value=salutation_value)

            first_name_input = page.locator('input[name="mbo_registration_step_two[firstName]"]')
            await first_name_input.fill(account_data['first_name'])

            last_name_input = page.locator('input[name="mbo_registration_step_two[lastName]"]')
            await last_name_input.fill(account_data['last_name'])

            country_select = page.locator('select#mbo_registration_step_two_country')
            await country_select.select_option(value=account_data['country'])
            log(f"Успешно выбрана страна: {account_data['country']}")

            log("Решаем капчу...")
            try:
                await solve_captcha(page)
            except Exception as e_captcha:
                log(f"Капча FAILED: {type(e_captcha).__name__}: {e_captcha}")
                raise

            checkbox1 = page.locator('input[name="mbo_registration_step_two[acceptTerms]"]')
            await checkbox1.evaluate("el => el.click()")
            await page.wait_for_timeout(1000)

            checkbox2 = page.locator('input[name="mbo_registration_step_two[acknowledgeWithdrawal]"]')
            await checkbox2.evaluate("el => el.click()")
            await page.wait_for_timeout(2000)

            submit_btn = page.locator('button[name="mbo_registration_step_two[next]"]')
            log("Ожидаем активации кнопки регистрации...")
            try:
                await page.wait_for_function(
                    'document.querySelector("button[name=\\"mbo_registration_step_two[next]\\"]").disabled === false',
                    timeout=20000,
                )
            except Exception:
                log("Кнопка всё ещё заблокирована. Снимаем принудительно!")
                await submit_btn.evaluate("el => el.removeAttribute('disabled')")

            log("Нажимаем 'Open account now'...")
            await submit_btn.evaluate("el => el.click()")

            try:
                later_btn = page.locator('button[name="mbo_registration_recovery[later]"]')
                await later_btn.wait_for(state="visible", timeout=30000)
                await later_btn.click()
                log("Шаг восстановления пропущен.")
            except Exception as e_later:
                log(f"Шаг восстановления не появился: {type(e_later).__name__}: {e_later}")
                log(f"  URL: {page.url}")

            new_account = MailboxAccount.objects.create(
                email=f"{account_data['email']}@mailbox.org",
                password=account_password,
                first_name=account_data['first_name'],
                last_name=account_data['last_name'],
                country=account_data['country'],
                gender=account_data['gender'],
                created_at=datetime.datetime.now(),
                provider='Mailbox.org',
                status='New',
                used_pattern=account_data['pattern_used'],
            )

            log(f"Аккаунт {new_account.email} успешно сохранён! (combo_id={account_data['combo_id']} закрыт)")
            return new_account

        except Exception as e:
            log(f"Ошибка при регистрации (attempt {attempt}): {type(e).__name__}: {e}")

            if account_data and 'combo_id' in account_data:
                try:
                    name_gen.release(account_data['combo_id'])
                    log(f"  → combo_id={account_data['combo_id']} возвращён в пул")
                except Exception as e_rel:
                    log(f"  → не удалось вернуть combo_id={account_data['combo_id']}: {e_rel}")

            log(f"Спроба {attempt} не удалась. Закрываем контекст и пробуем снова...")
            continue

        finally:
            if context:
                try:
                    await context.close()
                except Exception:
                    pass

    log(f"Не удалось создать аккаунт для {country} после {MAX_RETRIES_PER_ACCOUNT} попыток.")
    return None


async def main_async(target_countries: List[str] = None):
    log(f"\n{'#' * 30} ЗАПУСК АСИНХРОННОЙ ГЕНЕРАЦИИ {'#' * 30}")

    if target_countries:
        countries = target_countries
    else:
        countries = list(
            NameCombination.objects
            .filter(is_used=False)
            .values_list('country', flat=True)
            .distinct()
        )
        if not countries:
            log("Нет доступных стран (нет свободных комбинаций). Завершение.")
            return



    log(f"Параллельных воркеров: {CONCURRENT_WORKERS}")
    log(f"Лимит на КАЖДУЮ страну: {LIMIT_PER_COUNTRY}")

    name_generators = {country: DatabaseNameGenerator(country) for country in countries}

    # Счётчики по странам
    successes: Dict[str, int] = {c: 0 for c in countries}   # успешно создано
    inflight:  Dict[str, int] = {c: 0 for c in countries}   # сейчас в работе (зарезервировано)

    def free_countries() -> List[str]:
        return [
            c for c in countries
            if successes.get(c, 0) + inflight.get(c, 0) < LIMIT_PER_COUNTRY
        ]

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-infobars',
                '--disable-dev-shm-usage',
                '--no-sandbox',
            ]
        )

        semaphore = asyncio.Semaphore(CONCURRENT_WORKERS)
        stop_flag = False

        async def worker():
            nonlocal stop_flag
            while not stop_flag:
                available = free_countries()
                if not available:
                    log("Все страны достигли лимита. Останавливаем работу.")
                    stop_flag = True
                    break

                country = random.choice(available)
                inflight[country] += 1  # резервируем слот ДО await

                async with semaphore:
                    if stop_flag:
                        inflight[country] -= 1
                        break

                    name_gen = name_generators[country]
                    slot_number = successes[country] + 1
                    result = await register_one_account(country, browser, name_gen, slot_number)

                    inflight[country] -= 1

                    if result is not None:
                        successes[country] += 1
                        log(f"  [{country}] успешно: {successes[country]}/{LIMIT_PER_COUNTRY}")
                    else:
                        free_combos = NameCombination.objects.filter(
                            country=country, is_used=False
                        ).count()
                        if free_combos == 0:
                            log(f"Страна {country} исчерпала комбинации. Удаляем из пула.")
                            if country in countries:
                                countries.remove(country)
                            if not countries:
                                log("Все страны исчерпали комбинации. Останавливаем работу.")
                                stop_flag = True
                                break

        tasks = [asyncio.create_task(worker()) for _ in range(CONCURRENT_WORKERS)]
        try:
            await asyncio.gather(*tasks)
        except KeyboardInterrupt:
            log("\nОстановка по запросу пользователя.")
        finally:
            await browser.close()
            total = sum(successes.values())
            log(f"\nИтог по странам: {successes}")
            log(f"Всего успешно создано аккаунтов — {total}")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        target_countries = [c.strip().upper() for c in sys.argv[1].split(',') if c.strip()]
    else:
        target_countries = None

    asyncio.run(main_async(target_countries))