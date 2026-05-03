import asyncio
import random
import re
import time  # Added
import requests  # Added
from datetime import datetime
from bs4 import BeautifulSoup  # Added
from playwright.async_api import async_playwright
# import playwright_stealth
from playwright_stealth import stealth_async
from fake_useragent import UserAgent

# ================= CONFIG ================= #
BOT_TOKEN = "8213751012:AAFYvubDXeY3xU8vjaWLxNTT7XqMtPhUuwQ"
CHAT_ID = "-1003888963521"
CHECK_INTERVAL = 120  # seconds                                                          

ua = UserAgent() 
URLS = [
    # HealthJobsUK (newest first)
    "https://www.healthjobsuk.com/job_list?JobSearch_Submit=Search&_srt=publicationdate&_sd=desc",
    "https://www.healthjobsuk.com/job_list?JobSearch_q=&JobSearch_d=534&JobSearch_g=&JobSearch_re=_POST&JobSearch_re_0=1&JobSearch_re_1=1-_-_-&JobSearch_re_2=1-_-_--_-_-&JobSearch_Submit=Search&_tr=JobSearch&_ts=64082&_srt=startdate&_sd=d",
    "https://www.healthjobsuk.com/job_list?JobSearch_q=&JobSearch_d=737&JobSearch_g=&JobSearch_re=_POST&JobSearch_re_0=1&JobSearch_re_1=1-_-_-&JobSearch_re_2=1-_-_--_-_-&JobSearch_Submit=Search&_tr=JobSearch&_ts=81534&_srt=startdate&_sd=a",
    "https://www.healthjobsuk.com/job_list?JobSearch_q=&JobSearch_d=594&JobSearch_g=&JobSearch_re=_POST&JobSearch_re_0=1&JobSearch_re_1=1-_-_-&JobSearch_re_2=1-_-_--_-_-&JobSearch_Submit=Search&_tr=JobSearch&_ts=88730&_srt=startdate&_sd=a",
    "https://www.healthjobsuk.com/job_list?JobSearch_q=&JobSearch_d=572&JobSearch_g=&JobSearch_re=_POST&JobSearch_re_0=1&JobSearch_re_1=1-_-_-&JobSearch_re_2=1-_-_--_-_-&JobSearch_Submit=Search&_tr=JobSearch&_ts=97667&_srt=startdate&_sd=a",
    "https://www.healthjobsuk.com/job_list?JobSearch_q=&JobSearch_d=558&JobSearch_g=&JobSearch_re=_POST&JobSearch_re_0=1&JobSearch_re_1=1-_-_-&JobSearch_re_2=1-_-_--_-_-&JobSearch_Submit=Search&_tr=JobSearch&_ts=110250&_srt=startdate&_sd=a",
    "https://www.healthjobsuk.com/job_list?JobSearch_q=&JobSearch_d=581&JobSearch_g=&JobSearch_re=_POST&JobSearch_re_0=1&JobSearch_re_1=1-_-_-&JobSearch_re_2=1-_-_--_-_-&JobSearch_Submit=Search&_tr=JobSearch&_ts=44291&_srt=startdate&_sd=a",
    
    # NHS Jobs England
    "https://www.jobs.nhs.uk/candidate/search/results?keyword=doctor&sort=publicationDateDesc",
    "https://www.jobs.nhs.uk/candidate/search/results?searchFormType=sortBy&sort=publicationDateDesc&searchByLocationOnly=true&language=en#",

    # HSCNI (Northern Ireland)
    "https://jobs.hscni.net/Search?SearchCatID=0",

    # Scotland
    "https://apply.jobs.scot.nhs.uk/Home/Search"
]

# ================= FILTERS ================= #
MEDICAL_SPECIALTIES = [
    "medicine", "acute", "internal", "general medicine",
    "surgery", "general surgery", "trauma", "orthopaedic",
    "plastic", "emergency", "cardiology", "respiratory",
    "gastro", "neurology", "paediatric", "haematology",
    "intensive care", "critical care", "icu", "vascular", "urology"
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
    "locum doctor"
]

EXCLUDE_KEYWORDS = [
    "consultant", "st4", "st5", "st6", "st7",
    "nurse", "midwife", "assistant",
    "manager", "director", "admin",
    "physiotherapist", "radiographer",
    "lead",
    "scientist", "receptionist", "housekeeper", "cook", "clerk", 
    "practitioner",
    "nutritionist",
    "nutrition", "coordinator", "therapist", "secretary", "pharmacist", "matron", "worker"
]

# ================= LOGGING ================= #
def log(message):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {message}", flush=True)

# ================= HEADERS ================= #
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-GB,en;q=0.9",
    "Connection": "keep-alive"
}

# ================= UTILITIES ================= #
def load_seen():
    try:
        with open("seen_jobs.txt", "r") as f:
            return set(f.read().splitlines())
    except:
        return set()

def save_seen(job_id):
    with open("seen_jobs.txt", "a") as f:
        f.write(job_id + "\n")

# ================= TELEGRAM ================= #
def send_telegram(message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message}

    while True:
        try:
            r = requests.post(url, data=payload, timeout=10)

            if r.status_code == 200:
                log(f"Telegram status: {r.status_code}")
                break

            elif r.status_code == 429:
                retry_after = 5
                try:
                    retry_after = r.json().get("parameters", {}).get("retry_after", 5)
                except:
                    pass
                log(f"⚠️ Telegram rate limit hit. Sleeping {retry_after}s")
                time.sleep(retry_after)

            else:
                log(f"Telegram error: {r.status_code}")
                break

        except Exception as e:
            log(f"Telegram ERROR: {e}")
            break

def relevant_job(title):
    t = title.lower()

    if any(ex in t for ex in EXCLUDE_KEYWORDS):
        return False

    if not any(sp in t for sp in MEDICAL_SPECIALTIES):
        return False

    if not any(gr in t for gr in GRADE_KEYWORDS):
        return False

    return True

def extract_job_id(link):
    match = re.search(r"\d+", link)
    return match.group() if match else link

def normalize_link(link, base):
    if link.startswith("/"):
        return base + link
    return link

# ================= FETCH TITLE ================= #
def fetch_real_title(url):
    try:
        session = requests.Session()
        session.headers.update(HEADERS)

        r = session.get(url, timeout=10)

        if r.status_code == 403:
            log("⚠️ 403 on job page, retrying with new session...")
            time.sleep(5)

            session = requests.Session()
            session.headers.update(HEADERS)
            r = session.get(url, timeout=10)

            if r.status_code == 403:
                return None

        if r.status_code != 200:
            return None

        soup = BeautifulSoup(r.text, "html.parser")
        h1 = soup.find("h1")
        if h1:
            return h1.get_text(strip=True)

    except Exception as e:
        log(f"Error fetching real title: {e}")

    return None

# ================= SCRAPER ================= #
                              

async def check_site_stealth(url, seen_jobs, context):
    log(f"Checking: {url}")
    page = await context.new_page()
    
    # You MUST await the stealth initialization
    await stealth_async(page)
    # Use stealth_sync (it works for async pages too)
    # This is more compatible with different versions of the library
    try:
        await page.goto(url, wait_until="networkidle")
        playwright_stealth.stealth_sync(page)
    except AttributeError:
        # Fallback for older versions
        await playwright_stealth.stealth_async(page)
    
    await asyncio.sleep(random.uniform(2, 5))
    
    try:
        response = await page.goto(url, wait_until="networkidle", timeout=60000)
        
        if not response or response.status == 403:
            log(f"❌ Blocked (403) or no response from {url}. Skipping.")
            return

        log(f"Status code: {response.status}")
        content = await page.content()
        soup = BeautifulSoup(content, "html.parser")
        links = soup.find_all("a", href=True)
        
        base_match = re.match(r"(https?://[^/]+)", url)
        base = base_match.group(1) if base_match else ""

        new_jobs = 0

        for a in links:
            try:
                raw_text = a.get_text(strip=True)
                link = normalize_link(a["href"], base)

                if not raw_text or len(raw_text) < 5:
                    continue

                if "jobs.nhs.uk" in url and "/Job/" not in link:
                    continue
                if "healthjobsuk.com" in url and "job" not in link.lower():
                    continue

                if "healthjobsuk.com/job/" in link:
                    title = raw_text
                    try:
                        temp_page = await context.new_page()
                        # Fixed the call here as well
                        playwright_stealth.stealth_sync(temp_page) 
                        await temp_page.goto(link, wait_until="domcontentloaded", timeout=15000)
                        h1 = await temp_page.query_selector("h1")
                        if h1:
                            title = await h1.inner_text()
                        await temp_page.close()
                    except:
                        pass
                    await asyncio.sleep(random.uniform(1, 2))
                else:
                    title = raw_text

                if not relevant_job(title):
                    continue

                job_id = extract_job_id(link)
                if job_id in seen_jobs:
                    continue

                message = f"🚨 NEW NHS JOB\n\n🏥 {title}\n🔗 {link}"
                log(f"NEW JOB: {title}")
                send_telegram(message)

                save_seen(job_id)
                seen_jobs.add(job_id)
                new_jobs += 1
                                    
            except Exception as e:
                log(f"Error processing link: {e}")

        log(f"Found {new_jobs} new jobs on this site.")

    except Exception as e:
        log(f"SCRAPER ERROR on {url}: {e}")
    finally:
        await page.close()

async def main():
    log("🚀 NHS JOB BOT STARTED (STEALTH MODE)")
    seen_jobs = load_seen()
    
    async with async_playwright() as p:
        # Launching a visible browser (headless=False) is harder to detect, 
        # but headless=True is fine if stealth is applied correctly.
        browser = await p.chromium.launch(headless=True)
        
        # Create a browser context with a random User-Agent
        context = await browser.new_context(
            user_agent=ua.random,
            viewport={'width': 1920, 'height': 1080}
        )

        while True:
            for url in URLS:
                await check_site_stealth(url, seen_jobs, context)
                # Small break between different site URLs
                await asyncio.sleep(random.uniform(5, 10))

            log(f"Sleeping {CHECK_INTERVAL} seconds...\n")
            await asyncio.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    asyncio.run(main())
