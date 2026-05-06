import asyncio
import random
import re
import aiohttp
from datetime import datetime
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright, TimeoutError as PWTimeout
from playwright_stealth import stealth_async
from fake_useragent import UserAgent

# ================= CONFIG ================= #
BOT_TOKEN = "8213751012:AAFYvubDXeY3xU8vjaWLxNTT7XqMtPhUuwQ"
CHAT_ID = "-1003888963521"
CHECK_INTERVAL = 120          # seconds between full cycles
PAGE_TIMEOUT = 45_000         # ms
DETAIL_TIMEOUT = 20_000       # ms
SITE_HARD_LIMIT = 300         # seconds — hard kill per URL task
TELEGRAM_SEND_INTERVAL = 1.1  # slightly above Telegram's 1 msg/s/chat limit

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
def log(msg: str):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)

# ================= SEEN-JOBS PERSISTENCE ================= #
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
_tg_queue: asyncio.Queue = asyncio.Queue()

async def telegram_consumer():
    """
    Fully async Telegram sender using aiohttp — never blocks the event loop.
    Paces sends at TELEGRAM_SEND_INTERVAL seconds to respect the 1 msg/s/chat limit.
    On 429, honours the exact retry_after Telegram returns.
    """
    api_url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    async with aiohttp.ClientSession() as session:
        while True:
            msg = await _tg_queue.get()
            if msg is None:
                _tg_queue.task_done()
                break

            payload = {"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"}
            backoff = 5
            for attempt in range(5):
                try:
                    async with session.post(
                        api_url, data=payload,
                        timeout=aiohttp.ClientTimeout(total=10)
                    ) as r:
                        if r.status == 200:
                            log("✅ Telegram sent")
                            break
                        elif r.status == 429:
                            body = await r.json()
                            wait = body.get("parameters", {}).get("retry_after", backoff)
                            log(f"⚠️  Telegram 429 — honouring retry_after={wait}s")
                            await asyncio.sleep(wait)
                            backoff = max(backoff * 2, wait + 1)
                        else:
                            text = await r.text()
                            log(f"❌ Telegram HTTP {r.status}: {text[:200]}")
                            break
                except asyncio.TimeoutError:
                    log(f"❌ Telegram send timed out (attempt {attempt + 1})")
                    await asyncio.sleep(backoff)
                    backoff *= 2
                     
                                                                             
                         
                except Exception as e:
                    log(f"❌ Telegram exception: {e}")
                    await asyncio.sleep(backoff)
                    backoff *= 2
                             
                                                   

            _tg_queue.task_done()
            await asyncio.sleep(TELEGRAM_SEND_INTERVAL)

def enqueue_telegram(msg: str):
    _tg_queue.put_nowait(msg)

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

# NOTE: Scotland jobs are NOT filtered through relevant_job().
# The Scottish NHS uses different grade/title conventions and the filter
# would incorrectly exclude valid roles. All Scotland jobs that pass the
# basic HTML extraction are sent as-is.
def relevant_job_scotland(title: str) -> bool:
    return bool(title and len(title) > 5)

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
    """Safe whitespace-collapsed get_text()."""
    return " ".join(el.get_text().split()) if el else ""

def sel_txt(parent, selector: str) -> str:
    """Select first match and return its collapsed text, or ''."""
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
async def create_context(playwright):
    browser = await playwright.chromium.launch(
        headless=True,
        args=[
            "--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu",
            "--disable-setuid-sandbox",
            "--disable-blink-features=AutomationControlled",
            "--disable-infobars",
            "--window-size=1920,1080",
        ],
    )
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
    return browser, ctx

# ================= GOTO WITH RETRY ================= #
async def goto_with_retry(page, url: str, retries: int = 3,
                          timeout: int = PAGE_TIMEOUT) -> bool:
       
                                                                       
                                                                      
       
    backoff = 5
    for attempt in range(1, retries + 1):
        try:
            resp = await page.goto(url, wait_until="domcontentloaded", timeout=timeout)
            if resp and resp.status == 200:
                return True
            if resp and resp.status == 403:
                log(f"⛔ 403 on {url} (attempt {attempt}). Backing off {backoff}s.")
                await asyncio.sleep(backoff)
                backoff *= 2
            elif resp:
                log(f"⚠️  HTTP {resp.status} on {url} (attempt {attempt}).")
                return False
        except PWTimeout:
            log(f"⏱️  Timeout on {url} (attempt {attempt}). Retrying in {backoff}s.")
            await asyncio.sleep(backoff)
            backoff *= 2
        except Exception as e:
            log(f"❌ Nav error {url}: {e} (attempt {attempt}).")
            await asyncio.sleep(backoff)
            backoff *= 2
    return False

# ================= SITE-SPECIFIC PARSERS ================= #

def parse_nhsjobs(soup: BeautifulSoup, base: str) -> list[dict]:
    """
    Extracts all fields from listing-page cards — no detail visit needed.
                                

    HTML structure (jobs.nhs.uk):
      <li data-test="search-result">
        <a data-test="search-result-job-title">            ← title + href
        <div data-test="search-result-location">
          <h3> employer <div class="location-font-size">  ← employer / location
              
        <li data-test="search-result-salary">     <strong> ← salary
        <li data-test="search-result-closingDate"> <strong> ← closing date
                                                                                              
        <li data-test="search-result-jobType">     <strong> ← contract type
                                                                                                 
           
    """
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
            "title":        title,
            "link":         href,
            "employer":     employer,
            "location":     location,
            "salary":       strong("search-result-salary"),
            "closing_date": strong("search-result-closingDate"),
            "contract":     strong("search-result-jobType"),
            "needs_detail": False,
            "site":         "nhsjobs",
        })
    return jobs


def parse_healthjobsuk(soup: BeautifulSoup, base: str) -> list[dict]:
    """
    Extracts fields from listing cards — no detail visit needed.

    HTML structure (healthjobsuk.com):
      <li class="hj-job …">
        <a href="/job/…" title="…">                       ← link (title attr = job title)
          <div class="hj-jobtitle …">                     ← job title text
          <div class="hj-grade …">                        ← grade
          <div class="hj-employername …">                 ← employer name
          <div class="hj-locationtown …">                 ← location
          <div class="hj-primaryspeciality …">            ← speciality
          <div class="hj-salary …">                       ← salary
    """
    jobs = []
    for li in soup.select("li.hj-job"):
        a = li.find("a", href=True)
        if not a:
            continue
        href  = normalize_link(a["href"], base)

        # Title: prefer the dedicated div, fall back to the <a> title attribute
        title = sel_txt(li, ".hj-jobtitle") or a.get("title", "").strip()
        if not title:
            continue

        jobs.append({
            "title":      title,
            "link":       href,
            "grade":      sel_txt(li, ".hj-grade"),
            "employer":   sel_txt(li, ".hj-employername"),
            "location":   sel_txt(li, ".hj-locationtown"),
            "speciality": sel_txt(li, ".hj-primaryspeciality"),
            "salary":     sel_txt(li, ".hj-salary"),
            # Closing date is not present on the listing page for this site
            "needs_detail": False,
            "site":         "healthjobsuk",
        })
    return jobs


def parse_hscni(soup: BeautifulSoup, base: str) -> list[dict]:
    """
    Extracts fields from listing cards — no detail visit needed.

    HTML structure (jobs.hscni.net):
      <article class="job-result …" data-id="…">
        <h2><a href="/Job/…">                             ← title + link
        <span class="job-ref …">Ref: …</span>            ← reference
        <ul class="job-overview">
          <li><strong>Salary: </strong>…                  ← salary
          <li><strong>Location: </strong>…                ← location
          <li><strong>Contract Type: </strong>…           ← contract
        <div class="job-closing"><strong>Closing:</strong> … ← closing date
    """
    jobs = []
    for article in soup.select("article.job-result"):
        a = article.select_one("h2 a")
        if not a:
            continue
        href  = normalize_link(a.get("href", ""), base)
        title = txt(a)
        if not title or not href:
            continue

        # Reference number (strip leading "Ref: ")
        ref_el = article.select_one(".job-ref")
        ref = txt(ref_el).replace("Ref:", "").strip() if ref_el else ""

        # Overview list items — keyed by their <strong> label
        overview: dict = {}
        for li in article.select("ul.job-overview li"):
            strong = li.find("strong")
            if not strong:
                continue
            label = txt(strong).rstrip(":").lower()
            # Value = everything after the <strong>
            strong.extract()
            value = txt(li)
            overview[label] = value

        # Closing date lives in its own div
        closing_div = article.select_one(".job-closing")
        closing_date = ""
        if closing_div:
            strong = closing_div.find("strong")
            if strong:
                strong.extract()
            closing_date = txt(closing_div)

        jobs.append({
            "title":        title,
            "link":         href,
            "ref":          ref,
            "salary":       overview.get("salary", ""),
            "location":     overview.get("location", ""),
            "contract":     overview.get("contract type", ""),
            "closing_date": closing_date,
            "needs_detail": False,
            "site":         "hscni",
        })
    return jobs


def parse_scotland(soup: BeautifulSoup, base: str) -> list[dict]:
    """
    Extracts fields from listing cards — no detail visit needed.

    HTML structure (apply.jobs.scot.nhs.uk):
      <div class="card-body …">
        <a href="/Job/JobDetail?JobId=…">                 ← title + link
        <p class="jobreference"><strong>Job reference:</strong> …
        <p class="salary"><strong>Salary:</strong> …
        <p class="closingdate"><strong>Closing date:</strong> …
        <p class="department"><strong>Job Family:</strong> …
        <p class="location"><strong>Location:</strong> …
        <p class="employmenttype"><strong>Employment type:</strong> …
        <p class="hours"><strong>Hours per week:</strong> …
        <p class="school"><strong>Employer (NHS Board):</strong> …
        <p class="shift"><strong>Department:</strong> …

    NOTE: Scotland jobs bypass the standard grade/specialty filter
    (relevant_job_scotland is used instead) because Scottish NHS uses
    different titling conventions that the England/Wales keywords miss.
    """
    seen: set = set()
    jobs = []
    for card in soup.select("div.card-body"):
        a = card.select_one("a[href*='JobDetail']")
        if not a:
            continue
        href  = normalize_link(a.get("href", ""), base)
        title = txt(a)

        # Deduplicate by JobId
        m = re.search(r"JobId=(\d+)", href)
        uid = m.group(1) if m else href
        if uid in seen:
            continue
        seen.add(uid)

        def detail(css_class: str) -> str:
            """
            Each detail row is a <p class="jobdetailsitem <css_class>">.
            The value is the text after stripping the <strong> label.
            """
            p = card.select_one(f"p.{css_class}")
            if not p:
                return ""
            strong = p.find("strong")
            if strong:
                strong.extract()
            return txt(p)

        jobs.append({
            "title":           title,
            "link":            href,
            "ref":             detail("jobreference"),
            "salary":          detail("salary"),
            "closing_date":    detail("closingdate"),
            "job_family":      detail("department"),      # "Job Family" field
            "location":        detail("location"),
            "employment_type": detail("employmenttype"),
            "hours":           detail("hours"),
            "employer":        detail("school"),          # "Employer (NHS Board)"
            "department":      detail("shift"),           # "Department" field
            "needs_detail":    False,
            "site":            "scotland",
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

# ================= DETAIL-PAGE FETCH (fallback only) ================= #
async def fetch_detail_title(context, link: str) -> str:
    """Used only by sites that still need a detail page visit (none currently)."""
    page = await context.new_page()
    try:
        await stealth_async(page)
        await asyncio.sleep(random.uniform(1.0, 2.5))
        ok = await goto_with_retry(page, link, retries=2, timeout=DETAIL_TIMEOUT)
        if not ok:
            return ""
        soup = BeautifulSoup(await page.content(), "html.parser")
        h1 = soup.find("h1")
        return txt(h1) if h1 else ""
    except Exception as e:
        log(f"Detail fetch error ({link}): {e}")
        return ""
    finally:
        await page.close()

# ================= MESSAGE FORMATTERS ================= #

def format_nhsjobs(job: dict) -> str:
    lines = ["🚨 <b>NEW NHS JOB — England</b>\n",
             f"🏥 <b>{job['title']}</b>"]
    if job.get("employer"):     lines.append(f"🏢 {job['employer']}")
                                               
    if job.get("location"):     lines.append(f"📍 {job['location']}")
                                               
    if job.get("salary"):       lines.append(f"💷 {job['salary']}")
                                             
    if job.get("closing_date"): lines.append(f"📅 Closes: {job['closing_date']}")
                                                           
    if job.get("contract"):     lines.append(f"📋 {job['contract']}")
    lines.append(f"🔗 {job['link']}")
    return "\n".join(lines)


def format_healthjobsuk(job: dict) -> str:
    lines = ["🚨 <b>NEW NHS JOB — HealthJobsUK</b>\n",
             f"🏥 <b>{job['title']}</b>"]
    if job.get("grade"):        lines.append(f"🎓 {job['grade']}")
    if job.get("employer"):     lines.append(f"🏢 {job['employer']}")
    if job.get("location"):     lines.append(f"📍 {job['location']}")
    if job.get("speciality"):   lines.append(f"🔬 {job['speciality']}")
    if job.get("salary"):       lines.append(f"💷 {job['salary']}")
    lines.append(f"🔗 {job['link']}")
    return "\n".join(lines)


def format_hscni(job: dict) -> str:
    lines = ["🚨 <b>NEW NHS JOB — Northern Ireland</b>\n",
             f"🏥 <b>{job['title']}</b>"]
    if job.get("ref"):          lines.append(f"🔖 Ref: {job['ref']}")
    if job.get("location"):     lines.append(f"📍 {job['location']}")
    if job.get("salary"):       lines.append(f"💷 {job['salary']}")
    if job.get("contract"):     lines.append(f"📋 {job['contract']}")
    if job.get("closing_date"): lines.append(f"📅 Closes: {job['closing_date']}")
    lines.append(f"🔗 {job['link']}")
    return "\n".join(lines)


def format_scotland(job: dict) -> str:
    lines = ["🚨 <b>NEW NHS JOB — Scotland</b>\n",
             f"🏥 <b>{job['title']}</b>"]
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
    if site == "nhsjobs":     return format_nhsjobs(job)
    if site == "healthjobsuk": return format_healthjobsuk(job)
    if site == "hscni":        return format_hscni(job)
    if site == "scotland":     return format_scotland(job)
    # Generic fallback
    lines = [f"🚨 <b>NEW NHS JOB</b>\n", f"🏥 <b>{job['title']}</b>"]
    if job.get("location"): lines.append(f"📍 {job['location']}")
    if job.get("salary"):   lines.append(f"💷 {job['salary']}")
    lines.append(f"🔗 {job['link']}")
    return "\n".join(lines)

# ================= SINGLE-URL SCRAPER ================= #
async def check_site(url: str, seen_jobs: set, playwright) -> int:
    log(f"🔍 Checking: {url}")
    new_jobs = 0
    base     = get_base(url)
    parser   = get_parser(url)

    browser = context = page = None
    try:
        browser, context = await create_context(playwright)
        page = await context.new_page()
        await stealth_async(page)
        await asyncio.sleep(random.uniform(1.5, 4.0))

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

                # Fetch detail page when needed (currently no site requires this)
                if job.get("needs_detail"):
                    detail_title = await fetch_detail_title(context, link)
                    if detail_title:
                        job = {**job, "title": detail_title}
                    await asyncio.sleep(random.uniform(0.8, 1.8))

                # Apply the correct filter depending on the site
                title = job.get("title", "")
                if job.get("site") == "scotland":
                    if not relevant_job_scotland(title):
                        continue
                else:
                    if not title or not relevant_job(title):
                        continue

                # Atomic claim
                async with _seen_lock:
                    if job_id in seen_jobs:
                        continue
                    seen_jobs.add(job_id)

                log(f"   🆕 NEW JOB [{job.get('site','?')}]: {title}")
                enqueue_telegram(format_message(job))
                await async_save_seen(job_id)
                new_jobs += 1

            except Exception as e:
                log(f"   ⚠️  Entry error: {e}")

        log(f"   ✅ [{url[:60]}] {new_jobs} new job(s) found.")

    except Exception as e:
        log(f"❌ SCRAPER ERROR on {url}: {e}")
    finally:
        for obj in (page, context, browser):
            if obj:
                try:
                    await obj.close()
                except Exception:
                    pass

    return new_jobs


# ================= PARALLEL CYCLE ================= #
async def _site_with_timeout(url: str, seen_jobs: set, playwright) -> int:
       
                                                                           
                                                                           
       
    try:
        return await asyncio.wait_for(
            check_site(url, seen_jobs, playwright),
            timeout=SITE_HARD_LIMIT,
        )
    except asyncio.TimeoutError:
        log(f"⏰ Hard timeout ({SITE_HARD_LIMIT}s) hit for {url[:60]} — skipping.")
        return 0
    except Exception as e:
        log(f"⚠️  Task error for {url[:60]}: {e}")
        return 0


async def run_cycle(seen_jobs: set, playwright):
    log(f"🚀 Parallel cycle — {len(URLS)} URLs (hard limit {SITE_HARD_LIMIT}s each)…")
    tasks   = [asyncio.create_task(_site_with_timeout(u, seen_jobs, playwright)) for u in URLS]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    total   = sum(r for r in results if isinstance(r, int))
    log(f"✅ Cycle done — {total} new job(s) total.")


# ================= ENTRY POINT ================= #
async def main():
    log("🚀 NHS JOB BOT STARTED")
    seen_jobs = load_seen()
    log(f"   Loaded {len(seen_jobs)} previously seen job IDs.")

                                                                                   
    asyncio.create_task(telegram_consumer())

    async with async_playwright() as p:
        cycle = 0
        while True:
            cycle += 1
            log(f"─── CYCLE {cycle} ───────────────────────────────")
            try:
                await run_cycle(seen_jobs, p)
            except Exception as e:
                log(f"🔥 Cycle-level error (will continue): {e}")

            log(f"💤 Sleeping {CHECK_INTERVAL}s …\n")
            await asyncio.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    asyncio.run(main())
