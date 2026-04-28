import time
import re
import os
import requests
from bs4 import BeautifulSoup

# ================= CONFIG ================= #
BOT_TOKEN = "8213751012:AAFYvubDXeY3xU8vjaWLxNTT7XqMtPhUuwQ"
CHAT_ID = "-1003888963521"
CHECK_INTERVAL = 300 
DATA_PATH = os.getenv("PERSISTENT_STORAGE", ".") 
SEEN_FILE = os.path.join(DATA_PATH, "seen_jobs.txt")

# Mimic a real browser
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "en-GB,en-US;q=0.9,en;q=0.8",
    "Referer": "https://www.google.com/"
}

URLS = [
    "https://www.jobs.nhs.uk/candidate/search/results?keyword=doctor&sort=publicationDateDesc"
]

def load_seen():
    if not os.path.exists(SEEN_FILE): return set()
    with open(SEEN_FILE, "r") as f: return set(f.read().splitlines())

def send_telegram(message):
    try:
        requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", data={"chat_id": CHAT_ID, "text": message}, timeout=10)
    except Exception as e:
        print(f"Telegram Error: {e}")

def check_site(url, seen_jobs):
    try:
        # Use requests instead of Playwright to avoid the 403 blocks
        response = requests.get(url, headers=HEADERS, timeout=30)
        if response.status_code != 200:
            print(f"DEBUG: Blocked by {url} (Status: {response.status_code})")
            return

        soup = BeautifulSoup(response.text, "html.parser")
        # Look for job links
        links = soup.select('a[href*="/job/"]')
        
        for a in links:
            title = a.get_text(strip=True)
            link = "https://www.jobs.nhs.uk" + a['href']
            job_id = re.search(r"\d+", link)
            
            if job_id and job_id.group() not in seen_jobs:
                send_telegram(f"🚨 NEW NHS JOB\n\n🏥 {title}\n🔗 {link}")
                seen_jobs.add(job_id.group())
                with open(SEEN_FILE, "a") as f: f.write(job_id.group() + "\n")
    except Exception as e:
        print(f"DEBUG Error: {e}")

def main():
    seen_jobs = load_seen()
    while True:
        for url in URLS:
            check_site(url, seen_jobs)
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()
