import requests
from bs4 import BeautifulSoup
import time
import datetime
import re
import os

# ---------------- CONFIG ---------------- #

BOT_TOKEN = os.environ.get("BOT_TOKEN")  # Optional for Telegram
CHAT_ID = os.environ.get("CHAT_ID")      # Optional for Telegram

CHECK_INTERVAL = 120  # 2 minutes

# URLs to monitor
URLS = [
    # Broad HealthJobsUK search
    "https://www.healthjobsuk.com/job_list?JobSearch_q=&JobSearch_d=&JobSearch_g=&JobSearch_re=_POST&JobSearch_re_0=1&JobSearch_re_1=1-_-_-&JobSearch_re_2=1-_-_--_-_-&JobSearch_Submit=Search&_tr=JobSearch&_ts=94511",
    
    # NHS Jobs England
    "https://www.jobs.nhs.uk/candidate/search/results?keyword=doctor&sort=publicationDateDesc",

    # Scotland
    "https://apply.jobs.scot.nhs.uk/Home/Search",

    # Northern Ireland
    "https://jobs.hscni.net/Search?SearchCatID=0"
]

SPECIALTY_KEYWORDS = [
    "general surgery",
    "trauma",
    "orthopaedic",
    "orthopedic",
    "plastic surgery",
    "paediatric surgery",
    "pediatric surgery",
    "internal medicine",
    "general medicine",
    "emergency medicine",
    "emergency department"
]

GRADE_KEYWORDS = [
    "junior",
    "specialty doctor",
    "trust doctor",
    "st1",
    "st2",
    "st3",
    "clinical fellow",
    "junior fellow",
    "research fellow",
    "core",
    "ct1",
    "ct2"
]

EXCLUDE_KEYWORDS = [
    "consultant",
    "nurse",
    "midwife",
    "pharmacist",
    "physiotherapist",
    "radiographer",
    "healthcare assistant",
    "admin",
    "manager",
    "director"
]

# ---------------------------------------- #

# Persistent job storage
def load_seen():
    try:
        with open("seen_jobs.txt", "r") as f:
            return set(f.read().splitlines())
    except:
        return set()

def save_seen(job_id):
    with open("seen_jobs.txt", "a") as f:
        f.write(job_id + "\n")

# Filter jobs by specialty + grade + exclusion
def relevant_job(title):
    title_lower = title.lower()

    if any(ex in title_lower for ex in EXCLUDE_KEYWORDS):
        return False

    specialty_match = any(sp in title_lower for sp in SPECIALTY_KEYWORDS)
    grade_match = any(gr in title_lower for gr in GRADE_KEYWORDS)

    return specialty_match and grade_match

# Extract numeric job ID from link
def extract_job_id(link):
    match = re.search(r'\d+', link)
    return match.group() if match else link

# Optional: send Telegram message
def send_telegram(message):
    if not BOT_TOKEN or not CHAT_ID:
        return
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message}
    try:
        requests.post(url, data=payload, timeout=10)
    except:
        pass

# Core function to check one site
def check_site(url, seen_jobs):
    print(f"Checking {url}")

    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(response.text, "html.parser")

        job_links = soup.find_all("a", href=True)

        for a in job_links:
            title = a.get_text(strip=True)
            link = a["href"]

            if not title or len(title) < 10:
                continue

            # Only consider links that look like job pages
            if "/Job/" not in link.lower() and "vacancy" not in link.lower():
                continue

            if not relevant_job(title):
                continue

            job_id = extract_job_id(link)

            if job_id in seen_jobs:
                continue

            # NEW JOB FOUND
            print("\n=== NEW JOB FOUND ===")
            print("Title:", title)
            print("Link:", link)
            print("=====================\n")

            # Send Telegram alert
            send_telegram(f"🚨 New Job Found:\n{title}\n{link}")

            save_seen(job_id)
            seen_jobs.add(job_id)

    except Exception as e:
        print(f"Error checking {url}: {e}")

# Main loop
def main():
    print("🚀 Job Monitoring Bot started...")
    seen_jobs = load_seen()

    while True:
        for url in URLS:
            check_site(url, seen_jobs)

        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()
