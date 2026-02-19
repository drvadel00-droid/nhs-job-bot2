import requests
import json
import os
from datetime import datetime, timedelta

BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

SEARCH_URLS = [
    "https://www.jobclerk.com/jobs?q=surgery&grade=Junior&grade=Senior",
    "https://www.jobclerk.com/jobs?q=emergency&grade=Junior&grade=Senior"
]

KEYWORDS = ["emergency", "surgery", "trust doctor", "clinical fellow"]

SEEN_FILE = "seen_jobs.json"
if os.path.exists(SEEN_FILE):
    with open(SEEN_FILE, "r") as f:
        seen_jobs = set(json.load(f))
else:
    seen_jobs = set()

def save_seen_jobs():
    with open(SEEN_FILE, "w") as f:
        json.dump(list(seen_jobs), f)

def send_telegram(message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {"chat_id": CHAT_ID, "text": message}
    resp = requests.post(url, data=data)
    if resp.status_code != 200:
        print("Telegram send error:", resp.text)

def fetch_jobs():
    global seen_jobs
    for url in SEARCH_URLS:
        try:
            resp = requests.get(url)
            if resp.status_code != 200:
                print(f"Failed to fetch {url}")
                continue

            html = resp.text

            # TEMP: crude way to find job links in HTML
            # We'll improve this if the site has a JSON/API
            jobs_found = 0
            for line in html.splitlines():
                if "/job/" in line.lower():
                    # crude extraction of URL
                    start = line.find("/job/")
                    end = line.find('"', start)
                    job_url = line[start:end]

                    if not job_url.startswith("http"):
                        job_url = "https://www.jobclerk.com" + job_url

                    # crude extraction of title
                    title_start = line.find(">") + 1
                    title_end = line.find("<", title_start)
                    job_title = line[title_start:title_end].strip()

                    if not any(k in job_title.lower() for k in KEYWORDS):
                        continue

                    if job_url not in seen_jobs:
                        seen_jobs.add(job_url)
                        save_seen_jobs()
                        send_telegram(f"🚨 Job Found:\n{job_title}\n{job_url}")
                        jobs_found += 1

            print(f"Found {jobs_found} matching jobs on {url}")

        except Exception as e:
            print(f"Error fetching {url}: {e}")

# Run once for testing
fetch_jobs()
