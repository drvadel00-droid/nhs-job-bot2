import requests
import time
import os
from urllib.parse import urljoin

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
    "nhs_jobs": "https://www.jobs.nhs.uk/api/search/results",
    "healthjobsuk": "https://www.healthjobsuk.com/job_list",
    "hscni": "https://jobs.hscni.net/Search?SearchCatID=0",
    "nhs_scotland": "https://apply.jobs.scot.nhs.uk/api/vacancies"
}

# ================= FILTER KEYWORDS ================= #

EXCLUDE_KEYWORDS = [
    "consultant", "st4", "st5", "st6", "st7",
    "nurse", "midwife", "psychologist",
    "admin", "radiographer", "physiotherapist",
    "manager", "director", "assistant"
]

DOCTOR_TERMS = [
    "doctor", "clinical fellow", "junior clinical fellow", "senior clinical fellow",
    "registrar", "trust doctor", "specialty doctor",
    "core trainee", "ct1", "ct2", "ct3", "st1", "st2", "st3", "fy1", "fy2"
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

def extract_job_id(link):
    return link.split("?")[0]

# ================= DRIVER SETUP ================= #

def get_driver():
    chrome_options = Options()
    chrome_options.binary_location = "/usr/bin/google-chrome"
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    service = Service()
    return webdriver.Chrome(service=service, options=chrome_options)

# ================= SCRAPERS ================= #

# --- NHS England (API) ---
def scrape_nhs_jobs(seen_jobs):
    print("🔎 NHS Jobs (England)...")
    params = {"keyword": "doctor", "sort": "publicationDateDesc", "page": 1, "resultsPerPage": 20}
    try:
        r = requests.get(URLS["nhs_jobs"], params=params, timeout=15)
        data = r.json()
        for job in data.get("results", []):
            title = job.get("title")
            href = job.get("url")
            if not title or not href:
                continue
            if not relevant_job(title):
                continue
            job_id = extract_job_id(href)
            if job_id in seen_jobs:
                continue
            message = f"🚨 NHS England Job\n\n🏥 {title}\n🔗 {href}"
            print(message)
            send_telegram(message)
            save_seen(job_id)
            seen_jobs.add(job_id)
    except Exception as e:
        print("Error scraping NHS Jobs:", e)

# --- NHS Scotland (API) ---
def scrape_scotland(seen_jobs):
    print("🔎 NHS Scotland...")
    try:
        r = requests.get(URLS["nhs_scotland"], timeout=15)
        data = r.json()
        for job in data.get("Vacancies", []):
            title = job.get("VacancyTitle")
            href = job.get("VacancyURL")
            if not title or not href:
                continue
            if not relevant_job(title):
                continue
            job_id = extract_job_id(href)
            if job_id in seen_jobs:
                continue
            message = f"🚨 NHS Scotland Job\n\n🏥 {title}\n🔗 {href}"
            print(message)
            send_telegram(message)
            save_seen(job_id)
            seen_jobs.add(job_id)
    except Exception as e:
        print("Error scraping NHS Scotland:", e)

# --- HealthJobsUK (Selenium) ---
def scrape_healthjobsuk(driver, seen_jobs):
    print("🔎 HealthJobsUK...")
    driver.get(URLS["healthjobsuk"])
    try:
        WebDriverWait(driver, 15).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, "a.jobTitle"))
        )
        jobs = driver.find_elements(By.CSS_SELECTOR, "a.jobTitle")
        for job in jobs:
            title = job.text.strip()
            href = job.get_attribute("href")
            if not title or not href:
                continue
            if not relevant_job(title):
                continue
            full_link = urljoin("https://www.healthjobsuk.com", href)
            job_id = extract_job_id(full_link)
            if job_id in seen_jobs:
                continue
            message = f"🚨 HealthJobsUK\n\n🏥 {title}\n🔗 {full_link}"
            print(message)
            send_telegram(message)
            save_seen(job_id)
            seen_jobs.add(job_id)
    except Exception as e:
        print("Error scraping HealthJobsUK:", e)

# --- HSCNI (Selenium) ---
def scrape_hscni(driver, seen_jobs):
    print("🔎 HSCNI (Northern Ireland)...")
    driver.get(URLS["hscni"])
    try:
        WebDriverWait(driver, 15).until(
            EC.presence_of_all_elements_located((By.TAG_NAME, "a"))
        )
        links = driver.find_elements(By.TAG_NAME, "a")
        for link in links:
            title = link.text.strip()
            href = link.get_attribute("href")
            if not title or not href:
                continue
            if not relevant_job(title):
                continue
            job_id = extract_job_id(href)
            if job_id in seen_jobs:
                continue
            message = f"🚨 Northern Ireland Job\n\n🏥 {title}\n🔗 {href}"
            print(message)
            send_telegram(message)
            save_seen(job_id)
            seen_jobs.add(job_id)
    except Exception as e:
        print("Error scraping HSCNI:", e)

# ================= MAIN LOOP ================= #

def main():
    print("🚀 Smart UK NHS Doctor Job Bot Started...\n")
    seen_jobs = load_seen()
    while True:
        driver = None
        try:
            driver = get_driver()
            scrape_nhs_jobs(seen_jobs)
            scrape_scotland(seen_jobs)
            scrape_healthjobsuk(driver, seen_jobs)
            scrape_hscni(driver, seen_jobs)
        except Exception as e:
            print("❌ Main loop error:", e)
        finally:
            if driver:
                driver.quit()
        print(f"\n⏳ Sleeping for {CHECK_INTERVAL} seconds...\n")
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()
