import requests
from bs4 import BeautifulSoup
import time
import os

# ================= CONFIG ================= #
BOT_TOKEN = "8213751012:AAFYvubDXeY3xU8vjaWLxNTT7XqMtPhUuwQ"
CHAT_ID = "-1003888963521"
CHECK_INTERVAL = 300  # 5 minutes

URLS = {
    "nhs_jobs": "https://www.jobs.nhs.uk/candidate/search/results?keyword=doctor&sort=publicationDateDesc",
    "healthjobsuk": "https://www.healthjobsuk.com/job_list"
}

DOCTOR_TERMS = [
    "doctor", "clinical fellow", "junior clinical fellow", "senior clinical fellow",
    "registrar", "trust doctor", "specialty doctor",
    "core trainee", "ct1", "ct2", "ct3", "st1", "st2", "st3", "fy1", "fy2"
]

EXCLUDE_KEYWORDS = [
    "consultant", "st4", "st5", "st6", "st7",
    "nurse", "midwife", "psychologist", "admin",
    "radiographer", "physiotherapist", "manager",
    "director", "assistant"
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
    r = requests.get(URLS["healthjobsuk"])
    soup = BeautifulSoup(r.text, "html.parser")
    
    jobs = soup.select("a.jobTitle")  # works for HealthJobsUK
    for job in jobs:
        title = job.get_text(strip=True)
        href = job.get("href")
        if not href or not title or not relevant_job(title):
            continue
        full_link = f"https://www.healthjobsuk.com{href}"
        job_id = href.split("/")[-1]
        if job_id in seen_jobs:
            continue
        message = f"🚨 HealthJobsUK Job\n\n🏥 {title}\n🔗 {full_link}"
        print(message)
        send_telegram(message)
        save_seen(job_id)
        seen_jobs.add(job_id)

def scrape_nhs_jobs(seen_jobs):
    print("🔎 NHS Jobs...")
    r = requests.get(URLS["nhs_jobs"])
    soup = BeautifulSoup(r.text, "html.parser")
    
    jobs = soup.select("a[data-test='search-result-job-title']")
    for job in jobs:
        title = job.get_text(strip=True)
        href = job.get("href")
        if not href or not title or not relevant_job(title):
            continue
        job_id = href.split("?")[0]
        if job_id in seen_jobs:
            continue
        message = f"🚨 NHS England Job\n\n🏥 {title}\n🔗 {href}"
        print(message)
        send_telegram(message)
        save_seen(job_id)
        seen_jobs.add(job_id)

# ================= MAIN LOOP ================= #

def main():
    print("🚀 UK Doctor Job Bot Started...")
    seen_jobs = load_seen()
    while True:
        try:
            scrape_healthjobsuk(seen_jobs)
            scrape_nhs_jobs(seen_jobs)
        except Exception as e:
            print("❌ Error:", e)
        print(f"\n⏳ Sleeping {CHECK_INTERVAL} seconds...\n")
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()
