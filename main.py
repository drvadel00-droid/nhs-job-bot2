
import requests
import time
import os
import hashlib
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
CHECK_INTERVAL = 300 

# Updated URLs for 2026
URLS = {
    "nhs_england": "https://www.jobs.nhs.uk/candidate/search/results?keyword=doctor&sort=publicationDateDesc",
    "nhs_scotland": "https://apply.jobs.scot.nhs.uk/Home/Job?chkDivision=98,120,118,119,121,99,100,122,123", # Medical/Dental category
    "hscni": "https://jobs.hscni.net/Search?SearchCatID=63", # Medical & Dental specific ID
    "healthjobsuk": "https://www.healthjobsuk.com/job_list/s2/Medical_Dental"
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
}

EXCLUDE_KEYWORDS = ["consultant", "nurse", "midwife", "admin", "manager", "physiotherapist"]
DOCTOR_TERMS = ["doctor", "clinical fellow", "registrar", "trust doctor", "fy1", "fy2", "st1", "ct1"]

# ================= UTILITIES ================= #

def get_job_hash(title, link):
    return hashlib.md5(f"{title}{link}".encode()).hexdigest()

def send_telegram(message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    try: requests.post(url, data={"chat_id": CHAT_ID, "text": message}, timeout=10)
    except: pass

def is_relevant(title):
    t = title.lower()
    if any(ex in t for ex in EXCLUDE_KEYWORDS): return False
    return any(term in t for term in DOCTOR_TERMS)

def get_driver():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument(f"user-agent={HEADERS['User-Agent']}")
    return webdriver.Chrome(options=options)

# ================= SCRAPERS ================= #

def scrape_site(driver, site_name, url, selector):
    print(f"🔎 Checking {site_name}...")
    try:
        driver.get(url)
        # Wait for links to appear
        WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
        
        # Scroll down slightly to trigger lazy loaders
        driver.execute_script("window.scrollTo(0, 500);")
        time.sleep(2)

        jobs = driver.find_elements(By.CSS_SELECTOR, selector)
        seen_jobs = set(open("seen_jobs.txt").read().splitlines()) if os.path.exists("seen_jobs.txt") else set()
        
        for job in jobs[:15]: # Check latest 15
            title = job.text.strip()
            link = job.get_attribute("href")
            
            if is_relevant(title):
                job_id = get_job_hash(title, link)
                if job_id not in seen_jobs:
                    msg = f"🚨 {site_name} Job\n\n🏥 {title}\n🔗 {link}"
                    print(f"✨ New: {title}")
                    send_telegram(msg)
                    with open("seen_jobs.txt", "a") as f: f.write(job_id + "\n")
    except Exception as e:
        print(f"❌ Error on {site_name}")

# ================= MAIN ================= #

def main():
    print("🚀 Doctor Job Bot v2.0 (2026 Compatible) Started...")
    while True:
        driver = get_driver()
        # Define CSS selectors for the links on each site
        scrape_site(driver, "NHS England", URLS["nhs_england"], "a[data-testid='search-result-title']")
        scrape_site(driver, "NHS Scotland", URLS["nhs_scotland"], "a[href*='/Home/Job/']")
        scrape_site(driver, "HSCNI", URLS["hscni"], "a[href*='/Job/']")
        scrape_site(driver, "HealthJobsUK", URLS["healthjobsuk"], "a.jobTitle, .job-list-item a")
        
        driver.quit()
        print(f"⏳ Sleeping {CHECK_INTERVAL}s...")
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()
