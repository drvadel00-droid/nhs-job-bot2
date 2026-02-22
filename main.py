import requests
from bs4 import BeautifulSoup
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

# ---------------- CONFIG ---------------- #
BOT_TOKEN = "YOUR_BOT_TOKEN"
CHAT_ID = "YOUR_CHAT_ID"
CHECK_INTERVAL = 300  # 5 minutes

URLS = [
    "https://www.healthjobsuk.com/job_list?JobSearch_q=&JobSearch_d=&JobSearch_g=&JobSearch_re=_POST&JobSearch_re_0=1&JobSearch_re_1=1-_-_-&JobSearch_re_2=1-_-_--_-_-&JobSearch_Submit=Search&_tr=JobSearch&_ts=94511",
    "https://www.jobs.nhs.uk/candidate/search/results?keyword=doctor&sort=publicationDateDesc",
    "https://jobs.hscni.net/Search?SearchCatID=0",
]

SCOTLAND_URL = "https://apply.jobs.scot.nhs.uk/Home/Search"

# ---------------- FILTER LOGIC ---------------- #

MEDICAL_SPECIALTIES = [
    "medicine", "internal medicine", "general medicine",
    "paediatric", "pediatric", "surgery", "trauma",
    "orthopaedic", "orthopedic", "emergency",
    "oncology", "cardiology", "respiratory",
    "gastroenterology", "neurology",
    "obstetrics", "gynaecology", "haematology"
]

GRADE_KEYWORDS = [
    "foundation", "fy1", "fy2",
    "ct1", "ct2", "ct3",
    "st1", "st2", "st3",
    "registrar", "sas doctor",
    "specialty doctor", "trust doctor",
    "clinical fellow", "junior fellow",
    "locum doctor"
]

EXCLUDE_KEYWORDS = [
    "consultant", "st4", "st5", "st6", "st7",
    "nurse", "midwife", "psychologist",
    "admin", "radiographer",
    "physiotherapist", "manager",
    "director", "assistant"
]

# ---------------- DRIVER SETUP ---------------- #

def get_driver():
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")

    chrome_options.binary_location = "/usr/bin/chromium"

    service = Service("/usr/bin/chromedriver")

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
    if not BOT_TOKEN or not CHAT_ID:
        return
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message}
    try:
        requests.post(url, data=payload, timeout=10)
    except Exception as e:
        print("Telegram Error:", e)

def extract_job_id(link):
    match = re.search(r"\d{5,}", link)
    return match.group() if match else link

def relevant_job(title):
    t = title.lower()
    if any(ex in t for ex in EXCLUDE_KEYWORDS):
        return False
    if not any(sp in t for sp in MEDICAL_SPECIALTIES):
        return False
    if not any(gr in t for gr in GRADE_KEYWORDS):
        return False
    return True

def normalize_link(link, base):
    if link.startswith("/"):
        return base + link
    return link

# ---------------- REQUESTS SCRAPER ---------------- #

def check_site(url, seen_jobs):
    print(f"Checking {url}")
    headers = {"User-Agent": "Mozilla/5.0"}

    try:
        response = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(response.text, "html.parser")
        links = soup.find_all("a", href=True)

        base_url = re.match(r"(https?://[^/]+)", url).group(1)

        for a in links:
            title = a.get_text(strip=True)
            link = normalize_link(a["href"], base_url)

            if not title or len(title) < 6:
                continue

            if not re.search(r"\d+", link):
                continue

            if not relevant_job(title):
                continue

            job_id = extract_job_id(link)
            if job_id in seen_jobs:
                continue

            message = f"🚨 New Job Found!\n\n🏥 {title}\n🔗 {link}"
            print(message)
            send_telegram(message)

            save_seen(job_id)
            seen_jobs.add(job_id)

    except Exception as e:
        print(f"Error checking {url}: {e}")

# ---------------- SCOTLAND (SELENIUM) ---------------- #

def check_scotland(driver, seen_jobs):
    print("Checking Scotland jobs...")

    try:
        driver.get(SCOTLAND_URL)

        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )

        time.sleep(5)

        links = driver.find_elements(By.TAG_NAME, "a")

        for a in links:
            title = a.text.strip()
            href = a.get_attribute("href")

            if not href or not title or len(title) < 8:
                continue

            if "JobDetail" not in href and not re.search(r"\d{6,}", href):
                continue

            if not relevant_job(title):
                continue

            job_id = extract_job_id(href)
            if job_id in seen_jobs:
                continue

            message = f"🚨 Scotland Job Found!\n\n🏥 {title}\n🔗 {href}"
            print(message)
            send_telegram(message)

            save_seen(job_id)
            seen_jobs.add(job_id)

    except Exception as e:
        print("Error checking Scotland:", e)

# ---------------- MAIN LOOP ---------------- #

def main():
    print("🚀 NHS Job Bot Started...")

    seen_jobs = load_seen()
    driver = get_driver()

    try:
        while True:
            for url in URLS:
                check_site(url, seen_jobs)

            check_scotland(driver, seen_jobs)

            print(f"Waiting {CHECK_INTERVAL} seconds...\n")
            time.sleep(CHECK_INTERVAL)

    except KeyboardInterrupt:
        print("Stopping bot...")

    finally:
        driver.quit()

if __name__ == "__main__":
    main()
