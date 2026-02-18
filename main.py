import requests
from bs4 import BeautifulSoup
import time
import json
import os

# -----------------------------
# Telegram Setup
# -----------------------------
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

if not BOT_TOKEN or not CHAT_ID:
    raise ValueError("BOT_TOKEN or CHAT_ID not set!")

# -----------------------------
# Job Clerk URLs
# -----------------------------
SEARCH_URLS = [
    "https://www.jobclerk.com/jobs?q=surgery",
    "https://www.jobclerk.com/jobs?q=emergency"
]

# Keywords filter
KEYWORDS = ["emergency", "surgery", "trust doctor", "clinical fellow"]

# Persist seen jobs
SEEN_FILE = "seen_jobs.json"
if os.path.exists(SEEN_FILE):
    with open(SEEN_FILE, "r") as f:
        seen_jobs = set(json.load(f))
else:
    seen_jobs = set()

def save_seen_jobs():
    with open(SEEN_FILE, "w") as f:
        json.dump(list(seen_jobs), f)

# Send Telegram alert
def send_telegram(message):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        data = {"chat_id": CHAT_ID, "text": message}
        resp = requests.post(url, data=data)
        if resp.status_code != 200:
            print("Failed to send message:", resp.text)
    except Exception as e:
        print("Telegram error:", e)

# Check Job Clerk Pages
def check_jobs():
    global seen_jobs
    for url in SEARCH_URLS:
        try:
            response = requests.get(url, timeout=10)
            soup = BeautifulSoup(response.text, "html.parser")
            
            # Scrape all <a> links
            links = soup.find_all("a", href=True)
            
            for link in links:
                job_url = link["href"]
                if "/job/" in job_url:
                    if not job_url.startswith("http"):
                        job_url = "https://www.jobclerk.com" + job_url
                    
                    if any(keyword in link.text.lower() for keyword in KEYWORDS):
                        if job_url not in seen_jobs:
                            seen_jobs.add(job_url)
                            save_seen_jobs()
                            send_telegram(f"🚨 New Job Posted:\n{job_url}")
        except Exception as e:
            print(f"Error checking {url}: {e}")

# Main loop
print("Bot started. Monitoring Job Clerk URLs...")
while True:
    check_jobs()
    time.sleep(180)  # every 3 minutes
