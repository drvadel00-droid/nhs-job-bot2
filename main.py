import time
import re
import os
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import requests

# ---------------- CONFIG ---------------- #
BOT_TOKEN = "8213751012:AAFYvubDXeY3xU8vjaWLxNTT7XqMtPhUuwQ"
CHAT_ID = "-1003888963521"
CHECK_INTERVAL = 300  # Increased to 5 mins to avoid being blocked

URLS = [
    "https://www.healthjobsuk.com/job_list?JobSearch_q=doctor",
    "https://www.jobs.nhs.uk/candidate/search/results?keyword=doctor&sort=publicationDateDesc",
    "https://jobs.hscni.net/Search?SearchCatID=0",
    "https://apply.jobs.scot.nhs.uk/Home/Search"
]

# (Keep your MEDICAL_SPECIALTIES, GRADE_KEYWORDS, and EXCLUDE_KEYWORDS as they were)
MEDICAL_SPECIALTIES = ["medicine", "surgery", "emergency", "cardiology", "pediatric", "paediatric"] # ... etc
GRADE_KEYWORDS = ["fy1", "fy2", "sho", "registrar", "clinical fellow", "trust doctor"] # ... etc
EXCLUDE_KEYWORDS = ["nurse", "midwife", "consultant", "admin"] # ... etc

# ---------------- SELENIUM SETUP ---------------- #
def get_driver():
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # Run without a window
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    service = Service(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=chrome_options)

# ---------------- UTILS ---------------- #
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
        print(f"Telegram Error: {e}")

def relevant_job(title):
    t = title.lower()
    if any(ex in t for ex in EXCLUDE_KEYWORDS): return False
    return any(sp in t for sp in MEDICAL_SPECIALTIES) and any(gr in t for gr in GRADE_KEYWORDS)

# ---------------- SCRAPER LOGIC ---------------- #
def scrape_jobs(driver, url, seen_jobs):
    print(f"🔍 Checking: {url}")
    driver.get(url)
    
    # Wait up to 10 seconds for anchor tags to appear
    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "a"))
        )
        # Small sleep to allow JS to finish rendering lists
        time.sleep(3) 
    except:
        print(f"Timeout waiting for {url}")
        return

    links = driver.find_elements(By.TAG_NAME, "a")
    base_url = re.match(r"(https?://[^/]+)", url).group(1)

    for a in links:
        try:
            title = a.text.strip()
            href = a.get_attribute("href")
            
            if not href or not title or len(title) < 10:
                continue
            
            # Filter for job-like links (usually contain ID numbers)
            if not re.search(r"\d{5,}", href):
                continue

            if relevant_job(title):
                job_id = re.search(r"\d+", href).group() if re.search(r"\d+", href) else href
                
                if job_id not in seen_jobs:
                    msg = f"🚨 New Job!\n\n🏥 {title}\n🔗 {href}"
                    print(f"Found: {title}")
                    send_telegram(msg)
                    save_seen(job_id)
                    seen_jobs.add(job_id)
        except:
            continue

def main():
    print("🚀 NHS Job Bot (Dynamic Version) Started...")
    seen_jobs = load_seen()
    driver = get_driver()
    
    try:
        while True:
            for url in URLS:
                scrape_jobs(driver, url, seen_jobs)
            print(f"Waiting {CHECK_INTERVAL}s...")
            time.sleep(CHECK_INTERVAL)
    except KeyboardInterrupt:
        print("Stopping...")
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
