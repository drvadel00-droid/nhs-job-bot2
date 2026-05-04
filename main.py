import asyncio
import random
import re
import time
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
DETAIL_TIMEOUT = 25_000       # ms for job-detail pages

ua = UserAgent()

URLS = [
    HealthJobsUK — newest first (general + per-trust)
    "https://www.healthjobsuk.com/job_list?JobSearch_Submit=Search&_srt=publicationdate&_sd=desc",
    "https://www.healthjobsuk.com/job_list?JobSearch_q=&JobSearch_d=534&JobSearch_g=&JobSearch_re=_POST&JobSearch_re_0=1&JobSearch_re_1=1-_-_-&JobSearch_re_2=1-_-_--_-_-&JobSearch_Submit=Search&_tr=JobSearch&_ts=64082&_srt=publicationdate&_sd=desc",
    "https://www.healthjobsuk.com/job_list?JobSearch_q=&JobSearch_d=737&JobSearch_g=&JobSearch_re=_POST&JobSearch_re_0=1&JobSearch_re_1=1-_-_-&JobSearch_re_2=1-_-_--_-_-&JobSearch_Submit=Search&_tr=JobSearch&_ts=81534&_srt=publicationdate&_sd=desc",
    "https://www.healthjobsuk.com/job_list?JobSearch_q=&JobSearch_d=594&JobSearch_g=&JobSearch_re=_POST&JobSearch_re_0=1&JobSearch_re_1=1-_-_-&JobSearch_re_2=1-_-_--_-_-&JobSearch_Submit=Search&_tr=JobSearch&_ts=88730&_srt=publicationdate&_sd=desc",
    "https://www.healthjobsuk.com/job_list?JobSearch_q=&JobSearch_d=572&JobSearch_g=&JobSearch_re=_POST&JobSearch_re_0=1&JobSearch_re_1=1-_-_-&JobSearch_re_2=1-_-_--_-_-&JobSearch_Submit=Search&_tr=JobSearch&_ts=97667&_srt=publicationdate&_sd=desc",
    "https://www.healthjobsuk.com/job_list?JobSearch_q=&JobSearch_d=558&JobSearch_g=&JobSearch_re=_POST&JobSearch_re_0=1&JobSearch_re_1=1-_-_-&JobSearch_re_2=1-_-_--_-_-&JobSearch_Submit=Search&_tr=JobSearch&_ts=110250&_srt=publicationdate&_sd=desc",
    "https://www.healthjobsuk.com/job_list?JobSearch_q=&JobSearch_d=581&JobSearch_g=&JobSearch_re=_POST&JobSearch_re_0=1&JobSearch_re_1=1-_-_-&JobSearch_re_2=1-_-_--_-_-&JobSearch_Submit=Search&_tr=JobSearch&_ts=44291&_srt=publicationdate&_sd=desc",
    # NHS Jobs England — medical & dental staff group, junior pay bands
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

# ================= PERSISTENCE ================= #
def load_seen() -> set:
    """Load seen job IDs (URL-based, per-site unique IDs)."""
    try:
        with open("seen_jobs.txt", "r") as f:
            return set(f.read().splitlines())
    except FileNotFoundError:
        return set()

def save_seen(job_id: str):
    with open("seen_jobs.txt", "a") as f:
        f.write(job_id + "\n")

def load_seen_signatures() -> set:
    """Load cross-site dedup signatures (normalised title|location pairs)."""
    try:
        with open("seen_signatures.txt", "r") as f:
            return set(f.read().splitlines())
    except FileNotFoundError:
        return set()

def save_seen_signature(sig: str):
    with open("seen_signatures.txt", "a") as f:
        f.write(sig + "\n")

# ================= CROSS-SITE DEDUP ================= #
def _normalise(text: str) -> str:
    """Lowercase, strip all non-alphanumeric chars for fuzzy matching."""
    return re.sub(r"[^a-z0-9]", "", text.lower())

def make_signature(title: str, location: str) -> str:
    """Stable key to detect the same vacancy posted on multiple sites."""
    return f"{_normalise(title)}|{_normalise(location)}"

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

def format_message(info: dict) -> str:
    """Build the structured Telegram notification."""
    title    = info.get("title")    or "N/A"
    location = info.get("location") or "N/A"
    salary   = info.get("salary")   or "N/A"
    grade    = info.get("grade")    or "N/A"
    link     = info.get("link")     or ""
    return (
        f"🚨 <b>NEW NHS JOB</b>\n\n"
        f"📋 <b>Title</b>: {title}\n"
        f"📍 <b>Location</b>: {location}\n"
        f"💷 <b>Salary</b>: {salary}\n"
        f"🏅 <b>Grade</b>: {grade}\n"
        f"🔗 <b>URL</b>: {link}"
    )

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

# ================= DETAIL-PAGE PARSER ================= #
_LOCATION_LABELS = {"location", "town", "city", "base", "site", "place of work"}
_SALARY_LABELS   = {"salary", "pay", "remuneration", "wage", "pay range", "salary range"}
_GRADE_LABELS    = {"grade", "band", "pay band", "nhs band", "agenda for change",
                    "afc band", "staff group", "job level", "pay grade"}

def _match_label(raw: str, label_set: set) -> bool:
    return any(lbl in raw.lower() for lbl in label_set)

def _scrub(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()

# Grade tokens used to detect concatenated HealthJobsUK h1
_GRADE_TOKENS = [
    "FY1", "FY2", "CT1", "CT2", "CT3", "ST1", "ST2", "ST3",
    "Registrar", "Trust Doctor", "Trust Grade", "Clinical Fellow",
    "Specialty Doctor", "Junior", "Locum Doctor", "Foundation",
]

def _split_healthjobsuk_h1(raw: str) -> dict:
    """
    HealthJobsUK concatenates everything into one block of text, e.g.:
      "Medical Education Fellow in General Medicine (ST3)ST3
       Harrogate and District NHS Foundation Trust, Harrogate
       Speciality: General Medicine  Salary: £65,048 - £73,992 per annum"

    Parse it into clean title / grade / location / salary fields.
    """
    result = {"title": None, "location": None, "salary": None, "grade": None}

    # --- Salary ---
    sal_m = re.search(r"Salary\s*:?\s*(£[\d,]+\s*[-–to]+\s*£[\d,]+(?:\s*per\s+annum)?)", raw, re.I)
    if sal_m:
        result["salary"] = sal_m.group(1).strip()

    # --- Grade: prefer parenthesised form first, then bare token ---
    grade_paren = re.search(
        r"\((" + "|".join(re.escape(g) for g in _GRADE_TOKENS) + r")\)",
        raw, re.I
    )
    grade_bare = re.search(
        r"\b(" + "|".join(re.escape(g) for g in _GRADE_TOKENS) + r")\b",
        raw, re.I
    )
    if grade_paren:
        result["grade"] = grade_paren.group(1)
    elif grade_bare:
        result["grade"] = grade_bare.group(1)

    # --- Location: city that follows "NHS ... Trust," or "Hospital," ---
    loc_m = re.search(
        r"(?:NHS[^,\n]+?(?:Trust|Hospital)|Foundation Trust)[,\s]+([A-Z][A-Za-z\s\-]+?)(?=\s*(?:Specialit|Salary|$))",
        raw, re.I
    )
    if loc_m:
        result["location"] = loc_m.group(1).strip().rstrip(",")

    # --- Title: everything before the first grade token / trust / salary marker ---
    cutoff = len(raw)
    for pattern in [
        r"\s*\([A-Z]{2}\d\)",                         # (ST3) grade in parens
        r"\b(?:NHS|Foundation Trust|Hospital Trust)\b",
        r"\bSpecialit(?:y|ies)\b",
        r"\bSalary\b",
    ]:
        m = re.search(pattern, raw, re.I)
        if m and m.start() < cutoff:
            cutoff = m.start()

    raw_title = raw[:cutoff].strip().rstrip(",").strip()
    # Remove trailing bare grade token if still present
    for g in _GRADE_TOKENS:
        raw_title = re.sub(r"\s*\b" + re.escape(g) + r"\b\s*$", "", raw_title, flags=re.I).strip()
    result["title"] = raw_title or None

    return result


def parse_detail_soup(soup: BeautifulSoup) -> dict:
    """
    Extract title, location, salary and grade from a job detail page.

    For HealthJobsUK the <h1> contains everything concatenated — detected by
    the presence of 'Salary' or 'NHS' inside the h1 text and handled by
    _split_healthjobsuk_h1().

    For all other sites four generic strategies are tried:
      1. <dl> / <dt> + <dd> pairs
      2. <table> <th>/<td> rows
      3. <li> with bold/strong label
      4. <p>/<div>/<span> with "label: value" text
    """
    result = {"title": None, "location": None, "salary": None, "grade": None}

    h1 = soup.find("h1")
    raw_h1 = _scrub(h1.get_text()) if h1 else ""

    # Detect concatenated HealthJobsUK h1 (contains embedded Salary: or NHS Trust)
    if raw_h1 and (re.search(r"Salary\s*:", raw_h1, re.I) or
                   re.search(r"\bNHS\b|\bFoundation Trust\b", raw_h1, re.I)):
        parsed = _split_healthjobsuk_h1(raw_h1)
        result.update({k: v for k, v in parsed.items() if v})
    else:
        result["title"] = raw_h1 or None

    def try_fill(label_raw: str, value_raw: str):
        label = label_raw.strip().rstrip(":").strip()
        value = _scrub(value_raw)
        if not value:
            return
        if result["location"] is None and _match_label(label, _LOCATION_LABELS):
            result["location"] = value
        if result["salary"] is None and _match_label(label, _SALARY_LABELS):
            result["salary"] = value
        if result["grade"] is None and _match_label(label, _GRADE_LABELS):
            result["grade"] = value

    # Strategy 1: <dl> <dt>/<dd> pairs
    for dl in soup.find_all("dl"):
        for dt, dd in zip(dl.find_all("dt"), dl.find_all("dd")):
                               
                                    
            try_fill(dt.get_text(), dd.get_text())

    # Strategy 2: <table> rows
    for table in soup.find_all("table"):
        for row in table.find_all("tr"):
            cells = row.find_all(["th", "td"])
            if len(cells) >= 2:
                try_fill(cells[0].get_text(), cells[1].get_text())

    # Strategy 3: <li> with bold/strong label
    for li in soup.find_all("li"):
        strong = li.find(["strong", "b"])
        if strong:
                                     
            try_fill(strong.get_text(), li.get_text().replace(strong.get_text(), "", 1))
                                  

    # Strategy 4: "label: value" in block elements
    for tag in soup.find_all(["p", "div", "span"]):
        # Only consider shallow elements (no nested block tags) to avoid huge blobs
        if tag.find(["p", "div", "table", "ul"]):
            continue
        text = tag.get_text()
                                     
        if ":" in text:
            parts = text.split(":", 1)
            if len(parts[0].split()) <= 4:   # label should be short
                try_fill(parts[0], parts[1])
                         

    return result

# ================= BROWSER FACTORY ================= #
async def create_context(playwright):
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

# ================= HUMAN-LIKE HELPERS ================= #
async def human_scroll(page):
    try:
        total_height = await page.evaluate("document.body.scrollHeight")
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

# ================= SITE-SPECIFIC LISTING PARSERS ================= #

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
            jobs.append({"title": text, "link": normalize_link(href, base), "needs_detail": True})
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

# ================= DETAIL-PAGE FETCHER ================= #
async def fetch_detail_info(context, link: str) -> dict | None:
    """
    Visit a job detail page and return {title, location, salary, grade}.
    Returns None if the page could not be loaded.
    """
    page = await context.new_page()
    try:
        await stealth_async(page)
        await asyncio.sleep(random.uniform(1.5, 3.0))
        ok = await goto_with_retry(page, link, retries=2, timeout=DETAIL_TIMEOUT)
        if not ok:
            return None
        content = await page.content()
        soup = BeautifulSoup(content, "html.parser")
        info = parse_detail_soup(soup)
        log(f"      ↳ title={info['title']!r} | loc={info['location']!r} "
            f"| salary={info['salary']!r} | grade={info['grade']!r}")
        return info
    except Exception as e:
        log(f"   Detail fetch error ({link}): {e}")
        return None
    finally:
        await page.close()

# ================= MAIN SCRAPER ================= #
async def check_site(url: str, seen_jobs: set, seen_sigs: set, context) -> int:
    """Scrape one listing URL; return number of new jobs notified."""
    log(f"🔍 Checking: {url}")
    page = await context.new_page()
    new_jobs = 0
    base = get_base(url)
    parser = get_parser(url)

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

        log(f"   Found {len(candidates)} candidate links.")
        for i, job in enumerate(candidates):
            log(f"   [{i+1}] {job['title']!r} → {job['link']}")

        for job in candidates:
            try:
                title  = job["title"]
                link   = job["link"]
                job_id = extract_job_id(link)

                # Skip if already seen by URL-based ID
                if job_id in seen_jobs:
                    continue

                # Fetch full details from the job page
                info = await fetch_detail_info(context, link)
                await asyncio.sleep(random.uniform(1, 2.5))

                if info and info.get("title"):
                    title = info["title"]
                else:
                    info = {}

                # Apply relevance filter on the real title
                if not relevant_job(title):
                    continue

                # --- Cross-site duplicate check ---
                location = info.get("location") or ""
                sig = make_signature(title, location)
                if sig in seen_sigs:
                    log(f"   ⏭️  Cross-site duplicate, skipping: {title!r}")
                    # Mark ID seen so we don't re-fetch next cycle
                    save_seen(job_id)
                    seen_jobs.add(job_id)
                    continue

                # All clear — notify
                full_info = {
                    "title":    title,
                    "location": info.get("location"),
                    "salary":   info.get("salary"),
                    "grade":    info.get("grade"),
                    "link":     link,
                }
                message = format_message(full_info)
                log(f"   🆕 NEW JOB: {title} | {location}")
                send_telegram(message)

                save_seen(job_id)
                seen_jobs.add(job_id)
                save_seen_signature(sig)
                seen_sigs.add(sig)
                new_jobs += 1

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
    seen_sigs = load_seen_signatures()
    log(f"   Loaded {len(seen_jobs)} seen job IDs, {len(seen_sigs)} cross-site signatures.")

    async with async_playwright() as p:
        browser, context = await create_context(p)
        urls_checked = 0

        while True:
            for url in URLS:
                if urls_checked > 0 and urls_checked % CONTEXT_ROTATE_EVERY == 0:
                    log("🔄 Rotating browser context...")
                    try:
                        await context.close()
                        await browser.close()
                    except Exception:
                        pass
                    browser, context = await create_context(p)

                try:
                    await check_site(url, seen_jobs, seen_sigs, context)
                except Exception as e:
                    log(f"⚠️  Unhandled error on {url}: {e}. Recreating context...")
                    try:
                        await context.close()
                        await browser.close()
                    except Exception:
                        pass
                    browser, context = await create_context(p)

                urls_checked += 1
                await asyncio.sleep(random.uniform(6, 15))

            log(f"💤 Full cycle done. Sleeping {CHECK_INTERVAL}s before next cycle.\n")
            await asyncio.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    asyncio.run(main())
