import os
import time
import requests
from urllib.parse import urljoin

from bs4 import BeautifulSoup
import requests

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# ================= CONFIG ================= #
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
CHECK_INTERVAL = 300  # 5 minutes

URLS = {
    "nhs_jobs": "https://www.jobs.nhs.uk/candidate/search/results?keyword=doctor&sort=publicationDateDesc",
    "healthjobsuk": "https://www.healthjobsuk.com/job_list",
    "hscni": "https://jobs.hscni.net/Search?SearchCatID=0",
    "nhs_scotland": "https://apply.jobs.scot.nhs.uk/Home/Search"
}

DOCTOR_TERMS = [
    "doctor", "registrar", "ct1", "ct2", "ct3",
    "st1", "st2", "st3", "fy1", "fy2",
    "specialty doctor", "trust doctor", "clinical fellow"
]

EXCLUDE_TERMS = ["consultant", "nurse", "midwife", "admin", "manager"]

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
        print("Telegram Error:", e)

def relevant_job(title):
    t = title.lower()
    if any(ex in t for ex in EXCLUDE_TERMS):
        return False
    return any(term in t for term in DOCTOR_TERMS)

# ================= HEALTHJOBSUK (BeautifulSoup) ================= #

def scrape_healthjobs(seen_jobs):
    print("🔎 HealthJobsUK...")
    r = requests.get(URLS["healthjobsuk"])
    soup = BeautifulSoup(r.text, "html.parser")
    
    for job in soup.select("a.jobTitle"):
        title = job.get_text(strip=True)
        href = urljoin("https://www.healthjobsuk.com", job.get("href"))
        if not relevant_job(title):
            continue
        job_id = href.split("?")[0]
        if job_id in seen_jobs:
            continue
        message = f"🚨 HealthJobsUK Job\n🏥 {title}\n🔗 {href}"
        print(message)
        send_telegram(message)
        save_seen(job_id)
        seen_jobs.add(job_id)

# ================= NHS JOBS (BeautifulSoup) ================= #

def scrape_nhs_jobs(seen_jobs):
    print("🔎 NHS Jobs...")
    r = requests.get(URLS["nhs_jobs"])
    soup = BeautifulSoup(r.text, "html.parser")
    
    for job in soup.select("a[data-test='search-result-job-title']"):
        title = job.get_text(strip=True)
        href = job.get("href")
        if not href.startswith("http"):
            href = urljoin("https://www.jobs.nhs.uk", href)
        if not relevant_job(title):
            continue
        job_id = href.split("?")[0]
        if job_id in seen_jobs:
            continue
        message = f"🚨 NHS England Job\n🏥 {title}\n🔗 {href}"
        print(message)
        send_telegram(message)
        save_seen(job_id)
        seen_jobs.add(job_id)

# ================= HSCNI & NHS SCOTLAND (Selenium) ================= #

def get_driver():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    service = Service()
    return webdriver.Chrome(service=service, options=options)

def scrape_hscni(driver, seen_jobs):
    print("🔎 HSCNI...")
    driver.get(URLS["hscni"])
    WebDriverWait(driver, 20).until(EC.presence_of_all_elements_located((By.TAG_NAME, "a")))
    links = driver.find_elements(By.TAG_NAME, "a")
    for link in links:
        title = link.text.strip()
        href = link.get_attribute("href")
        if not title or not href:
            continue
        if not relevant_job(title):
            continue
        job_id = href.split("?")[0]
        if job_id in seen_jobs:
            continue
        message = f"🚨 Northern Ireland Job\n🏥 {title}\n🔗 {href}"
        print(message)
        send_telegram(message)
        save_seen(job_id)
        seen_jobs.add(job_id)

def scrape_scotland(driver, seen_jobs):
    print("🔎 NHS Scotland...")
    driver.get(URLS["nhs_scotland"])
    WebDriverWait(driver, 20).until(EC.presence_of_all_elements_located((By.TAG_NAME, "a")))
    links = driver.find_elements(By.TAG_NAME, "a")
    for link in links:
        title = link.text.strip()
        href = link.get_attribute("href")
        if not title or not href:
            continue
        if not relevant_job(title):
            continue
        job_id = href.split("?")[0]
        if job_id in seen_jobs:
            continue
        message = f"🚨 Scotland Job\n🏥 {title}\n🔗 {href}"
        print(message)
        send_telegram(message)
        save_seen(job_id)
        seen_jobs.add(job_id)

# ================= MAIN LOOP ================= #

def main():
    seen_jobs = load_seen()
    while True:
        try:
            # BeautifulSoup first
            scrape_healthjobs(seen_jobs)
            scrape_nhs_jobs(seen_jobs)
            
            # Selenium for dynamic sites
            driver = get_driver()
            scrape_hscni(driver, seen_jobs)
            scrape_scotland(driver, seen_jobs)
            driver.quit()
            
        except Exception as e:
            print("❌ Error:", e)
        
        print(f"⏳ Sleeping for {CHECK_INTERVAL} seconds...\n")
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()
