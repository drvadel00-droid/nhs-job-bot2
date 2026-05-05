import asyncio
import random
import re
import time
import json
import requests
from datetime import datetime
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright, TimeoutError as PWTimeout
from playwright_stealth import stealth_async
from fake_useragent import UserAgent

# ================= CONFIG ================= #
BOT_TOKEN = "8213751012:AAFYvubDXeY3xU8vjaWLxNTT7XqMtPhUuwQ"
CHAT_ID = "-1003888963521"
CHECK_INTERVAL = 120          # seconds between full cycles
PAGE_TIMEOUT = 60_000         # ms
DETAIL_TIMEOUT = 20_000       # ms for job-detail pages
TELEGRAM_SEND_INTERVAL = 1.0  # seconds between Telegram messages

ua = UserAgent()

URLS = [
    # HealthJobsUK — newest first (general + per-trust)
    "https://www.healthjobsuk.com/job_list?JobSearch_Submit=Search&_srt=publicationdate&_sd=desc",
    "https://www.healthjobsuk.com/job_list?JobSearch_q=&JobSearch_d=534&JobSearch_g=&JobSearch_re=_POST&JobSearch_re_0=1&JobSearch_re_1=1-_-_-&JobSearch_re_2=1-_-_--_-_-&JobSearch_Submit=Search&_tr=JobSearch&_ts=64082&_srt=startdate&_sd=d",
    "https://www.healthjobsuk.com/job_list?JobSearch_q=&JobSearch_d=737&JobSearch_g=&JobSearch_re=_POST&JobSearch_re_0=1&JobSearch_re_1=1-_-_-&JobSearch_re_2=1-_-_--_-_-&JobSearch_Submit=Search&_tr=JobSearch&_ts=81534&_srt=startdate&_sd=a",
    "https://www.healthjobsuk.com/job_list?JobSearch_q=&JobSearch_d=594&JobSearch_g=&JobSearch_re=_POST&JobSearch_re_0=1&JobSearch_re_1=1-_-_-&JobSearch_re_2=1-_-_--_-_-&JobSearch_Submit=Search&_tr=JobSearch&_ts=88730&_srt=startdate&_sd=a",
    "https://www.healthjobsuk.com/job_list?JobSearch_q=&JobSearch_d=572&JobSearch_g=&JobSearch_re=_POST&JobSearch_re_0=1&JobSearch_re_1=1-_-_-&JobSearch_re_2=1-_-_--_-_-&JobSearch_Submit=Search&_tr=JobSearch&_ts=97667&_srt=startdate&_sd=a",
    "https://www.healthjobsuk.com/job_list?JobSearch_q=&JobSearch_d=558&JobSearch_g=&JobSearch_re=_POST&JobSearch_re_0=1&JobSearch_re_1=1-_-_-&JobSearch_re_2=1-_-_--_-_-&JobSearch_Submit=Search&_tr=JobSearch&_ts=110250&_srt=startdate&_sd=a",
    "https://www.healthjobsuk.com/job_list?JobSearch_q=&JobSearch_d=581&JobSearch_g=&JobSearch_re=_POST&JobSearch_re_0=1&JobSearch_re_1=1-_-_-&JobSearch_re_2=1-_-_--_-_-&JobSearch_Submit=Search&_tr=JobSearch&_ts=44291&_srt=startdate&_sd=a",
    # NHS Jobs England
    "https://www.jobs.nhs.uk/candidate/search/results?staffGroup=MEDICAL_AND_DENTAL&payRange=40-50%2C50-60%2C60-70&searchFormType=sortBy&sort=publicationDateDesc&language=en#",
    # HSCNI (Northern Ireland)
    "https://jobs.hscni.net/Search?SearchCatID=0",
    # Scotland
    "https://apply.jobs.scot.nhs.uk/Home/Job",
]

# ================= FILTERS ================= #
MEDICAL_SPECIALTIES = [
    "medicine", "acute", "internal", "general medicine",
    "surgery", "general surgery", "trauma", "orthopaedic",
    "plastic", "emergency", "cardiology", "respiratory",
    "gastro", "neurology", "paediatric", "haematology",
    "intensive care", "critical care", "icu", "vascular", "urology",
]

GRADE_KEYWORDS = [
    "fy1", "fy2", "foundation",
    "ct1", "ct2", "ct3",
    "st1", "st2", "st3",
    "registrar",
    "trust doctor", "trust grade",
    "clinical fellow", "junior fellow", "junior clinical fellow",
    "specialty doctor",
    "junior",
    "locum doctor",
]

EXCLUDE_KEYWORDS = [
    "consultant", "st4", "st5", "st6", "st7",
    "nurse", "midwife", "assistant",
    "manager", "director", "admin",
    "physiotherapist", "radiographer",
    "lead", "scientist", "receptionist", "housekeeper",
    "cook", "clerk", "practitioner", "nutritionist",
    "nutrition", "coordinator", "therapist", "secretary",
    "pharmacist", "matron", "worker",
]

VIEWPORTS = [
    {"width": 1920, "height": 1080},
    {"width": 1440, "height": 900},
    {"width": 1366, "height": 768},
    {"width": 1536, "height": 864},
    {"width": 1280, "height": 800},
]

# ================= LOGGING ================= #
def log(message: str):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {message}", flush=True)

# ================= SEEN-JOBS PERSISTENCE ================= #
# Guarded by an asyncio.Lock so parallel tasks don't race on the file.
_seen_lock = asyncio.Lock()

def load_seen() -> set:
    try:
        with open("seen_jobs.txt", "r") as f:
            return set(f.read().splitlines())
    except FileNotFoundError:
        return set()

async def async_save_seen(job_id: str):
    async with _seen_lock:
        with open("seen_jobs.txt", "a") as f:
            f.write(job_id + "\n")

# ================= TELEGRAM QUEUE ================= #
# All scraper tasks push messages here; a single consumer drains it,
# waiting TELEGRAM_SEND_INTERVAL between sends to avoid 429s.
_tg_queue: asyncio.Queue = asyncio.Queue()

async def telegram_consumer():
    """Drain the Telegram queue, one message per second."""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    while True:
        message = await _tg_queue.get()
        if message is None:          # sentinel → shut down
            _tg_queue.task_done()
            break
        payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "HTML"}
        backoff = 5
        for attempt in range(5):
            try:
                r = requests.post(url, data=payload, timeout=10)
                if r.status_code == 200:
                    log(f"✅ Telegram sent (attempt {attempt + 1})")
                    break
                elif r.status_code == 429:
                    retry_after = r.json().get("parameters", {}).get("retry_after", backoff)
                    log(f"⚠️  Telegram rate-limited. Sleeping {retry_after}s")
                    await asyncio.sleep(retry_after)
                    backoff *= 2
                else:
                    log(f"❌ Telegram error {r.status_code}: {r.text[:200]}")
                    break
            except Exception as e:
                log(f"❌ Telegram exception: {e}")
                await asyncio.sleep(backoff)
                backoff *= 2
        _tg_queue.task_done()
        # Pace sends to avoid hitting Telegram's rate limit
        await asyncio.sleep(TELEGRAM_SEND_INTERVAL)

def enqueue_telegram(message: str):
    """Non-blocking push onto the Telegram queue (safe from any coroutine)."""
    _tg_queue.put_nowait(message)

# ================= FILTER LOGIC ================= #
def relevant_job(title: str) -> bool:
    t = title.lower()
    if any(ex in t for ex in EXCLUDE_KEYWORDS):
        return False
    if not any(sp in t for sp in MEDICAL_SPECIALTIES):
        return False
    if not any(gr in t for gr in GRADE_KEYWORDS):
        return False
    return True

def extract_job_id(link: str) -> str:
    match = re.search(r"\d{4,}", link)
    return match.group() if match else link

def normalize_link(href: str, base: str) -> str:
    if href.startswith("http"):
        return href
    if href.startswith("/"):
        return base.rstrip("/") + href
    return href

def get_base(url: str) -> str:
    m = re.match(r"(https?://[^/]+)", url)
    return m.group(1) if m else ""

# ================= HUMAN-LIKE HELPERS ================= #
async def human_scroll(page):
    try:
        total_height = await page.evaluate("document.body.scrollHeight")
        viewport_height = page.viewport_size["height"] if page.viewport_size else 768
        scrolled = 0
        while scrolled < total_height:
            step = random.randint(300, 700)
            scrolled += step
            await page.mouse.wheel(0, step)
            await asyncio.sleep(random.uniform(0.3, 0.9))
        await page.mouse.wheel(0, -random.randint(200, 500))
        await asyncio.sleep(random.uniform(0.5, 1.2))
    except Exception:
        pass

async def random_mouse_move(page):
    try:
        vp = page.viewport_size or {"width": 1280, "height": 800}
        x = random.randint(100, vp["width"] - 100)
        y = random.randint(100, vp["height"] - 100)
        await page.mouse.move(x, y)
    except Exception:
        pass

# ================= BROWSER FACTORY ================= #
async def create_context(playwright):
    """Launch a fresh Chromium browser and return (browser, context)."""
    browser = await playwright.chromium.launch(
        headless=True,
        args=[
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--disable-gpu",
            "--disable-setuid-sandbox",
            "--disable-blink-features=AutomationControlled",
            "--disable-infobars",
            "--window-size=1920,1080",
            "--start-maximized",
        ],
    )
    vp = random.choice(VIEWPORTS)
    context = await browser.new_context(
        user_agent=ua.random,
        viewport=vp,
        locale="en-GB",
        timezone_id="Europe/London",
        java_script_enabled=True,
        ignore_https_errors=False,
        extra_http_headers={
            "Accept-Language": "en-GB,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1",
            "Upgrade-Insecure-Requests": "1",
        },
    )
    await context.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        Object.defineProperty(navigator, 'plugins',   { get: () => [1,2,3,4,5] });
        Object.defineProperty(navigator, 'languages', { get: () => ['en-GB', 'en'] });
        window.chrome = { runtime: {} };
    """)
    return browser, context

# ================= SITE-SPECIFIC PARSERS ================= #
def parse_healthjobsuk(soup: BeautifulSoup, base: str) -> list[dict]:
    jobs = []
    for a in soup.select("a[href*='/job/']"):
        href = normalize_link(a["href"], base)
        text = a.get_text(strip=True)
        if text and len(text) > 5:
            jobs.append({"title": text, "link": href, "needs_detail": True})
    return jobs

def parse_nhsjobs(soup: BeautifulSoup, base: str) -> list[dict]:
    seen_ids: set = set()
    jobs = []
    for a in soup.select("a[href*='/candidate/jobadvert/']"):
        href = normalize_link(a["href"], base)
        uid = href.split("?")[0].rstrip("/").split("/")[-1]
        if uid in seen_ids:
            continue
        seen_ids.add(uid)
        text = a.get_text(strip=True)
        if text and len(text) > 5:
            jobs.append({"title": text, "link": href, "needs_detail": True})
    return jobs

def parse_hscni(soup: BeautifulSoup, base: str) -> list[dict]:
    jobs = []
    for a in soup.select("a[href*='/Job/'], a[href*='/job/'], a[href*='JobID=']"):
        href = normalize_link(a["href"], base)
        text = a.get_text(strip=True)
        if text and len(text) > 5:
            jobs.append({"title": text, "link": href, "needs_detail": True})
    return jobs

def parse_scotland(soup: BeautifulSoup, base: str) -> list[dict]:
    seen_ids: set = set()
    jobs = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "JobId=" not in href and "JobDetail" not in href:
            continue
        full = normalize_link(href, base)
        job_id_match = re.search(r"JobId=(\d+)", href)
        uid = job_id_match.group(1) if job_id_match else full
        if uid in seen_ids:
            continue
        seen_ids.add(uid)
        text = a.get_text(strip=True)
        jobs.append({"title": text, "link": full, "needs_detail": True})
    return jobs

def parse_generic(soup: BeautifulSoup, base: str) -> list[dict]:
    jobs = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "job" not in href.lower():
            continue
        text = a.get_text(strip=True)
        if text and len(text) > 8:
            jobs.append({"title": text, "link": normalize_link(href, base), "needs_detail": False})
    return jobs

def get_parser(url: str):
    if "healthjobsuk.com" in url:
        return parse_healthjobsuk
    if "jobs.nhs.uk" in url:
        return parse_nhsjobs
    if "hscni.net" in url:
        return parse_hscni
    if "jobs.scot.nhs.uk" in url:
        return parse_scotland
    return parse_generic

# ================= RETRY WRAPPER ================= #
async def goto_with_retry(page, url: str, retries: int = 3, timeout: int = PAGE_TIMEOUT) -> bool:
    backoff = 5
    for attempt in range(1, retries + 1):
        try:
            response = await page.goto(url, wait_until="networkidle", timeout=timeout)
            if response and response.status == 200:
                return True
            if response and response.status == 403:
                log(f"⛔ 403 on {url} (attempt {attempt}). Backing off {backoff}s.")
                await asyncio.sleep(backoff)
                backoff *= 2
            elif response:
                log(f"⚠️  HTTP {response.status} on {url} (attempt {attempt}).")
                return False
        except PWTimeout:
            log(f"⏱️  Timeout on {url} (attempt {attempt}). Retrying in {backoff}s.")
            await asyncio.sleep(backoff)
            backoff *= 2
        except Exception as e:
            log(f"❌ Error navigating {url}: {e} (attempt {attempt}).")
            await asyncio.sleep(backoff)
            backoff *= 2
    return False

# ================= DETAIL-PAGE TITLE FETCH ================= #
async def fetch_detail_title(context, link: str) -> str | None:
    page = await context.new_page()
    try:
        await stealth_async(page)
        await asyncio.sleep(random.uniform(1.5, 3.5))
        ok = await goto_with_retry(page, link, retries=2, timeout=DETAIL_TIMEOUT)
        if not ok:
            return None
        h1 = await page.query_selector("h1")
        if h1:
            return (await h1.inner_text()).strip()
    except Exception as e:
        log(f"Detail fetch error ({link}): {e}")
    finally:
        await page.close()
    return None

# ================= SINGLE-URL SCRAPER ================= #
async def check_site(url: str, seen_jobs: set, playwright) -> int:
    """
    Scrape one URL in its own dedicated browser context.
    Parallel-safe: uses _seen_lock for all seen_jobs mutations.
    New jobs are pushed onto _tg_queue instead of sent directly.
    """
    log(f"🔍 Checking: {url}")
    new_jobs = 0
    base = get_base(url)
    parser = get_parser(url)

    browser, context = await create_context(playwright)
    page = await context.new_page()

    try:
        await stealth_async(page)
        await asyncio.sleep(random.uniform(2, 6))

        ok = await goto_with_retry(page, url)
        if not ok:
            log(f"⛔ Giving up on {url}.")
            return 0

        await random_mouse_move(page)
        await asyncio.sleep(random.uniform(1, 2.5))
        await human_scroll(page)

        content = await page.content()
        soup = BeautifulSoup(content, "html.parser")
        candidates = parser(soup, base)
        log(f"   [{url[:60]}] Found {len(candidates)} candidate links.")

        for job in candidates:
            try:
                title = job["title"]
                link  = job["link"]

                if job.get("needs_detail"):
                    job_id = extract_job_id(link)
                    # Fast pre-check before spending time on the detail page
                    async with _seen_lock:
                        already_seen = job_id in seen_jobs
                    if already_seen:
                        continue

                    detail_title = await fetch_detail_title(context, link)
                    if detail_title:
                        title = detail_title
                    await asyncio.sleep(random.uniform(1, 2.5))

                if not relevant_job(title):
                    continue

                job_id = extract_job_id(link)

                # Atomic check-and-mark to prevent duplicate Telegram messages
                async with _seen_lock:
                    if job_id in seen_jobs:
                        continue
                    seen_jobs.add(job_id)

                message = (
                    f"🚨 <b>NEW NHS JOB</b>\n\n"
                    f"🏥 <b>{title}</b>\n"
                    f"🔗 {link}"
                )
                log(f"   🆕 NEW JOB: {title}")
                enqueue_telegram(message)
                await async_save_seen(job_id)
                new_jobs += 1

            except Exception as e:
                log(f"   ⚠️  Error processing job entry: {e}")

        log(f"   ✅ [{url[:60]}] Done — {new_jobs} new jobs found.")

    except Exception as e:
        log(f"❌ SCRAPER ERROR on {url}: {e}")
    finally:
        await page.close()
        try:
            await context.close()
            await browser.close()
        except Exception:
            pass

    return new_jobs


# ================= PARALLEL CYCLE ================= #
async def run_cycle(seen_jobs: set, playwright):
    """Fire all URLs concurrently and wait for every one to finish."""
    log(f"🚀 Starting parallel cycle over {len(URLS)} URLs…")
    tasks = [
        asyncio.create_task(check_site(url, seen_jobs, playwright))
        for url in URLS
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    total = 0
    for url, res in zip(URLS, results):
        if isinstance(res, Exception):
            log(f"⚠️  Task for {url[:60]} raised: {res}")
        else:
            total += res
    log(f"✅ Cycle complete — {total} new job(s) found across all URLs.")


# ================= ENTRY POINT ================= #
async def main():
    log("🚀 NHS JOB BOT STARTED (parallel + Telegram-queue mode)")
    seen_jobs = load_seen()
    log(f"   Loaded {len(seen_jobs)} previously seen job IDs.")

    # Start the Telegram consumer as a background task
    consumer_task = asyncio.create_task(telegram_consumer())

    async with async_playwright() as p:
        while True:
            await run_cycle(seen_jobs, p)
            log(f"💤 Sleeping {CHECK_INTERVAL}s before next cycle.\n")
            await asyncio.sleep(CHECK_INTERVAL)

    # Signal the consumer to stop (only reached on clean shutdown)
    await _tg_queue.put(None)
    await consumer_task


if __name__ == "__main__":
    asyncio.run(main())
