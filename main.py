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
CONTEXT_ROTATE_EVERY = 3      # rotate browser context after N URLs
PAGE_TIMEOUT = 60_000         # ms
DETAIL_TIMEOUT = 20_000       # ms for job-detail pages

ua = UserAgent()

URLS = [
    # HealthJobsUK — newest first (general + per-trust)
    # "https://www.healthjobsuk.com/job_list?JobSearch_Submit=Search&_srt=publicationdate&_sd=desc",
    # "https://www.healthjobsuk.com/job_list?JobSearch_q=&JobSearch_d=534&JobSearch_g=&JobSearch_re=_POST&JobSearch_re_0=1&JobSearch_re_1=1-_-_-&JobSearch_re_2=1-_-_--_-_-&JobSearch_Submit=Search&_tr=JobSearch&_ts=64082&_srt=startdate&_sd=d",
    # "https://www.healthjobsuk.com/job_list?JobSearch_q=&JobSearch_d=737&JobSearch_g=&JobSearch_re=_POST&JobSearch_re_0=1&JobSearch_re_1=1-_-_-&JobSearch_re_2=1-_-_--_-_-&JobSearch_Submit=Search&_tr=JobSearch&_ts=81534&_srt=startdate&_sd=a",
    # "https://www.healthjobsuk.com/job_list?JobSearch_q=&JobSearch_d=594&JobSearch_g=&JobSearch_re=_POST&JobSearch_re_0=1&JobSearch_re_1=1-_-_-&JobSearch_re_2=1-_-_--_-_-&JobSearch_Submit=Search&_tr=JobSearch&_ts=88730&_srt=startdate&_sd=a",
    # "https://www.healthjobsuk.com/job_list?JobSearch_q=&JobSearch_d=572&JobSearch_g=&JobSearch_re=_POST&JobSearch_re_0=1&JobSearch_re_1=1-_-_-&JobSearch_re_2=1-_-_--_-_-&JobSearch_Submit=Search&_tr=JobSearch&_ts=97667&_srt=startdate&_sd=a",
    # "https://www.healthjobsuk.com/job_list?JobSearch_q=&JobSearch_d=558&JobSearch_g=&JobSearch_re=_POST&JobSearch_re_0=1&JobSearch_re_1=1-_-_-&JobSearch_re_2=1-_-_--_-_-&JobSearch_Submit=Search&_tr=JobSearch&_ts=110250&_srt=startdate&_sd=a",
    # "https://www.healthjobsuk.com/job_list?JobSearch_q=&JobSearch_d=581&JobSearch_g=&JobSearch_re=_POST&JobSearch_re_0=1&JobSearch_re_1=1-_-_-&JobSearch_re_2=1-_-_--_-_-&JobSearch_Submit=Search&_tr=JobSearch&_ts=44291&_srt=startdate&_sd=a",
    # NHS Jobs England
    # "https://www.jobs.nhs.uk/candidate/search/results?keyword=doctor&sort=publicationDateDesc",
    # "https://www.jobs.nhs.uk/candidate/search/results?searchFormType=sortBy&sort=publicationDateDesc&searchByLocationOnly=true&language=en",
    # # HSCNI (Northern Ireland)
    # "https://jobs.hscni.net/Search?SearchCatID=0",
    # Scotland
    "https://apply.jobs.scot.nhs.uk/Home/Job"
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

# ================= VIEWPORTS (randomised) ================= #
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
def load_seen() -> set:
    try:
        with open("seen_jobs.txt", "r") as f:
            return set(f.read().splitlines())
    except FileNotFoundError:
        return set()

def save_seen(job_id: str):
    with open("seen_jobs.txt", "a") as f:
        f.write(job_id + "\n")

# ================= TELEGRAM ================= #
def send_telegram(message: str):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "HTML"}
    backoff = 5
    for attempt in range(5):
        try:
            r = requests.post(url, data=payload, timeout=10)
            if r.status_code == 200:
                log(f"✅ Telegram sent (attempt {attempt + 1})")
                return
            elif r.status_code == 429:
                retry_after = r.json().get("parameters", {}).get("retry_after", backoff)
                log(f"⚠️  Telegram rate-limited. Sleeping {retry_after}s")
                time.sleep(retry_after)
                backoff *= 2
            else:
                log(f"❌ Telegram error {r.status_code}: {r.text[:200]}")
                return
        except Exception as e:
            log(f"❌ Telegram exception: {e}")
            time.sleep(backoff)
            backoff *= 2

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
    match = re.search(r"\d{4,}", link)   # at least 4 digits = real ID
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
    """Scroll down the page in a human-like, randomised fashion."""
    try:
        total_height = await page.evaluate("document.body.scrollHeight")
        viewport_height = page.viewport_size["height"] if page.viewport_size else 768
        scrolled = 0
        while scrolled < total_height:
            step = random.randint(300, 700)
            scrolled += step
            await page.mouse.wheel(0, step)
            await asyncio.sleep(random.uniform(0.3, 0.9))
        # Scroll back up a bit — humans often do this
        await page.mouse.wheel(0, -random.randint(200, 500))
        await asyncio.sleep(random.uniform(0.5, 1.2))
    except Exception:
        pass

async def random_mouse_move(page):
    """Move the mouse to a random position to simulate human presence."""
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
            "--disable-blink-features=AutomationControlled",  # hides webdriver flag
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
    # Persist cookies between pages in the same context
    await context.add_init_script("""
        // Remove navigator.webdriver flag
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        // Fake plugins array
        Object.defineProperty(navigator, 'plugins', { get: () => [1,2,3,4,5] });
        // Fake languages
        Object.defineProperty(navigator, 'languages', { get: () => ['en-GB', 'en'] });
        // Chrome runtime object
        window.chrome = { runtime: {} };
    """)
    return browser, context

# ================= SITE-SPECIFIC PARSERS ================= #

def parse_healthjobsuk(soup: BeautifulSoup, base: str) -> list[dict]:
    """Return list of {title, link} for HealthJobsUK listing pages."""
    jobs = []
    # Primary: article/li elements with job links
    for a in soup.select("a[href*='/job/']"):
        href = normalize_link(a["href"], base)
        text = a.get_text(strip=True)
        if text and len(text) > 5:
            jobs.append({"title": text, "link": href, "needs_detail": True})
    return jobs


def parse_nhsjobs(soup: BeautifulSoup, base: str) -> list[dict]:
    """Return list of {title, link} for jobs.nhs.uk."""
    jobs = []
    # Job cards have <a> with href matching /candidate/jobadvert/
    for a in soup.select("a[href*='/Job/']"):
        href = normalize_link(a["href"], base)
        text = a.get_text(strip=True)
        if text and len(text) > 5:
            jobs.append({"title": text, "link": href, "needs_detail": False})
    # Fallback: any anchor whose text looks like a job title
    if not jobs:
        for a in soup.find_all("a", href=True):
            if "/Job/" in a["href"] or "/job/" in a["href"]:
                text = a.get_text(strip=True)
                if text and len(text) > 5:
                    jobs.append({"title": text,
                                 "link": normalize_link(a["href"], base),
                                 "needs_detail": False})
    return jobs


def parse_hscni(soup: BeautifulSoup, base: str) -> list[dict]:
    """Return list of {title, link} for jobs.hscni.net."""
    jobs = []
    for a in soup.select("a[href*='/Job/'], a[href*='/job/'], a[href*='JobID=']"):
        href = normalize_link(a["href"], base)
        text = a.get_text(strip=True)
        if text and len(text) > 5:
            jobs.append({"title": text, "link": href, "needs_detail": False})
    return jobs


def parse_scotland(soup: BeautifulSoup, base: str) -> list[dict]:
    """Return list of {title, link} for apply.jobs.scot.nhs.uk.

    The listing page link text is often generic ("View", "Apply", etc.)
    so we always fetch the detail page to get the real <h1> job title.
    Duplicates by JobId are de-duped before any detail fetch is attempted.
    """
    seen_ids: set = set()
    jobs = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "JobId=" not in href and "JobDetail" not in href:
            continue
        full = normalize_link(href, base)
        # Extract JobId so we don't queue the same vacancy twice
        # (listing pages often have multiple links per row)
        job_id_match = re.search(r"JobId=(\d+)", href)
        uid = job_id_match.group(1) if job_id_match else full
        if uid in seen_ids:
            continue
        seen_ids.add(uid)
        text = a.get_text(strip=True)
        jobs.append({"title": text, "link": full, "needs_detail": True})
    return jobs


def parse_generic(soup: BeautifulSoup, base: str) -> list[dict]:
    """Fallback: grab any link whose text might be a job title."""
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
    """Navigate to URL with exponential-backoff retry. Returns True on success."""
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
    """Open a job detail page and return the <h1> title, or None on failure."""
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

# ================= MAIN SCRAPER ================= #
async def check_site(url: str, seen_jobs: set, context) -> int:
    """Scrape one URL; return number of new jobs found."""
    log(f"🔍 Checking: {url}")
    page = await context.new_page()
    new_jobs = 0
    base = get_base(url)
    parser = get_parser(url)

    try:
        await stealth_async(page)
        # Pre-navigation jitter so requests don't look machine-paced
        await asyncio.sleep(random.uniform(2, 6))

        ok = await goto_with_retry(page, url)
        if not ok:
            log(f"⛔ Giving up on {url}.")
            return 0

        # Human-like interaction before scraping
        await random_mouse_move(page)
        await asyncio.sleep(random.uniform(1, 2.5))
        await human_scroll(page)

        content = await page.content()
        soup = BeautifulSoup(content, "html.parser")
        candidates = parser(soup, base)

        log(f"   Found {len(candidates)} candidate links.")

        for job in candidates:
            try:
                title = job["title"]
                link = job["link"]

                # Fetch detail page when listing link text is unreliable
                if job.get("needs_detail"):
                    job_id = extract_job_id(link)
                    if job_id in seen_jobs:
                        continue
                    detail_title = await fetch_detail_title(context, link)
                    log(f"   Scotland detail title: {detail_title!r}")
                    if detail_title:
                        title = detail_title
                    await asyncio.sleep(random.uniform(1, 2.5))

                if not relevant_job(title):
                    continue

                job_id = extract_job_id(link)
                if job_id in seen_jobs:
                    continue

                message = (
                    f"🚨 <b>NEW NHS JOB</b>\n\n"
                    f"🏥 <b>{title}</b>\n"
                    f"🔗 {link}"
                )
                log(f"   🆕 NEW JOB: {title}")
                send_telegram(message)
                save_seen(job_id)
                seen_jobs.add(job_id)
                new_jobs += 1

                # Brief cooldown between Telegram sends
                await asyncio.sleep(random.uniform(1, 2))

            except Exception as e:
                log(f"   ⚠️  Error processing job entry: {e}")

        log(f"   ✅ Done — {new_jobs} new jobs found.")

    except Exception as e:
        log(f"❌ SCRAPER ERROR on {url}: {e}")
    finally:
        await page.close()

    return new_jobs


# ================= ENTRY POINT ================= #
async def main():
    log("🚀 NHS JOB BOT STARTED (stealth + anti-block mode)")
    seen_jobs = load_seen()
    log(f"   Loaded {len(seen_jobs)} previously seen job IDs.")

    async with async_playwright() as p:
        browser, context = await create_context(p)
        urls_checked = 0

        while True:
            for url in URLS:
                # Rotate context every N URLs to avoid fingerprint accumulation
                if urls_checked > 0 and urls_checked % CONTEXT_ROTATE_EVERY == 0:
                    log("🔄 Rotating browser context...")
                    try:
                        await context.close()
                        await browser.close()
                    except Exception:
                        pass
                    browser, context = await create_context(p)

                try:
                    await check_site(url, seen_jobs, context)
                except Exception as e:
                    log(f"⚠️  Unhandled error on {url}: {e}. Recreating context...")
                    try:
                        await context.close()
                        await browser.close()
                    except Exception:
                        pass
                    browser, context = await create_context(p)

                urls_checked += 1
                # Inter-URL jitter — looks like a human tabbing between sites
                await asyncio.sleep(random.uniform(6, 15))

            log(f"💤 Full cycle done. Sleeping {CHECK_INTERVAL}s before next cycle.\n")
            await asyncio.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    asyncio.run(main())
