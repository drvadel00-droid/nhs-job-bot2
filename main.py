import requests
from bs4 import BeautifulSoup
import time
import os
from datetime import datetime, timedelta

# ---------------- CONFIG ---------------- #

BOT_TOKEN = os.environ.get("BOT_TOKEN")  # Telegram Bot Token
CHAT_ID = os.environ.get("CHAT_ID")      # Telegram Chat ID

CHECK_INTERVAL = 120  # seconds (2 minutes)

URLS = [
    "https://jobs.hscni.net/Search?SearchCatID=0",
    "https://www.jobs.nhs.uk/candidate/search/results?keyword=doctor&sort=publicationDateDesc",
    "https://apply.jobs.scot.nhs.uk/Home/Search",
    "https://www.healthjobsuk.com/job_list?JobSearch_q=&JobSearch_d=&JobSearch_g=&JobSearch_re=_POST&JobSearch_re_0=1&JobSearch_re_1=1-_-_-&JobSearch_re_2=1-_-_--_-_-&JobSearch_Submit=Search&_tr=JobSearch&_ts=94511"
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

# ---------------------------------------- #

def load_seen():
    seen = set()
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE, "r") as f:
            for line in f:
                seen.add(line.strip())
    return seen

def save_seen(job_id):
    with open(SEEN_FILE, "a") as f:
        f.write(f"{job_id}\n")

def send_telegram(message):
    if not BOT_TOKEN or not CHAT_ID:
        return
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message}
    try:
        requests.post(url, data=payload, timeout=10)
    except:
        pass

def relevant_job(title):
    title_lower = title.lower()
    if any(ex in title_lower for ex in EXCLUDE_KEYWORDS):
        return False
    specialty_match = any(sp in title_lower for sp in SPECIALTY_KEYWORDS)
    grade_match = any(gr in title_lower for gr in GRADE_KEYWORDS)
    return specialty_match and grade_match

def scrape_url(url, seen_jobs):
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, headers=headers, timeout=20)
        soup = BeautifulSoup(resp.text, "html.parser")
        links = soup.find_all("a", href=True)

        for a in links:
            title = a.get_text(strip=True)
            link = a["href"]

            # fallback: skip very short links or empty title
            if not title or len(title) < 10:
                continue

            if not relevant_job(title):
                continue

            # use link as unique ID
            job_id = link
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
            seen_jobs.add(job_id)

    except Exception as e:
        print(f"Error fetching {url}: {e}")

# ---------------- MAIN LOOP ---------------- #

def main():
    print("🚀 NHS Job Bot started...")
    seen_jobs = load_seen()

    while True:
        for url in URLS:
            scrape_url(url, seen_jobs)
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()
