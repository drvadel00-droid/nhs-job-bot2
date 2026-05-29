import asyncio
import random
import re
import aiohttp
import gc
import os
import resource
from datetime import datetime
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright, TimeoutError as PWTimeout
from playwright_stealth import stealth_async
from fake_useragent import UserAgent

# ================= CONFIG ================= #
BOT_TOKEN = "8213751012:AAFYvubDXeY3xU8vjaWLxNTT7XqMtPhUuwQ"
CHAT_ID         = "-1003888963521"   # group — receives alerts with 5-min delay
EARLY_CHAT_ID   = "-1003967074726"       # personal — receives alerts immediately (5 min early)
EARLY_DELAY     = 300                # seconds the group waits after the personal alert

WHOP_API_KEY    = "apik_ud2gxqVNMTONA_A2052134_C_9990092af1338a1becd245e112caaac179d91e2e6bbf23cbb0e176ab43765a"
WHOP_CHANNEL_ID = "chat_feed_1CbW9WpgbzoeU9E9KQ5WpT"


CHECK_INTERVAL = 120          # seconds between full cycles
PAGE_TIMEOUT = 20_000         # ms
DETAIL_TIMEOUT = 15_000       # ms
SITE_HARD_LIMIT = 300         # seconds — hard kill per URL task
TELEGRAM_SEND_INTERVAL = 1.1
MAX_CONCURRENT_CONTEXTS = 3   # concurrent contexts inside the ONE shared browser
PLAYWRIGHT_RECYCLE_EVERY = 120 # recreate browser every N cycles

ua = UserAgent()

URLS = [
    # HealthJobsUK
    "https://www.healthjobsuk.com/job_list?JobSearch_Submit=Search&_srt=publicationdate&_sd=desc",
    "https://www.healthjobsuk.com/job_list?JobSearch_q=&JobSearch_d=534&JobSearch_g=&JobSearch_re=_POST&JobSearch_re_0=1&JobSearch_re_1=1-_-_-&JobSearch_re_2=1-_-_--_-_-&JobSearch_Submit=Search&_tr=JobSearch&_ts=64082&_srt=startdate&_sd=d",
    "https://www.healthjobsuk.com/job_list?JobSearch_q=&JobSearch_d=737&JobSearch_g=&JobSearch_re=_POST&JobSearch_re_0=1&JobSearch_re_1=1-_-_-&JobSearch_re_2=1-_-_--_-_-&JobSearch_Submit=Search&_tr=JobSearch&_ts=81534&_srt=startdate&_sd=a",
    "https://www.healthjobsuk.com/job_list?JobSearch_q=&JobSearch_d=594&JobSearch_g=&JobSearch_re=_POST&JobSearch_re_0=1&JobSearch_re_1=1-_-_-&JobSearch_re_2=1-_-_--_-_-&JobSearch_Submit=Search&_tr=JobSearch&_ts=88730&_srt=startdate&_sd=a",
    "https://www.healthjobsuk.com/job_list?JobSearch_q=&JobSearch_d=572&JobSearch_g=&JobSearch_re=_POST&JobSearch_re_0=1&JobSearch_re_1=1-_-_-&JobSearch_re_2=1-_-_--_-_-&JobSearch_Submit=Search&_tr=JobSearch&_ts=97667&_srt=startdate&_sd=a",
    "https://www.healthjobsuk.com/job_list?JobSearch_q=&JobSearch_d=558&JobSearch_g=&JobSearch_re=_POST&JobSearch_re_0=1&JobSearch_re_1=1-_-_-&JobSearch_re_2=1-_-_--_-_-&JobSearch_Submit=Search&_tr=JobSearch&_ts=110250&_srt=startdate&_sd=a",
    "https://www.healthjobsuk.com/job_list?JobSearch_q=&JobSearch_d=581&JobSearch_g=&JobSearch_re=_POST&JobSearch_re_0=1&JobSearch_re_1=1-_-_-&JobSearch_re_2=1-_-_--_-_-&JobSearch_Submit=Search&_tr=JobSearch&_ts=44291&_srt=startdate&_sd=a",
    # NHS Jobs England
    "https://www.jobs.nhs.uk/candidate/search/results?staffGroup=MEDICAL_AND_DENTAL&payRange=40-50%2C50-60%2C60-70&searchFormType=sortBy&sort=publicationDateDesc&language=en",
    # HSCNI (Northern Ireland)
    "https://jobs.hscni.net/Search?SearchCatID=0",
    # Scotland
    "https://apply.jobs.scot.nhs.uk/Home/Job",
]

# ================= FILTERS ================= #

# ---- CHAT_ID (group, broad filter) ----
CHAT_SPECIALTIES = [
    "medicine", "acute", "internal", "general", "medicine",
    "surgery", "general surgery", "trauma", "orthopaedic",
    "plastic", "emergency", "cardiology", "respiratory",
    "gastro", "neurology", "paediatric", "haematology",
    "intensive care", "critical care", "icu", "vascular", "urology",
    "obstetrics", "gynaecology", "gynecology", "anesthesia",
]
CHAT_GRADE_KEYWORDS = [
    "fy1", "fy2", "foundation", "st4", "st5", "st6", "st7",
    "ct1", "ct2", "ct3",
    "st1", "st2", "st3",
    "registrar",
    "trust", "doctor", "grade",
    "clinical", "fellow",
    "specialty",
    "junior",
    "locum", "doctor", "teaching", "senior",
]
CHAT_EXCLUDE_KEYWORDS = [
    "consultant",
    "nurse", "midwife", "assistant",
    "manager", "director", "admin",
    "physiotherapist", "radiographer",
    "lead", "scientist", "receptionist", "housekeeper",
    "cook", "clerk", "practitioner", "nutritionist",
    "nutrition", "coordinator", "therapist", "secretary",
    "pharmacist", "matron", "worker", "pharmacy", "chief", "counseling", "principal",
]

# ---- EARLY_CHAT_ID (personal, narrow filter) ----
EARLY_SPECIALTIES = [
    "medicine", "acute", "internal", "general", "medicine",
    "surgery", "general surgery", "trauma", "orthopaedic",
    "plastic", "emergency", "cardiology", "respiratory",
    "gastro", "neurology", "paediatric", "haematology",
    "intensive care", "critical care", "icu", "vascular", "urology", "rheumatology",
]
EARLY_GRADE_KEYWORDS = [
    "fy1", "fy2", "foundation",
    "ct1", "ct2", "ct3",
    "st1", "st2", "st3",
    "registrar",
    "trust", "doctor", "grade",
    "clinical", "fellow",
    "specialty",
    "junior",
    "locum", "doctor", "teaching",
]
EARLY_EXCLUDE_KEYWORDS = [
    "consultant", "st4", "st5", "st6", "st7", "cct",
    "nurse", "midwife", "assistant",
    "manager", "director", "admin",
    "physiotherapist", "radiographer",
    "lead", "scientist", "receptionist", "housekeeper",
    "cook", "clerk", "practitioner", "nutritionist",
    "nutrition", "coordinator", "therapist", "secretary",
    "pharmacist", "matron", "worker", "pharmacy", "chief", "psychiatry",
    "maxillofacial", "counseling", "principal",
]

VIEWPORTS = [
    {"width": 1920, "height": 1080},
    {"width": 1440, "height": 900},
    {"width": 1366, "height": 768},
    {"width": 1536, "height": 864},
    {"width": 1280, "height": 800},
]

# ================= LOGGING ================= #
def log(msg: str):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)

# ================= SEEN-JOBS PERSISTENCE ================= #
_seen_lock = asyncio.Lock()
SEEN_JOBS_PATH = os.environ.get("SEEN_JOBS_PATH", "seen_jobs.txt")

def load_seen() -> set:
    try:
        with open(SEEN_JOBS_PATH, "r") as f:
            return set(f.read().splitlines())
    except FileNotFoundError:
        return set()

async def async_save_seen(job_id: str):
    async with _seen_lock:
        with open(SEEN_JOBS_PATH, "a") as f:
            f.write(job_id + "\n")

# ================= TELEGRAM QUEUE ================= #
# Each queue item is a (chat_id, message_text) tuple.
_tg_queue: asyncio.Queue = asyncio.Queue()

async def _send_one(session: aiohttp.ClientSession, chat_id: str, msg: str):
    """Send a single message to one chat_id with retry/backoff logic."""
    api_url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": msg, "parse_mode": "HTML"}
    backoff = 5
    for attempt in range(5):
        try:
            async with session.post(
                api_url, data=payload,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as r:
                if r.status == 200:
                    log(f"✅ Telegram sent → {chat_id}")
                    return
                elif r.status == 429:
                    body = await r.json()
                    wait = body.get("parameters", {}).get("retry_after", backoff)
                    log(f"⚠️  Telegram 429 (chat {chat_id}) — retry_after={wait}s")
                    await asyncio.sleep(wait)
                    backoff = max(backoff * 2, wait + 1)
                else:
                    text = await r.text()
                    log(f"❌ Telegram HTTP {r.status} (chat {chat_id}): {text[:200]}")
                    return
        except asyncio.TimeoutError:
            log(f"❌ Telegram send timed out (attempt {attempt + 1}, chat {chat_id})")
            await asyncio.sleep(backoff)
            backoff *= 2
        except Exception as e:
            log(f"❌ Telegram exception (chat {chat_id}): {e}")
            await asyncio.sleep(backoff)
            backoff *= 2


async def telegram_consumer():
    """
    Drain _tg_queue.  Each item is (chat_id, text).
    Items are placed here by enqueue_telegram(); the delayed group send
    is handled separately via _schedule_group_send().
    """
    async with aiohttp.ClientSession() as session:
        while True:
            item = await _tg_queue.get()
            if item is None:
                _tg_queue.task_done()
                break
            chat_id, msg = item
            await _send_one(session, chat_id, msg)
            _tg_queue.task_done()
            await asyncio.sleep(TELEGRAM_SEND_INTERVAL)


async def _send_whop(session: aiohttp.ClientSession, msg: str):
    """Send a plain-text message to the Whop chat channel."""
    url = "https://api.whop.com/api/v1/messages"
    headers = {
        "Authorization": f"Bearer {WHOP_API_KEY}",
        "Content-Type": "application/json",
    }
    plain = re.sub(r"<[^>]+>", "", msg)
    payload = {"content": plain, "channel_id": WHOP_CHANNEL_ID}
    backoff = 5
    for attempt in range(4):
        try:
            async with session.post(
                url, json=payload, headers=headers,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as r:
                if r.status in (200, 201):
                    log(f"✅ Whop sent → {WHOP_CHANNEL_ID}")
                    return
                elif r.status == 429:
                    body = await r.json()
                    wait = body.get("retry_after", backoff)
                    log(f"⚠️  Whop 429 — retry_after={wait}s")
                    await asyncio.sleep(wait)
                    backoff = max(backoff * 2, wait + 1)
                else:
                    text = await r.text()
                    log(f"❌ Whop HTTP {r.status}: {text[:200]}")
                    return
        except asyncio.TimeoutError:
            log(f"❌ Whop send timed out (attempt {attempt + 1})")
            await asyncio.sleep(backoff)
            backoff *= 2
        except Exception as e:
            log(f"❌ Whop exception: {e}")
            await asyncio.sleep(backoff)
            backoff *= 2


async def _schedule_group_send(msg: str):
    """Wait EARLY_DELAY seconds then send to Telegram group AND Whop channel."""
    await asyncio.sleep(EARLY_DELAY)
    _tg_queue.put_nowait((CHAT_ID, msg))
    async with aiohttp.ClientSession() as session:
        await _send_whop(session, msg)


def enqueue_telegram(msg: str):
    """
    1. Send immediately to the personal (early-alert) chat.
    2. Schedule the group send EARLY_DELAY seconds later.
    """
    # Immediate personal alert
    _tg_queue.put_nowait((EARLY_CHAT_ID, msg))
    # Delayed group alert (fire-and-forget coroutine)
    asyncio.create_task(_schedule_group_send(msg))

# ================= FILTER LOGIC ================= #
def relevant_for_chat(title: str) -> bool:
    t = title.lower()
    if any(ex in t for ex in CHAT_EXCLUDE_KEYWORDS):
        return False
    if not any(sp in t for sp in CHAT_SPECIALTIES):
        return False
    if not any(gr in t for gr in CHAT_GRADE_KEYWORDS):
        return False
    return True

def relevant_for_early(title: str) -> bool:
    t = title.lower()
    if any(ex in t for ex in EARLY_EXCLUDE_KEYWORDS):
        return False
    if not any(sp in t for sp in EARLY_SPECIALTIES):
        return False
    if not any(gr in t for gr in EARLY_GRADE_KEYWORDS):
        return False
    return True

def extract_job_id(link: str) -> str:
    m = re.search(r"\d{4,}", link)
    return m.group() if m else link

def normalize_link(href: str, base: str) -> str:
    if href.startswith("http"):
        return href
    if href.startswith("/"):
        return base.rstrip("/") + href
    return href

def get_base(url: str) -> str:
    m = re.match(r"(https?://[^/]+)", url)
    return m.group(1) if m else ""

def txt(el) -> str:
    return " ".join(el.get_text().split()) if el else ""

def sel_txt(parent, selector: str) -> str:
    el = parent.select_one(selector)
    return txt(el) if el else ""

# ================= HUMAN-LIKE HELPERS ================= #
async def human_scroll(page):
    try:
        total = await page.evaluate("document.body.scrollHeight")
        scrolled = 0
        while scrolled < total:
            step = random.randint(300, 700)
            scrolled += step
            await page.mouse.wheel(0, step)
            await asyncio.sleep(random.uniform(0.3, 0.8))
        await page.mouse.wheel(0, -random.randint(200, 500))
        await asyncio.sleep(random.uniform(0.4, 1.0))
    except Exception:
        pass

async def random_mouse_move(page):
    try:
        vp = page.viewport_size or {"width": 1280, "height": 800}
        await page.mouse.move(random.randint(100, vp["width"] - 100),
                              random.randint(100, vp["height"] - 100))
    except Exception:
        pass

# ================= BROWSER FACTORY ================= #
async def launch_browser(playwright):
    """Launch a single Chromium process to be shared across all URL tasks."""
    return await playwright.chromium.launch(
        headless=True,
        args=[
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--disable-gpu",
            "--disable-setuid-sandbox",
            "--disable-blink-features=AutomationControlled",
            "--disable-infobars",
            "--window-size=1920,1080",
        ],
    )

async def new_context(browser):
    """Create an isolated browser context inside the shared browser."""
    vp = random.choice(VIEWPORTS)
    ctx = await browser.new_context(
        user_agent=ua.random,
        viewport=vp,
        locale="en-GB",
        timezone_id="Europe/London",
        java_script_enabled=True,
        extra_http_headers={
            "Accept-Language": "en-GB,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1",
        },
    )
    await ctx.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        Object.defineProperty(navigator, 'plugins',   { get: () => [1,2,3,4,5] });
        Object.defineProperty(navigator, 'languages', { get: () => ['en-GB','en'] });
        window.chrome = { runtime: {} };
    """)
    return ctx

# ================= GOTO WITH RETRY ================= #
_WAIT_STRATEGIES = ["domcontentloaded", "commit"]

async def goto_with_retry(page, url: str, retries: int = 2,
                          timeout: int = PAGE_TIMEOUT) -> bool:
    for attempt in range(1, retries + 1):
        strategy = _WAIT_STRATEGIES[min(attempt - 1, len(_WAIT_STRATEGIES) - 1)]
        try:
            resp = await page.goto(url, wait_until=strategy, timeout=timeout)
            if resp and resp.status == 200:
                return True
            if resp and resp.status == 403:
                log(f"⛔ 403 on {url[:70]} (attempt {attempt}).")
                await asyncio.sleep(2)
            elif resp:
                log(f"⚠️  HTTP {resp.status} on {url[:70]} (attempt {attempt}).")
                return False
        except PWTimeout:
            log(f"⏱️  Timeout [{strategy}] on {url[:70]} (attempt {attempt}).")
            await asyncio.sleep(2)
        except Exception as e:
            log(f"❌ Nav error {url[:70]}: {e} (attempt {attempt}).")
            await asyncio.sleep(2)
    return False

# ================= SITE-SPECIFIC PARSERS ================= #

def parse_nhsjobs(soup: BeautifulSoup, base: str) -> list[dict]:
    jobs = []
    for card in soup.select("li[data-test='search-result']"):
        a = card.select_one("a[data-test='search-result-job-title']")
        if not a:
            continue
        href  = normalize_link(a.get("href", ""), base)
        title = txt(a)
        if not title or not href:
            continue
        loc_block = card.select_one("[data-test='search-result-location']")
        employer = location = ""
        if loc_block:
            h3 = loc_block.find("h3")
            if h3:
                loc_div = h3.find("div", class_="location-font-size")
                if loc_div:
                    location = txt(loc_div)
                    loc_div.extract()
                employer = txt(h3)
        def strong(test: str) -> str:
            li = card.select_one(f"li[data-test='{test}']")
            return txt(li.find("strong")) if li and li.find("strong") else ""
        jobs.append({
            "title": title, "link": href, "employer": employer,
            "location": location, "salary": strong("search-result-salary"),
            "closing_date": strong("search-result-closingDate"),
            "contract": strong("search-result-jobType"),
            "needs_detail": False, "site": "nhsjobs",
        })
    return jobs


def parse_healthjobsuk(soup: BeautifulSoup, base: str) -> list[dict]:
    jobs = []
    for li in soup.select("li.hj-job"):
        a = li.find("a", href=True)
        if not a:
            continue
        href  = normalize_link(a["href"], base)
        title = sel_txt(li, ".hj-jobtitle") or a.get("title", "").strip()
        if not title:
            continue
        jobs.append({
            "title": title, "link": href,
            "grade": sel_txt(li, ".hj-grade"),
            "employer": sel_txt(li, ".hj-employername"),
            "location": sel_txt(li, ".hj-locationtown"),
            "speciality": sel_txt(li, ".hj-primaryspeciality"),
            "salary": sel_txt(li, ".hj-salary"),
            "needs_detail": False, "site": "healthjobsuk",
        })
    return jobs


def parse_hscni(soup: BeautifulSoup, base: str) -> list[dict]:
    jobs = []
    for article in soup.select("article.job-result"):
        a = article.select_one("h2 a")
        if not a:
            continue
        href  = normalize_link(a.get("href", ""), base)
        title = txt(a)
        if not title or not href:
            continue
        ref_el = article.select_one(".job-ref")
        ref = txt(ref_el).replace("Ref:", "").strip() if ref_el else ""
        overview: dict = {}
        for li in article.select("ul.job-overview li"):
            strong = li.find("strong")
            if not strong:
                continue
            label = txt(strong).rstrip(":").lower()
            strong.extract()
            overview[label] = txt(li)
        closing_div = article.select_one(".job-closing")
        closing_date = ""
        if closing_div:
            strong = closing_div.find("strong")
            if strong:
                strong.extract()
            closing_date = txt(closing_div)
        jobs.append({
            "title": title, "link": href, "ref": ref,
            "salary": overview.get("salary", ""),
            "location": overview.get("location", ""),
            "contract": overview.get("contract type", ""),
            "closing_date": closing_date,
            "needs_detail": False, "site": "hscni",
        })
    return jobs


def parse_scotland(soup: BeautifulSoup, base: str) -> list[dict]:
    seen: set = set()
    jobs = []
    for card in soup.select("div.card-body"):
        a = card.select_one("a[href*='JobDetail']")
        if not a:
            continue
        href  = normalize_link(a.get("href", ""), base)
        title = txt(a)
        m = re.search(r"JobId=(\d+)", href)
        uid = m.group(1) if m else href
        if uid in seen:
            continue
        seen.add(uid)
        def detail(css_class: str) -> str:
            p = card.select_one(f"p.{css_class}")
            if not p:
                return ""
            strong = p.find("strong")
            if strong:
                strong.extract()
            return txt(p)
        jobs.append({
            "title": title, "link": href,
            "ref": detail("jobreference"),
            "salary": detail("salary"),
            "closing_date": detail("closingdate"),
            "job_family": detail("department"),
            "location": detail("location"),
            "employment_type": detail("employmenttype"),
            "hours": detail("hours"),
            "employer": detail("school"),
            "department": detail("shift"),
            "needs_detail": False, "site": "scotland",
        })
    return jobs


def parse_generic(soup: BeautifulSoup, base: str) -> list[dict]:
    jobs = []
    for a in soup.find_all("a", href=True):
        if "job" not in a["href"].lower():
            continue
        title = txt(a)
        if title and len(title) > 8:
            jobs.append({"title": title, "link": normalize_link(a["href"], base),
                         "needs_detail": False, "site": "generic"})
    return jobs


def get_parser(url: str):
    if "healthjobsuk.com" in url: return parse_healthjobsuk
    if "jobs.nhs.uk"      in url: return parse_nhsjobs
    if "hscni.net"        in url: return parse_hscni
    if "jobs.scot.nhs.uk" in url: return parse_scotland
    return parse_generic

# ================= MESSAGE FORMATTERS ================= #

def format_nhsjobs(job: dict) -> str:
    lines = ["🚨 <b>NEW NHS JOB — England</b>\n", f"🏥 <b>{job['title']}</b>"]
    if job.get("employer"):     lines.append(f"🏢 {job['employer']}")
    if job.get("location"):     lines.append(f"📍 {job['location']}")
    if job.get("salary"):       lines.append(f"💷 {job['salary']}")
    if job.get("closing_date"): lines.append(f"📅 Closes: {job['closing_date']}")
    if job.get("contract"):     lines.append(f"📋 {job['contract']}")
    lines.append(f"🔗 {job['link']}")
    return "\n".join(lines)

def format_healthjobsuk(job: dict) -> str:
    lines = ["🚨 <b>NEW NHS JOB — HealthJobsUK</b>\n", f"🏥 <b>{job['title']}</b>"]
    if job.get("grade"):        lines.append(f"🎓 {job['grade']}")
    if job.get("employer"):     lines.append(f"🏢 {job['employer']}")
    if job.get("location"):     lines.append(f"📍 {job['location']}")
    if job.get("speciality"):   lines.append(f"🔬 {job['speciality']}")
    if job.get("salary"):       lines.append(f"💷 {job['salary']}")
    lines.append(f"🔗 {job['link']}")
    return "\n".join(lines)

def format_hscni(job: dict) -> str:
    lines = ["🚨 <b>NEW NHS JOB — Northern Ireland</b>\n", f"🏥 <b>{job['title']}</b>"]
    if job.get("ref"):          lines.append(f"🔖 Ref: {job['ref']}")
    if job.get("location"):     lines.append(f"📍 {job['location']}")
    if job.get("salary"):       lines.append(f"💷 {job['salary']}")
    if job.get("contract"):     lines.append(f"📋 {job['contract']}")
    if job.get("closing_date"): lines.append(f"📅 Closes: {job['closing_date']}")
    lines.append(f"🔗 {job['link']}")
    return "\n".join(lines)

def format_scotland(job: dict) -> str:
    lines = ["🚨 <b>NEW NHS JOB — Scotland</b>\n", f"🏥 <b>{job['title']}</b>"]
    if job.get("employer"):        lines.append(f"🏢 {job['employer']}")
    if job.get("location"):        lines.append(f"📍 {job['location']}")
    if job.get("department"):      lines.append(f"🏨 {job['department']}")
    if job.get("job_family"):      lines.append(f"🔬 {job['job_family']}")
    if job.get("salary"):          lines.append(f"💷 {job['salary']}")
    if job.get("employment_type"): lines.append(f"📋 {job['employment_type']}")
    if job.get("hours"):           lines.append(f"🕐 {job['hours']} hrs/week")
    if job.get("closing_date"):    lines.append(f"📅 Closes: {job['closing_date']}")
    if job.get("ref"):             lines.append(f"🔖 Ref: {job['ref']}")
    lines.append(f"🔗 {job['link']}")
    return "\n".join(lines)

def format_message(job: dict) -> str:
    site = job.get("site", "generic")
    if site == "nhsjobs":      return format_nhsjobs(job)
    if site == "healthjobsuk": return format_healthjobsuk(job)
    if site == "hscni":        return format_hscni(job)
    if site == "scotland":     return format_scotland(job)
    lines = [f"🚨 <b>NEW NHS JOB</b>\n", f"🏥 <b>{job['title']}</b>"]
    if job.get("location"): lines.append(f"📍 {job['location']}")
    if job.get("salary"):   lines.append(f"💷 {job['salary']}")
    lines.append(f"🔗 {job['link']}")
    return "\n".join(lines)

# ================= SINGLE-URL SCRAPER ================= #
async def check_site(url: str, seen_jobs: set, browser, is_first_cycle: bool = False) -> int:
    log(f"🔍 Checking: {url}")
    new_jobs = 0
    base   = get_base(url)
    parser = get_parser(url)

    context = page = None
    try:
        context = await new_context(browser)
        page = await context.new_page()
        await stealth_async(page)
        await asyncio.sleep(random.uniform(0, 5))

        if not await goto_with_retry(page, url):
            log(f"⛔ Giving up on {url}.")
            return 0

        await random_mouse_move(page)
        await asyncio.sleep(random.uniform(0.8, 2.0))
        await human_scroll(page)

        soup       = BeautifulSoup(await page.content(), "html.parser")
        candidates = parser(soup, base)
        log(f"   [{url[:60]}] {len(candidates)} candidate(s).")

        for job in candidates:
            try:
                link   = job["link"]
                job_id = extract_job_id(link)

                async with _seen_lock:
                    if job_id in seen_jobs:
                        continue

                title = job.get("title", "")
                goes_to_early = relevant_for_early(title)
                goes_to_chat  = relevant_for_chat(title)
                if not title or (not goes_to_early and not goes_to_chat):
                    continue

                async with _seen_lock:
                    if job_id in seen_jobs:
                        continue
                    seen_jobs.add(job_id)

                if is_first_cycle:
                    log(f"   👁️  SEEN (first cycle, no alert): {title}")
                else:
                    msg = format_message(job)
                    if goes_to_early:
                        log(f"   🆕 NEW JOB [{job.get('site','?')}] → early + public: {title}")
                        _tg_queue.put_nowait((EARLY_CHAT_ID, msg))
                        asyncio.create_task(_schedule_group_send(msg))
                    elif goes_to_chat:
                        log(f"   🆕 NEW JOB [{job.get('site','?')}] → public only: {title}")
                        _tg_queue.put_nowait((CHAT_ID, msg))
                await async_save_seen(job_id)
                new_jobs += 1

            except Exception as e:
                log(f"   ⚠️  Entry error: {e}")

        log(f"   ✅ [{url[:60]}] {new_jobs} new job(s) found.")

    except Exception as e:
        log(f"❌ SCRAPER ERROR on {url}: {e}")
    finally:
        for obj in (page, context):
            if obj:
                try:
                    await obj.close()
                except Exception:
                    pass

    return new_jobs

# ================= PARALLEL CYCLE ================= #
_ctx_sem: asyncio.Semaphore | None = None

async def _site_with_timeout(url: str, seen_jobs: set, browser, is_first_cycle: bool = False) -> int:
    async with _ctx_sem:
        try:
            return await asyncio.wait_for(
                check_site(url, seen_jobs, browser, is_first_cycle),
                timeout=SITE_HARD_LIMIT,
            )
        except asyncio.TimeoutError:
            log(f"⏰ Hard timeout ({SITE_HARD_LIMIT}s) hit for {url[:60]} — skipping.")
            return 0
        except Exception as e:
            log(f"⚠️  Task error for {url[:60]}: {e}")
            return 0


async def run_cycle(seen_jobs: set, browser, is_first_cycle: bool = False):
    label = " (first cycle — seeding seen list, no alerts)" if is_first_cycle else ""
    log(f"🚀 Cycle — {len(URLS)} URLs, {MAX_CONCURRENT_CONTEXTS} concurrent contexts{label}…")
    tasks   = [asyncio.create_task(_site_with_timeout(u, seen_jobs, browser, is_first_cycle)) for u in URLS]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    total   = sum(r for r in results if isinstance(r, int))
    log(f"✅ Cycle done — {total} new job(s) total.")

# ================= ENTRY POINT ================= #
async def main():
    global _ctx_sem

    try:
        soft, hard = resource.getrlimit(resource.RLIMIT_NPROC)
        resource.setrlimit(resource.RLIMIT_NPROC, (hard, hard))
        log(f"   RLIMIT_NPROC raised to {hard}")
    except Exception as e:
        log(f"   Could not raise RLIMIT_NPROC: {e}")

    _ctx_sem = asyncio.Semaphore(MAX_CONCURRENT_CONTEXTS)

    log("🚀 NHS JOB BOT STARTED")
    log(f"   Early-alert chat : {EARLY_CHAT_ID}  (immediate)")
    log(f"   Group chat       : {CHAT_ID}  (+{EARLY_DELAY}s delay)")

    log("📡 Sending Whop startup test message…")
    async with aiohttp.ClientSession() as _s:
        await _send_whop(_s, "🚀 NHS Job Bot is online and monitoring for new jobs.")

    seen_jobs = load_seen()
    log(f"   Loaded {len(seen_jobs)} previously seen job IDs.")
    asyncio.create_task(telegram_consumer())

    cycle = 0
    async with async_playwright() as playwright:
        while True:
            log("🌐 Launching shared browser…")
            browser = await launch_browser(playwright)
            try:
                for _ in range(PLAYWRIGHT_RECYCLE_EVERY):
                    cycle += 1
                    log(f"─── CYCLE {cycle} ───────────────────────────────")
                    try:
                        await run_cycle(seen_jobs, browser, is_first_cycle=(cycle == -1))
                    except Exception as e:
                        log(f"🔥 Cycle-level error (will continue): {e}")
                    log(f"💤 Sleeping {CHECK_INTERVAL}s …\n")
                    await asyncio.sleep(CHECK_INTERVAL)
            finally:
                log(f"♻️  Closing browser after {PLAYWRIGHT_RECYCLE_EVERY} cycles…")
                try:
                    await browser.close()
                except Exception:
                    pass
                gc.collect()
                await asyncio.sleep(5)


if __name__ == "__main__":
    asyncio.run(main())
