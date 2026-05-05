import asyncio
import random
import re
           
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
PAGE_TIMEOUT = 45_000         # ms — per page.goto()
DETAIL_TIMEOUT = 20_000       # ms — for detail pages
SITE_HARD_LIMIT = 300         # seconds — hard kill per URL task (prevents forever-hang)
TELEGRAM_SEND_INTERVAL = 1.0  # seconds between Telegram sends

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
    """Drains _tg_queue at one message per second to avoid Telegram 429s."""
    api_url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    while True:
        msg = await _tg_queue.get()
        if msg is None:
            _tg_queue.task_done()
            break
        payload = {"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"}
        backoff = 5
        for attempt in range(5):
            try:
                r = requests.post(api_url, data=payload, timeout=10)
                if r.status_code == 200:
                    log("✅ Telegram sent")
                    break
                elif r.status_code == 429:
                    wait = r.json().get("parameters", {}).get("retry_after", backoff)
                    log(f"⚠️  Telegram rate-limit — sleeping {wait}s")
                    await asyncio.sleep(wait)
                    backoff *= 2
                else:
                    log(f"❌ Telegram HTTP {r.status_code}: {r.text[:200]}")
                    break
            except Exception as e:
                log(f"❌ Telegram exception: {e}")
                await asyncio.sleep(backoff)
                backoff *= 2
        _tg_queue.task_done()
        await asyncio.sleep(TELEGRAM_SEND_INTERVAL)

def enqueue_telegram(msg: str):
    _tg_queue.put_nowait(msg)

# ================= HELPERS ================= #
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
    """Safe .get_text() with whitespace collapse."""
    return " ".join(el.get_text().split()) if el else ""

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
    """
    Navigate with retry. Uses domcontentloaded (not networkidle) so the
    call always completes within `timeout` ms and never hangs forever.
    """
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
    Extract everything from the search-result cards directly —
    NO detail-page visit needed.

    Card structure (from actual HTML):
      <li data-test="search-result">
        <a data-test="search-result-job-title">…title…</a>
        <div data-test="search-result-location">
          <h3>  employer  <div class="location-font-size"> location </div> </h3>
        </div>
        <li data-test="search-result-salary">   Salary: <strong>…</strong>  </li>
        <li data-test="search-result-closingDate"> Closing date: <strong>…</strong> </li>
        <li data-test="search-result-publicationDate"> Date posted: <strong>…</strong> </li>
        <li data-test="search-result-jobType"> Contract type: <strong>…</strong> </li>
        <li data-test="search-result-workingPattern"> Working pattern: <strong>…</strong> </li>
      </li>
    """
    jobs = []
    for card in soup.select("li[data-test='search-result']"):
        # ── Link & title ───────────────────────────────────────────────────
        a = card.select_one("a[data-test='search-result-job-title']")
        if not a:
            continue
        href  = normalize_link(a.get("href", ""), base)
        title = txt(a)
        if not title or not href:
            continue

        # ── Employer & location ────────────────────────────────────────────
        loc_block = card.select_one("[data-test='search-result-location']")
        employer = location = ""
        if loc_block:
            h3 = loc_block.find("h3")
            if h3:
                loc_div = h3.find("div", class_="location-font-size")
                if loc_div:
                    location = txt(loc_div)
                    loc_div.extract()          # remove so employer text is clean
                employer = txt(h3)

        # ── Salary ─────────────────────────────────────────────────────────
        salary_li = card.select_one("li[data-test='search-result-salary']")
        salary = txt(salary_li.find("strong")) if salary_li else ""

        # ── Closing date ───────────────────────────────────────────────────
        close_li = card.select_one("li[data-test='search-result-closingDate']")
        closing_date = txt(close_li.find("strong")) if close_li else ""

        # ── Contract type ──────────────────────────────────────────────────
        type_li = card.select_one("li[data-test='search-result-jobType']")
        contract = txt(type_li.find("strong")) if type_li else ""

        jobs.append({
            "title":        title,
            "link":         href,
            "employer":     employer,
            "location":     location,
            "salary":       salary,
            "closing_date": closing_date,
            "contract":     contract,
            "needs_detail": False,     # ← all data already on listing page
            "site":         "nhsjobs",
        })
    return jobs


def parse_healthjobsuk(soup: BeautifulSoup, base: str) -> list[dict]:
    jobs = []
    for a in soup.select("a[href*='/job/']"):
        href = normalize_link(a["href"], base)
        title = txt(a)
        if title and len(title) > 5:
            jobs.append({"title": title, "link": href, "needs_detail": True, "site": "healthjobsuk"})
    return jobs

                                                                
                         
             
                                                             
                                              
                                                           
                           
                    
                         
                                     
                                  
                                                                                               
               

def parse_hscni(soup: BeautifulSoup, base: str) -> list[dict]:
    jobs = []
    for a in soup.select("a[href*='/Job/'], a[href*='/job/'], a[href*='JobID=']"):
        href = normalize_link(a["href"], base)
        title = txt(a)
        if title and len(title) > 5:
            jobs.append({"title": title, "link": href, "needs_detail": True, "site": "hscni"})
    return jobs


def parse_scotland(soup: BeautifulSoup, base: str) -> list[dict]:
    seen: set = set()
    jobs = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "JobId=" not in href and "JobDetail" not in href:
            continue
        full = normalize_link(href, base)
        m = re.search(r"JobId=(\d+)", href)
        uid = m.group(1) if m else full
        if uid in seen:
            continue
        seen.add(uid)
                                     
        jobs.append({"title": txt(a), "link": full, "needs_detail": True, "site": "scotland"})
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

# ================= DETAIL-PAGE FETCH (non-NHS-Jobs sites) ================= #
                                                                                                 
               
                                         
            
                                                                                      
                                                   
                           
                                                   
                                                                                     
                                            
                            
                          
                                                                                    
                            
                         
                                                                                         
                                        
                        
                              
                                                                        
                                        
                        
                

                                                            

                                                             
                                                                          
                         
                                 
              
                                            
                 
                        
             

async def fetch_detail_title(context, link: str) -> str:
    """Fetch <h1> from a detail page. Returns empty string on failure."""
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
                 


                                                              
                         
                                                        
                                                    


# ================= MESSAGE FORMATTER ================= #
def format_message(job: dict, link: str) -> str:
                                                                             
                                                  
                                                  
                                                  
                                                  
                                                  

    lines = ["🚨 <b>NEW NHS JOB</b>\n",
             f"🏥 <b>{job['title']}</b>"]
    if job.get("employer"):
        lines.append(f"🏢 {job['employer']}")
    if job.get("location"):
        lines.append(f"📍 {job['location']}")
    if job.get("salary"):
        lines.append(f"💷 {job['salary']}")
    if job.get("closing_date"):
        lines.append(f"📅 Closes: {job['closing_date']}")
    if job.get("contract"):
        lines.append(f"📋 {job['contract']}")
    lines.append(f"🔗 {link}")
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

                # Fast pre-check
                async with _seen_lock:
                    if job_id in seen_jobs:
                        continue

                # For sites that need a detail-page visit, fetch the real title
                                  
                if job.get("needs_detail"):
                    detail_title = await fetch_detail_title(context, link)
                    if detail_title:
                        job = {**job, "title": detail_title}
                    await asyncio.sleep(random.uniform(0.8, 1.8))

                                                                    
                if not job.get("title") or not relevant_job(job["title"]):
                    continue

                # Atomic claim
                async with _seen_lock:
                    if job_id in seen_jobs:
                        continue
                    seen_jobs.add(job_id)

                log(f"   🆕 NEW JOB: {job['title']}")
                enqueue_telegram(format_message(job, link))
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
    """
    Hard-kill wrapper: if check_site hasn't returned within SITE_HARD_LIMIT
    seconds, cancel it and move on. This is the key fix for the stuck loop.
    """
    try:
        return await asyncio.wait_for(
            check_site(url, seen_jobs, playwright),
            timeout=SITE_HARD_LIMIT,
        )
    except asyncio.TimeoutError:
        log(f"⏰ Hard timeout ({SITE_HARD_LIMIT}s) hit for {url[:60]} — skipping.")
        return 0
    except Exception as e:
        log(f"⚠️  Unexpected error for {url[:60]}: {e}")
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

    # Start Telegram sender in background — lives for the entire process lifetime
    asyncio.create_task(telegram_consumer())

    async with async_playwright() as p:
        cycle = 0
        while True:
            cycle += 1
            log(f"─── CYCLE {cycle} ───────────────────────────────────────────")
            try:
                await run_cycle(seen_jobs, p)
            except Exception as e:
                                                                       
                log(f"🔥 Cycle-level error (will continue): {e}")

                                                                                                                                                     
            log(f"💤 Sleeping {CHECK_INTERVAL}s …\n")
            await asyncio.sleep(CHECK_INTERVAL)   # ← ALWAYS reached


if __name__ == "__main__":
    asyncio.run(main())
