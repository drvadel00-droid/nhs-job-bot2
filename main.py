import os
import time
import requests
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
CHECK_INTERVAL = 300  # seconds
HEALTHJOBS_URL = "https://www.healthjobsuk.com/job_list"

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

# ================= DRIVER ================= #

def get_driver():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    service = Service()
    return webdriver.Chrome(service=service, options=options)

# ================= SCRAPER ================= #

def scrape_healthjobs(seen_jobs):
    driver = get_driver()
    driver.get(HEALTHJOBS_URL)
    print("🔎 HealthJobsUK - Loading first page...")

    try:
        while True:
            # Wait for job cards
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
                job_id = href.split("?")[0]
                if job_id in seen_jobs:
                    continue
                message = f"🚨 HealthJobsUK Job\n🏥 {title}\n🔗 {href}"
                print(message)
                send_telegram(message)
                save_seen(job_id)
                seen_jobs.add(job_id)
            
            # Check if "Next" page exists
            try:
                next_button = driver.find_element(By.CSS_SELECTOR, "a.next")
                if "disabled" in next_button.get_attribute("class"):
                    break
                next_button.click()
                time.sleep(3)  # wait for next page to load
            except:
                break  # no next page, exit loop

    except Exception as e:
        print("Error scraping HealthJobsUK:", e)
    finally:
        driver.quit()

# ================= MAIN LOOP ================= #

def main():
    seen_jobs = load_seen()
    while True:
        scrape_healthjobs(seen_jobs)
        print(f"⏳ Sleeping for {CHECK_INTERVAL} seconds...\n")
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()
