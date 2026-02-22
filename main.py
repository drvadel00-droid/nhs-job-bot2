import requests
from bs4 import BeautifulSoup
import time
import re
import os
import datetime
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import requests

# ---------------- CONFIG ---------------- #
BOT_TOKEN = "8213751012:AAFYvubDXeY3xU8vjaWLxNTT7XqMtPhUuwQ"  # Your bot token
CHAT_ID = "-1003888963521"  # Your private channel numeric ID
CHECK_INTERVAL = 120  # seconds
BOT_TOKEN = "8213751012:AAFYvubDXeY3xU8vjaWLxNTT7XqMtPhUuwQ"
CHAT_ID = "-1003888963521"
CHECK_INTERVAL = 300  # Increased to 5 mins to avoid being blocked

URLS = [
    # HealthJobsUK
                  
    "https://www.healthjobsuk.com/job_list?JobSearch_q=&JobSearch_d=&JobSearch_g=&JobSearch_re=_POST&JobSearch_re_0=1&JobSearch_re_1=1-_-_-&JobSearch_re_2=1-_-_--_-_-&JobSearch_Submit=Search&_tr=JobSearch&_ts=94511",

    # NHS Jobs England
    "https://www.jobs.nhs.uk/candidate/search/results?keyword=doctor&sort=publicationDateDesc",

    # Northern Ireland
    "https://jobs.hscni.net/Search?SearchCatID=0",

    # Scotland NHS jobs (public page)
    "https://apply.jobs.scot.nhs.uk/Home/Search"
]

# ---------------- FILTER LOGIC ---------------- #
# (Keep your MEDICAL_SPECIALTIES, GRADE_KEYWORDS, and EXCLUDE_KEYWORDS as they were)
MEDICAL_SPECIALTIES = [
    "medicine", "internal medicine", "general medicine", "paediatric", "pediatric",
    "surgery", "general surgery", "trauma", "orthopaedic", "orthopedic", "plastic",
    "emergency medicine", "emergency department", "oncology", "cardiology",
    "respiratory", "gastroenterology", "neurology", "obstetrics", "gynaecology",
    "haematology"
]

GRADE_KEYWORDS = [
    "foundation", "fy1", "fy2", "f1", "f2",
    "ct1", "ct2", "ct3", "core trainee",
    "st1", "st2", "st3",
    "registrar",
    "sas doctor", "specialty doctor", "trust doctor",
    "clinical fellow", "junior fellow", "research fellow",
    "teaching fellow", "locum doctor"
]

EXCLUDE_KEYWORDS = [
    "consultant", "st4", "st5", "st6", "st7",
    "advanced trainee", "higher specialty",
    "nurse", "midwife", "psychologist", "assistant",
    "admin", "radiographer", "physiotherapist", "manager",
    "director", "healthcare assistant"
]
# ---------------- SELENIUM SETUP ---------------- #
def get_driver():
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    # CRITICAL: Set a window size so the site thinks it's a real desktop
    chrome_options.add_argument("--window-size=1920,1080") 
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    service = Service(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=chrome_options)
    
    
# ---------------- UTILS ---------------- #
def load_seen():
    try:
        if os.path.exists("seen_jobs.txt"):
            with open("seen_jobs.txt", "r") as f:
                return set(f.read().splitlines())
    except:
        return set()
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
    except:
        pass

def extract_job_id(link):
    match = re.search(r'\d+', link)
    return match.group() if match else link

def relevant_job(title):
    title_lower = title.lower()
    if any(ex in title_lower for ex in EXCLUDE_KEYWORDS):
        return False
    if not any(sp in title_lower for sp in MEDICAL_SPECIALTIES):
        return False
    if not any(gr in title_lower for gr in GRADE_KEYWORDS):
        return False
    return True

def normalize_link(link, base):
    if link.startswith("/"):
        return base + link
    return link

# ---------------- SITE CHECK ---------------- #
def check_site(url, seen_jobs):
    print(f"Checking {url}")
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(response.text, "html.parser")
        job_links = soup.find_all("a", href=True)

        base_url = re.match(r"(https?://[^/]+)", url).group(1)

        for a in job_links:
            title = a.get_text(strip=True)
            link = normalize_link(a["href"], base_url)

            if not title or len(title) < 5:
                continue

            # NHS Jobs England may have links without '/Job/', just ensure link has digits
            if not re.search(r"\d+", link):
                continue

            if not relevant_job(title):
                continue

            job_id = extract_job_id(link)
            if job_id in seen_jobs:
                continue

            # Treat all jobs as recent for NHS Jobs England
            message = f"🚨 New Job Found!\n\n🏥 {title}\n🔗 Apply: {link}"
            print(message + "\n")
            send_telegram(message)

            save_seen(job_id)
            seen_jobs.add(job_id)

    except Exception as e:
        print(f"Error checking {url}: {e}")

# ---------------- SCOTLAND CHECK ---------------- #
def check_scotland(seen_jobs):
    print("Checking Scotland jobs...")
    url = "https://apply.jobs.scot.nhs.uk/Home/Search"
    headers = {"User-Agent": "Mozilla/5.0"}
    print(f"Telegram Error: {e}")
        
def relevant_job(title):
    t = title.lower()
    if any(ex in t for ex in EXCLUDE_KEYWORDS): return False
    return any(sp in t for sp in MEDICAL_SPECIALTIES) and any(gr in t for gr in GRADE_KEYWORDS)
                    
# ---------------- SCRAPER LOGIC ---------------- #
def scrape_jobs(driver, url, seen_jobs):
    print(f"🔍 Checking: {url}")
    try:
        response = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(response.text, "html.parser")
        a_tags = soup.find_all("a", href=True)

        for a in a_tags:
            href = a['href']
            if "JobDetail?JobId=" not in href:
                continue
            link = normalize_link(href, "https://apply.jobs.scot.nhs.uk")
            title = a.get_text(strip=True)
            if not relevant_job(title):
                continue
            job_id = extract_job_id(link)
            if job_id in seen_jobs:
                driver.get(url)
        
        # Wait for the main content to load (adjusting to look for common job containers)
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        # Give JS extra time to render the list
        time.sleep(5) 

        # Scroll down slightly to trigger lazy-loading if present
        driver.execute_script("window.scrollTo(0, 500);")

        links = driver.find_elements(By.TAG_NAME, "a")
        
        for a in links:
            try:
                title = a.text.strip()
                href = a.get_attribute("href")
                
                if not href or not title or len(title) < 8:
                    continue
                
                # Check if it's a job link (contains job, vacancy, or 6+ digits)
                if not any(x in href.lower() for x in ["job", "vacancy", "detail"]) and not re.search(r"\d{6,}", href):
                    continue

                if relevant_job(title):
                    # Clean ID extraction
                    job_id_match = re.search(r"\d{5,}", href)
                    job_id = job_id_match.group() if job_id_match else href
                    
                    if job_id not in seen_jobs:
                        msg = f"🚨 New Job Found!\n\n🏥 {title}\n🔗 {href}"
                        print(f"Found: {title}")
                        send_telegram(msg)
                        save_seen(job_id)
                        seen_jobs.add(job_id)
            except:
                continue

            message = f"🚨 Scotland Job Found!\n\n🏥 {title}\n🔗 Apply: {link}"
            print(message + "\n")
            send_telegram(message)
            save_seen(job_id)
            seen_jobs.add(job_id)

    except Exception as e:
        print("Error checking Scotland:", e)

# ---------------- MAIN LOOP ---------------- #
        print(f"⚠️ Error scraping {url}: {e}")
                                             
def main():
    print("🚀 NHS Job Bot started...")
    print("🚀 NHS Job Bot (Dynamic Version) Started...")
    seen_jobs = load_seen()
    while True:
        for url in URLS:
            if "apply.jobs.scot.nhs.uk" in url:
                check_scotland(seen_jobs)
            else:
                check_site(url, seen_jobs)
        time.sleep(CHECK_INTERVAL)
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
