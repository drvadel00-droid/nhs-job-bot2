# ===============================================
# NHS / HealthJobs Scraper (BeautifulSoup version)
# ===============================================

import requests
from bs4 import BeautifulSoup
import time
import os

# ================= CONFIG ================= #
BOT_TOKEN = "1234567890:AAAFakeExampleBotToken123456789"
CHAT_ID = "-1001234567890"
CHECK_INTERVAL = 300  # 5 minutes

URLS = {
    "nhs_jobs": "https://www.jobs.nhs.uk/candidate/search/results?keyword=doctor&sort=publicationDateDesc",
    "healthjobsuk": "https://www.healthjobsuk.com/job_list",
    "hscni": "https://jobs.hscni.net/Search?SearchCatID=0"
}

EXCLUDE_KEYWORDS = [
    "consultant", "st4", "st5", "st6", "st7",
    "nurse", "midwife", "psychologist",
    "admin", "radiographer", "physiotherapist",
    "manager", "director", "assistant"
]

DOCTOR_TERMS = [
    "doctor", "registrar", "trust doctor",
    "specialty doctor", "clinical fellow", "junior fellow",
    "core trainee", "ct1", "ct2", "ct3",
    "st1", "st2", "st3", "fy1", "fy2"
]

# ================= UTILITIES ================= #

def load_seen():
    if os.path.exists("seen_jobs.txt"):
        with open("seen_jobs.txt", "r") as f:
            return set(f.read().splitlines())
    return set()

def save_seen(job_id):
    with open("seen_jobs.txt", "a") as f:
        f.write(job_id + "\n")

def send_telegram(message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message}
    try:
        requests.post(url, data=payload, timeout=10)
    except Exception as e:
        print("Telegram error:", e)

def relevant_job(title):
    t = title.lower()
    if any(ex in t for ex in EXCLUDE_KEYWORDS):
        return False
    return any(term in t for term in DOCTOR_TERMS)

# ================= SCRAPERS ================= #

def scrape_healthjobsuk(seen_jobs):
    print("🔎 HealthJobsUK...")
    resp = requests.get(URLS["healthjobsuk"])
    soup = BeautifulSoup(resp.text, "html.parser")

    jobs = soup.select("a.jobTitle")

    for job in jobs:
        title = job.get_text(strip=True)
        href = job.get("href")
        if not title or not href:
            continue
        if not relevant_job(title):
            continue
        full_link = f"https://www.healthjobsuk.com{href}"
        job_id = full_link
        if job_id in seen_jobs:
            continue
        message = f"🚨 HealthJobsUK\n\n🏥 {title}\n🔗 {full_link}"
        print(message)
        send_telegram(message)
        save_seen(job_id)
        seen_jobs.add(job_id)

def scrape_nhs_jobs(seen_jobs):
    print("🔎 NHS Jobs...")
    resp = requests.get(URLS["nhs_jobs"])
    soup = BeautifulSoup(resp.text, "html.parser")

    jobs = soup.select("a[data-test='search-result-job-title']")
    for job in jobs:
        title = job.get_text(strip=True)
        href = job.get("href")
        if not title or not href:
            continue
        if not relevant_job(title):
            continue
        job_id = href
        if job_id in seen_jobs:
            continue
        message = f"🚨 NHS England Job\n\n🏥 {title}\n🔗 {href}"
        print(message)
        send_telegram(message)
        save_seen(job_id)
        seen_jobs.add(job_id)

def scrape_hscni(seen_jobs):
    print("🔎 HSCNI...")
    resp = requests.get(URLS["hscni"])
    soup = BeautifulSoup(resp.text, "html.parser")

    jobs = soup.find_all("a")
    for job in jobs:
        title = job.get_text(strip=True)
        href = job.get("href")
        if not title or not href:
            continue
        if not relevant_job(title):
            continue
        job_id = href
        if job_id in seen_jobs:
            continue
        message = f"🚨 Northern Ireland Job\n\n🏥 {title}\n🔗 {href}"
        print(message)
        send_telegram(message)
        save_seen(job_id)
        seen_jobs.add(job_id)

# ================= MAIN LOOP ================= #

def main():
    print("🚀 Smart UK NHS / HealthJobs Scraper Started...\n")
    seen_jobs = load_seen()
    while True:
        try:
            scrape_healthjobsuk(seen_jobs)
            scrape_nhs_jobs(seen_jobs)
            scrape_hscni(seen_jobs)
        except Exception as e:
            print("❌ Error:", e)
        print(f"\n⏳ Sleeping for {CHECK_INTERVAL} seconds...\n")
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()
