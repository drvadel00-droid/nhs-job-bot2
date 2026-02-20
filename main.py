import requests
from bs4 import BeautifulSoup
import time
import datetime
import re

# ---------------- CONFIG ---------------- #

BOT_TOKEN = "<YOUR_BOT_TOKEN>"      # Replace with your Telegram bot token
CHAT_ID = "-1003888963521"          # Your private channel numeric ID

CHECK_INTERVAL = 120  # 2 minutes

# URLs to monitor
URLS = [
    # England HealthJobsUK search
    "https://www.healthjobsuk.com/job_list?JobSearch_q=&JobSearch_d=&JobSearch_g=&JobSearch_re=_POST&JobSearch_re_0=1&JobSearch_re_1=1-_-_-&JobSearch_re_2=1-_-_--_-_-&JobSearch_Submit=Search&_tr=JobSearch&_ts=94511",
    
    # NHS Jobs England
    "https://www.jobs.nhs.uk/candidate/search/results?keyword=doctor&sort=publicationDateDesc",

    # Scotland
    "https://apply.jobs.scot.nhs.uk/Home/Search",

    # Northern Ireland
    "https://jobs.hscni.net/Search?SearchCatID=0"
]

# Keywords to include
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
    "emergency department",
    "cardiology",
    "oncology",
    "neurology",
    "obstetrics",
    "gynaecology",
    "respiratory"
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
    "ct2",
    "sas"
]

# Keywords to exclude
EXCLUDE_KEYWORDS = [
    "consultant",
    "st4",
    "st5",
    "st6",
    "st7",
    "nurse",
    "midwife",
    "pharmacist",
    "physiotherapist",
    "radiographer",
    "healthcare assistant",
    "admin",
    "manager",
    "director",
    "higher specialty"
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

# Send Telegram message
def send_telegram(message):
    if not BOT_TOKEN or not CHAT_ID:
        print("Telegram not configured")
        return
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message}
    try:
        r = requests.post(url, data=payload, timeout=10)
        print(f"Telegram response: {r.status_code}")
    except Exception as e:
        print("Telegram send error:", e)

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
            if "/Job/" not in link.lower() and "vacancy" not in link.lower() and "job" not in link.lower():
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

            # Format message nicely for Telegram
            message = f"🚨 *New NHS Job Found!*\n\n*Title:* {title}\n*Link:* https://{url.split('/')[2]}{link}" \
                      if link.startswith("/") else f"🚨 *New NHS Job Found!*\n\n*Title:* {title}\n*Link:* {link}"

            send_telegram(message)

            save_seen(job_id)
            seen_jobs.add(job_id)

    except Exception as e:
        print(f"Error checking {url}: {e}")

# Main loop
def main():
    print("🚀 NHS Job Bot started...")
    seen_jobs = load_seen()

    while True:
        for url in URLS:
            check_site(url, seen_jobs)

        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()
