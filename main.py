import requests
from bs4 import BeautifulSoup
import time
import os

BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

# Broad TRAC search (UK-wide)
TRAC_URL = "https://www.jobs.nhs.uk/candidate/search/results?keyword=doctor"

KEYWORDS = [
    "general surgery",
    "trauma",
    "orthopaedic",
    "orthopedic",
    "plastic surgery",
    "paediatric surgery",
    "pediatric surgery",
    "internal medicine",
    "general medicine",
    "emergency medicine",
    "emergency department",
    "junior",
    "specialty doctor",
    "trust doctor",
    "st1",
    "st2",
    "st3",
    "clinical fellow",
    "junior fellow",
    "research fellow",
    "core",
    "ct1",
    "ct2"
]

seen_jobs = set()

def send_telegram(message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message}
    requests.post(url, data=payload)

def check_trac():
    try:
        resp = requests.get(TRAC_URL, timeout=15)
        soup = BeautifulSoup(resp.text, "html.parser")

        jobs = soup.find_all("a")

        for job in jobs:
            title = job.get_text(strip=True)
            href = job.get("href")

            if not title or not href:
                continue

            title_lower = title.lower()

            # Ignore consultants
            if "consultant" in title_lower:
                continue

            # Must contain at least one keyword
            if any(k in title_lower for k in KEYWORDS):

                full_link = href if href.startswith("http") else "https://www.jobs.nhs.uk" + href

                if full_link not in seen_jobs:
                    seen_jobs.add(full_link)

                    message = f"🚨 New Doctor Job:\n\n{title}\n\n{full_link}"
                    send_telegram(message)

                    print("Sent:", title)

    except Exception as e:
        print("Error checking TRAC:", e)

if __name__ == "__main__":
    print("Bot started. Monitoring TRAC every 2 minutes...")

    while True:
        check_trac()
        time.sleep(120)  # 2 minutes
