import os
import time
import json
import requests
from playwright.sync_api import sync_playwright

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
    "https://www.jobclerk.com/jobs?q=surgery&grade=Junior&grade=Senior",
    "https://www.jobclerk.com/jobs?q=emergency&grade=Junior&grade=Senior"
]

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

# -----------------------------
# Scrape Job Clerk using Playwright
# -----------------------------
def check_jobs():
    global seen_jobs
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        for url in SEARCH_URLS:
            try:
                page.goto(url, timeout=60000)
                page.wait_for_timeout(5000)  # wait for JS to load

                # Grab all <a> links
                links = page.query_selector_all("a")
                jobs_found = 0

                for link in links:
                    job_title = link.inner_text().strip()
                    job_url = link.get_attribute("href")

                    if not job_url or "/job/" not in job_url:
                        continue
                    if not job_url.startswith("http"):
                        job_url = "https://www.jobclerk.com" + job_url

                    # Keyword filter
                    if not any(keyword in job_title.lower() for keyword in KEYWORDS):
                        continue

                    if job_url not in seen_jobs:
                        seen_jobs.add(job_url)
                        save_seen_jobs()
                        send_telegram(f"🚨 Job Found:\n{job_title}\n{job_url}")
                        jobs_found += 1

                print(f"Found {jobs_found} matching jobs on {url}")

            except Exception as e:
                print(f"Error checking {url}: {e}")

        browser.close()

# -----------------------------
# Main loop
# -----------------------------
print("Bot started. Monitoring Job Clerk URLs...")
while True:
    check_jobs()
    time.sleep(60)
