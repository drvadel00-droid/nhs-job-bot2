import requests
from bs4 import BeautifulSoup
import time
import re
import os
from datetime import datetime, timedelta
from threading import Thread

# ---------------- CONFIG ---------------- #

BOT_TOKEN = os.environ.get("BOT_TOKEN")  # Telegram Bot Token
CHAT_ID = os.environ.get("CHAT_ID")      # Telegram Chat ID

CHECK_INTERVAL = 120  # seconds (2 minutes)

# Sites to monitor
URLS = [
    # HealthJobsUK
    "https://www.healthjobsuk.com/job_list?JobSearch_q=&JobSearch_d=&JobSearch_g=&JobSearch_re=_POST&JobSearch_re_0=1&JobSearch_re_1=1-_-_-&JobSearch_re_2=1-_-_--_-_-&JobSearch_Submit=Search&_tr=JobSearch&_ts=94511",
    # NHS Jobs England
    "https://www.jobs.nhs.uk/candidate/search/results?keyword=doctor&sort=publicationDateDesc",
    # Scotland
    "https://apply.jobs.scot.nhs.uk/Home/Search",
    # Northern Ireland
    "https://jobs.hscni.net/Search?SearchCatID=0"
]

SPECIALTY_KEYWORDS = [
    "general surgery", "trauma", "orthopaedic", "orthopedic", "plastic surgery",
    "paediatric surgery", "pediatric surgery", "internal medicine", "general medicine",
    "emergency medicine", "emergency department"
]

GRADE_KEYWORDS = [
    "junior", "specialty doctor", "trust doctor", "st1", "st2", "st3",
    "clinical fellow", "junior fellow", "research fellow", "core", "ct1", "ct2"
]

EXCLUDE_KEYWORDS = [
    "consultant", "nurse", "midwife", "pharmacist", "physiotherapist",
    "radiographer", "healthcare assistant", "admin", "manager", "director"
]

SEEN_FILE = "seen_jobs.txt"
MAX_JOB_AGE_DAYS = 60  # clean old IDs after 60 days

# ---------------------------------------- #

def load_seen():
    seen = {}
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE, "r") as f:
            for line in f:
                line = line.strip()
                if "||" in line:
                    job_id, ts = line.split("||")
                    seen[job_id] = datetime.fromisoformat(ts)
    return seen

def save_seen(job_id):
    with open(SEEN_FILE, "a") as f:
        f.write(f"{job_id}||{datetime.now().isoformat()}\n")

def clean_seen(seen_jobs):
    cutoff = datetime.now() - timedelta(days=MAX_JOB_AGE_DAYS)
    new_seen = {jid: ts for jid, ts in seen_jobs.items() if ts >= cutoff}
    with open(SEEN_FILE, "w") as f:
        for jid, ts in new_seen.items():
            f.write(f"{jid}||{ts.isoformat()}\n")
    return new_seen

def relevant_job(title):
    title_lower = title.lower()
    if any(ex in title_lower for ex in EXCLUDE_KEYWORDS):
        return False
    specialty_match = any(sp in title_lower for sp in SPECIALTY_KEYWORDS)
    grade_match = any(gr in title_lower for gr in GRADE_KEYWORDS)
    return specialty_match and grade_match

def extract_job_id(link):
    match = re.search(r'\d+', link)
    return match.group() if match else link

def send_telegram(message):
    if not BOT_TOKEN or not CHAT_ID:
        return
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message}
    try:
        requests.post(url, data=payload, timeout=10)
    except:
        pass

def scrape_url(url, seen_jobs):
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, timeout=20)
        soup = BeautifulSoup(response.text, "html.parser")
        links = soup.find_all("a", href=True)
        for a in links:
            title = a.get_text(strip=True)
            link = a["href"]

            # Ignore very short or empty titles
            if not title or len(title) < 10:
                continue

            # Consider links that contain numeric IDs
            if not re.search(r'\d+', link):
                continue

            if not relevant_job(title):
                continue

            job_id = extract_job_id(link)
            if job_id in seen_jobs:
                continue

            # New job detected
            print("\n=== NEW JOB FOUND ===")
            print("Title:", title)
            print("Link:", link)
            print("Source:", url)
            print("=====================\n")

            send_telegram(f"🚨 New Job Found:\n{title}\n{link}\nSource: {url}")
            save_seen(job_id)
            seen_jobs[job_id] = datetime.now()

    except Exception as e:
        print(f"Error scraping {url}: {e}")

def main():
    print("🚀 NHS Job Bot started...")
    seen_jobs = load_seen()
    seen_jobs = clean_seen(seen_jobs)

    while True:
        threads = []
        for url in URLS:
            t = Thread(target=scrape_url, args=(url, seen_jobs))
            t.start()
            threads.append(t)

        for t in threads:
            t.join()

        seen_jobs = clean_seen(seen_jobs)
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()
