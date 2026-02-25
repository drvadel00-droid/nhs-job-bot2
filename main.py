import requests
from bs4 import BeautifulSoup
import time
import re
import sys
from datetime import datetime

# ================= CONFIG ================= #
BOT_TOKEN = "8213751012:AAFYvubDXeY3xU8vjaWLxNTT7XqMtPhUuwQ"
CHAT_ID = "-1003888963521"
CHECK_INTERVAL = 120  # seconds

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
    "intensive care", "critical care", "icu"
]

GRADE_KEYWORDS = [
    "fy1", "fy2", "foundation",
    "ct1", "ct2", "ct3",
    "st1", "st2", "st3",
    "registrar",
    "trust doctor", "trust grade",
    "clinical fellow", "junior fellow",
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
    "scientist",
    "practitioner",
    "nutritionist",
    "nutrition"
]

# ================= LOGGING ================= #
def log(message):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {message}", flush=True)

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

def send_telegram(message):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        payload = {"chat_id": CHAT_ID, "text": message}
        r = requests.post(url, data=payload, timeout=10)
        log(f"Telegram status: {r.status_code}")
    except Exception as e:
        log(f"Telegram ERROR: {e}")

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

# ================= SCRAPER ================= #
def check_site(url, seen_jobs):
    log(f"Checking: {url}")

    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(url, headers=headers, timeout=20)

        log(f"Status code: {r.status_code}")

        soup = BeautifulSoup(r.text, "html.parser")
        links = soup.find_all("a", href=True)

        log(f"Found {len(links)} total links")

        base = re.match(r"(https?://[^/]+)", url).group(1)

        new_jobs = 0

        for a in links:
            title = a.get_text(strip=True)
            link = normalize_link(a["href"], base)

            if not title or len(title) < 5:
                continue

            # NHS Jobs filter
            if "jobs.nhs.uk" in url and "/Job/" not in link:
                continue

            # HealthJobsUK filter
            if "healthjobsuk.com" in url and "job" not in link.lower():
                continue

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

        log(f"New jobs found: {new_jobs}")

    except Exception as e:
        log(f"SCRAPER ERROR: {e}")

# ================= MAIN LOOP ================= #
def main():
    log("🚀 NHS JOB BOT STARTED")
    seen_jobs = load_seen()

    while True:
        for url in URLS:
            check_site(url, seen_jobs)

        log(f"Sleeping {CHECK_INTERVAL} seconds...\n")
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()
