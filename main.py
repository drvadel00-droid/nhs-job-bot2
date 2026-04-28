import time
import re
import os
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import requests

# ================= CONFIG ================= #
BOT_TOKEN = "8213751012:AAFYvubDXeY3xU8vjaWLxNTT7XqMtPhUuwQ"
CHAT_ID = "-1003888963521"
CHECK_INTERVAL = 300 
DATA_PATH = os.getenv("PERSISTENT_STORAGE", ".") 
SEEN_FILE = os.path.join(DATA_PATH, "seen_jobs.txt")

# ... (Keep your existing URLS and Filters lists here) ...

def relevant_job(title):
    t = title.lower()
    return not any(ex in t for ex in EXCLUDE_KEYWORDS) and any(sp in t for sp in MEDICAL_SPECIALTIES) and any(gr in t for gr in GRADE_KEYWORDS)

def send_telegram(message):
    try:
        requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", data={"chat_id": CHAT_ID, "text": message}, timeout=10)
    except Exception as e:
        print(f"Telegram Error: {e}")

def load_seen():
    if not os.path.exists(SEEN_FILE): return set()
    with open(SEEN_FILE, "r") as f: return set(f.read().splitlines())

def check_site(url, seen_jobs):
    print(f"DEBUG: Checking URL: {url}")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            page.goto(url, wait_until="networkidle", timeout=60000)
            soup = BeautifulSoup(page.content(), "html.parser")
            
            links = soup.select('a[href*="/Job/"], a[href*="/job/"]')
            print(f"DEBUG: Found {len(links)} candidate links.")
            
            for a in links:
                title = a.get_text(strip=True)
                if not title: continue
                
                print(f"DEBUG: Scraped Title: {title}")
                
                if not relevant_job(title):
                    continue
                
                link = a['href']
                if not link.startswith("http"): link = "/".join(url.split('/')[:3]) + link
                
                job_id = re.search(r"\d+", link)
                if job_id and job_id.group() not in seen_jobs:
                    job_id_str = job_id.group()
                    print(f"DEBUG: FOUND NEW MATCH: {title}")
                    send_telegram(f"🚨 NEW NHS JOB\n\n🏥 {title}\n🔗 {link}")
                    seen_jobs.add(job_id_str)
                    with open(SEEN_FILE, "a") as f: f.write(job_id_str + "\n")
                    
        except Exception as e:
            print(f"DEBUG: Scraping Error: {e}")
        finally:
            browser.close()

def main():
    seen_jobs = load_seen()
    print("DEBUG: Bot started. Initial scan...")
    while True:
        for url in URLS:
            check_site(url, seen_jobs)
        print(f"DEBUG: Cycle complete. Sleeping {CHECK_INTERVAL}s")
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()
