import os
import time
import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from urllib.parse import urljoin, urlencode

# ================= CONFIG ================= #
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
CHECK_INTERVAL = 300  # 5 minutes

# ================= FILTER LOGIC ================= #
EXCLUDE_KEYWORDS = [
    "consultant", "st4", "st5", "st6", "st7",
    "nurse", "midwife", "psychologist",
    "admin", "radiographer", "physiotherapist",
    "manager", "director", "assistant"
]

DOCTOR_TERMS = [
    "doctor", "clinical fellow", "junior clinical fellow",
    "senior clinical fellow", "registrar", "trust doctor",
    "specialty doctor", "core trainee", "ct1", "ct2", "ct3",
    "st1", "st2", "st3", "fy1", "fy2"
]

def relevant_job(title):
    t = title.lower()
    if any(ex in t for ex in EXCLUDE_KEYWORDS):
        return False
    return any(term in t for term in DOCTOR_TERMS)

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

# ================= DRIVER ================= #
def get_driver():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    service = Service()
    return webdriver.Chrome(service=service, options=options)

# ================= NHS JOBS ENGLAND ================= #
def scrape_nhs_jobs(seen_jobs):
    print("🔎 NHS Jobs England (API)...")
    base_url = "https://www.jobs.nhs.uk/xi/search"
    params = {"q": "doctor", "sort": "publicationDateDesc"}
    try:
        resp = requests.get(base_url, params=params, timeout=15)
        soup = BeautifulSoup(resp.text, "html.parser")
        links = soup.select("a[data-test='search-result-job-title']")
        for job in links:
            title = job.text.strip()
            href = urljoin(base_url, job.get("href"))
            if not relevant_job(title):
                continue
            job_id = href.split("?")[0]
            if job_id in seen_jobs:
                continue
            message = f"🚨 NHS England Job\n\n🏥 {title}\n🔗 {href}"
            print(message)
            send_telegram(message)
            save_seen(job_id)
            seen_jobs.add(job_id)
    except Exception as e:
        print("NHS Jobs Error:", e)

# ================= HEALTHJOBSUK ================= #
def scrape_healthjobsuk(seen_jobs):
    print("🔎 HealthJobsUK...")
    base_url = "https://www.healthjobsuk.com/job_list"
    try:
        resp = requests.get(base_url, timeout=15)
        soup = BeautifulSoup(resp.text, "html.parser")
        jobs = soup.select("a.jobTitle")
        for job in jobs:
            title = job.text.strip()
            href = urljoin(base_url, job.get("href"))
            if not relevant_job(title):
                continue
            job_id = href.split("?")[0]
            if job_id in seen_jobs:
                continue
            message = f"🚨 HealthJobsUK\n\n🏥 {title}\n🔗 {href}"
            print(message)
            send_telegram(message)
            save_seen(job_id)
            seen_jobs.add(job_id)
    except Exception as e:
        print("HealthJobsUK Error:", e)

# ================= HSCNI ================= #
def scrape_hscni(driver, seen_jobs):
    print("🔎 HSCNI (NI)...")
    url = "https://jobs.hscni.net/Search?SearchCatID=0"
    driver.get(url)
    WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.TAG_NAME, "a")))
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
        message = f"🚨 Northern Ireland Job\n\n🏥 {title}\n🔗 {href}"
        print(message)
        send_telegram(message)
        save_seen(job_id)
        seen_jobs.add(job_id)

# ================= NHS SCOTLAND ================= #
def scrape_scotland(driver, seen_jobs):
    print("🔎 NHS Scotland...")
    url = "https://apply.jobs.scot.nhs.uk/Home/Search"
    driver.get(url)
    WebDriverWait(driver, 20).until(EC.presence_of_all_elements_located((By.TAG_NAME, "tr")))
    rows = driver.find_elements(By.TAG_NAME, "tr")
    for row in rows:
        try:
            a = row.find_element(By.TAG_NAME, "a")
            title = a.text.strip()
            href = a.get_attribute("href")
            if not title or not href:
                continue
            if not relevant_job(title):
                continue
            job_id = href.split("?")[0]
            if job_id in seen_jobs:
                continue
            message = f"🚨 Scotland Job\n\n🏥 {title}\n🔗 {href}"
            print(message)
            send_telegram(message)
            save_seen(job_id)
            seen_jobs.add(job_id)
        except:
            continue

# ================= MAIN LOOP ================= #
def main():
    print("🚀 Smart UK NHS Doctor Job Bot Started...")
    seen_jobs = load_seen()
    driver = get_driver()
    while True:
        try:
            scrape_nhs_jobs(seen_jobs)
            scrape_healthjobsuk(seen_jobs)
            scrape_hscni(driver, seen_jobs)
            scrape_scotland(driver, seen_jobs)
        except Exception as e:
            print("Main loop error:", e)
        print(f"⏳ Sleeping for {CHECK_INTERVAL} seconds...\n")
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()
